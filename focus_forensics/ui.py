from __future__ import annotations

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from focus_forensics.analyzer import DailyReport, analyze_daily
from focus_forensics.exporter import export_csv, export_json, export_text
from focus_forensics.storage import Storage
from focus_forensics.tracker import ActivityTracker


class FocusForensicsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Focus Forensics")
        self.root.geometry("980x700")

        self.storage = Storage(Path("focus_forensics.db"))
        self.tracker = ActivityTracker(self.storage)
        self._tracking = False
        self._refresh_job: str | None = None

        self.status_var = tk.StringVar(value="Stopped")
        self.window_var = tk.StringVar(value="(no data yet)")
        self.score_var = tk.StringVar(value="0")
        self.focus_var = tk.StringVar(value="0.0 h")
        self.spikes_var = tk.StringVar(value="0")

        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Start Tracking", command=self.start).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="Stop Tracking", command=self.stop).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="Export Report", command=self.export_report).pack(side=tk.LEFT)
        ttk.Label(top, text="Status:").pack(side=tk.LEFT, padx=(20, 4))
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.LEFT)

        notebook = ttk.Notebook(frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        dashboard = ttk.Frame(notebook, padding=10)
        history = ttk.Frame(notebook, padding=10)
        notebook.add(dashboard, text="Dashboard")
        notebook.add(history, text="History")

        metrics = ttk.Frame(dashboard)
        metrics.pack(fill=tk.X, pady=(0, 12))
        for label, var in (
            ("Productivity Score", self.score_var),
            ("Deep Focus", self.focus_var),
            ("Distraction Spikes", self.spikes_var),
            ("Current Window", self.window_var),
        ):
            card = ttk.LabelFrame(metrics, text=label, padding=8)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
            ttk.Label(card, textvariable=var, wraplength=180).pack(anchor=tk.W)

        self.figure = Figure(figsize=(7, 4), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, dashboard)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        cols = ("time", "window", "process", "category", "idle")
        self.tree = ttk.Treeview(history, columns=cols, show="headings", height=20)
        for col in cols:
            self.tree.heading(col, text=col.title())
        self.tree.column("time", width=160, anchor=tk.W)
        self.tree.column("window", width=360, anchor=tk.W)
        self.tree.column("process", width=140, anchor=tk.W)
        self.tree.column("category", width=100, anchor=tk.W)
        self.tree.column("idle", width=80, anchor=tk.CENTER)
        self.tree.pack(fill=tk.BOTH, expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def start(self) -> None:
        if self._tracking:
            return
        self.tracker.start()
        self._tracking = True
        self.status_var.set("Tracking")

    def stop(self) -> None:
        if not self._tracking:
            return
        self.tracker.stop()
        self._tracking = False
        self.status_var.set("Stopped")

    def _refresh(self) -> None:
        samples = self.storage.get_samples_for_day(date.today())
        report = analyze_daily(samples)
        self._render_metrics(report, samples)
        self._render_chart(report)
        self._render_history()
        self._refresh_job = self.root.after(4000, self._refresh)

    def _render_metrics(self, report: DailyReport, samples: list[dict]) -> None:
        self.score_var.set(str(report.productivity_score))
        self.focus_var.set(f"{report.deep_focus_hours:.2f} h")
        self.spikes_var.set(str(report.distraction_spikes))
        if samples:
            latest = samples[-1]
            self.window_var.set(str(latest["window_title"])[:80])
        else:
            self.window_var.set("(no data yet)")

    def _render_chart(self, report: DailyReport) -> None:
        self.ax.clear()
        categories = list(report.category_breakdown_hours.keys())
        hours = [report.category_breakdown_hours[c] for c in categories]
        if categories:
            self.ax.bar(categories, hours)
            self.ax.set_ylabel("Hours")
            self.ax.set_title("Today's Time by Category")
            self.ax.tick_params(axis="x", rotation=35)
        else:
            self.ax.set_title("No data yet")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _render_history(self) -> None:
        rows = self.storage.get_recent_samples(60)
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            self.tree.insert(
                "",
                tk.END,
                values=(
                    row["ts"],
                    row["window_title"][:60],
                    row["process_name"],
                    row["category"],
                    "yes" if row["is_idle"] else "no",
                ),
            )

    def export_report(self) -> None:
        samples = self.storage.get_samples_for_day(date.today())
        report = analyze_daily(samples)

        path = filedialog.asksaveasfilename(
            title="Export report",
            defaultextension=".json",
            filetypes=[
                ("JSON", "*.json"),
                ("CSV", "*.csv"),
                ("Text", "*.txt"),
            ],
        )
        if not path:
            return
        out_path = Path(path)
        if out_path.suffix.lower() == ".csv":
            export_csv(out_path, date.today(), report)
        elif out_path.suffix.lower() == ".txt":
            export_text(out_path, date.today(), report)
        else:
            export_json(out_path, date.today(), report)
        messagebox.showinfo("Focus Forensics", f"Report exported to:\n{out_path}")

    def _on_close(self) -> None:
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
        if self._tracking:
            self.tracker.stop()
        self.storage.close()
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    root.app = FocusForensicsApp(root)  # Keep a strong reference for app lifetime.
    root.mainloop()
