from __future__ import annotations

import tkinter as tk
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from focus_forensics.analyzer import DailyReport, TrendReport, analyze_daily, analyze_trend
from focus_forensics.categorizer import CategoryRulesStore, parse_keywords
from focus_forensics.exporter import export_csv, export_json, export_text
from focus_forensics.paths import data_file
from focus_forensics.storage import Storage
from focus_forensics.tracker import ActivityTracker


class FocusForensicsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Focus Forensics")
        self.root.geometry("980x700")

        self.storage = Storage(data_file("focus_forensics.db"))
        self.rules_store = CategoryRulesStore(data_file("category_rules.json"))
        self.tracker = ActivityTracker(self.storage, rules_store=self.rules_store)
        self._tracking = False
        self._refresh_job: str | None = None

        self.status_var = tk.StringVar(value="Stopped")
        self.window_var = tk.StringVar(value="(no data yet)")
        self.score_var = tk.StringVar(value="0")
        self.focus_var = tk.StringVar(value="0.0 h")
        self.spikes_var = tk.StringVar(value="0")
        self.weekly_summary_var = tk.StringVar(value="No data yet")
        self.monthly_summary_var = tk.StringVar(value="No data yet")
        self.rule_category_var = tk.StringVar(value="")
        self.rule_keywords_var = tk.StringVar(value="")

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
        trends = ttk.Frame(notebook, padding=10)
        rules = ttk.Frame(notebook, padding=10)
        notebook.add(dashboard, text="Dashboard")
        notebook.add(trends, text="Trends")
        notebook.add(rules, text="Rules")
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

        trend_stats = ttk.Frame(trends)
        trend_stats.pack(fill=tk.X, pady=(0, 10))

        weekly_card = ttk.LabelFrame(trend_stats, text="Last 7 Days", padding=8)
        weekly_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))
        ttk.Label(weekly_card, textvariable=self.weekly_summary_var, wraplength=420).pack(anchor=tk.W)

        monthly_card = ttk.LabelFrame(trend_stats, text="Last 30 Days", padding=8)
        monthly_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ttk.Label(monthly_card, textvariable=self.monthly_summary_var, wraplength=420).pack(anchor=tk.W)

        self.trend_figure = Figure(figsize=(8, 4), dpi=100)
        self.weekly_ax = self.trend_figure.add_subplot(121)
        self.monthly_ax = self.trend_figure.add_subplot(122)
        self.trend_canvas = FigureCanvasTkAgg(self.trend_figure, trends)
        self.trend_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        form = ttk.LabelFrame(rules, text="Rule Editor", padding=8)
        form.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(form, text="Category").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(form, textvariable=self.rule_category_var, width=24).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(form, text="Keywords (comma-separated)").grid(row=0, column=2, sticky=tk.W, padx=(14, 8))
        ttk.Entry(form, textvariable=self.rule_keywords_var, width=48).grid(row=0, column=3, sticky=tk.W)

        buttons = ttk.Frame(rules)
        buttons.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(buttons, text="Add Rule", command=self.add_rule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Update Selected", command=self.update_selected_rule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Delete Selected", command=self.delete_selected_rule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Reset Defaults", command=self.reset_default_rules).pack(side=tk.LEFT)

        self.rules_tree = ttk.Treeview(
            rules,
            columns=("category", "keywords"),
            show="headings",
            height=16,
        )
        self.rules_tree.heading("category", text="Category")
        self.rules_tree.heading("keywords", text="Keywords")
        self.rules_tree.column("category", width=180, anchor=tk.W)
        self.rules_tree.column("keywords", width=720, anchor=tk.W)
        self.rules_tree.pack(fill=tk.BOTH, expand=True)
        self.rules_tree.bind("<<TreeviewSelect>>", self.on_rule_selected)

        self._render_rules()

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
        self._render_trends()
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

    def _render_trends(self) -> None:
        end_day = date.today()
        weekly_start = end_day - timedelta(days=6)
        monthly_start = end_day - timedelta(days=29)

        weekly_samples = self.storage.get_samples_between(weekly_start, end_day)
        monthly_samples = self.storage.get_samples_between(monthly_start, end_day)
        weekly = analyze_trend(weekly_samples, weekly_start, end_day)
        monthly = analyze_trend(monthly_samples, monthly_start, end_day)

        self.weekly_summary_var.set(self._format_trend_summary(weekly))
        self.monthly_summary_var.set(self._format_trend_summary(monthly))

        self._render_trend_plot(self.weekly_ax, weekly, "7-Day Productivity Score")
        self._render_trend_plot(self.monthly_ax, monthly, "30-Day Productivity Score")
        self.trend_figure.tight_layout()
        self.trend_canvas.draw_idle()

    def _render_trend_plot(self, axis, trend: TrendReport, title: str) -> None:
        axis.clear()
        labels = [point.day.strftime("%m-%d") for point in trend.points]
        values = [point.productivity_score for point in trend.points]
        if values:
            axis.plot(labels, values, marker="o", linewidth=1.8)
            axis.set_ylim(0, 100)
            axis.set_ylabel("Score")
            axis.tick_params(axis="x", rotation=35, labelsize=8)
        axis.set_title(title, fontsize=10)

    def _format_trend_summary(self, trend: TrendReport) -> str:
        return (
            f"Avg score: {trend.average_score} | "
            f"Avg deep focus: {trend.average_deep_focus_hours}h/day | "
            f"Avg spikes: {trend.average_distraction_spikes}/day"
        )

    def _render_rules(self) -> None:
        self.rules_tree.delete(*self.rules_tree.get_children())
        for index, rule in enumerate(self.rules_store.get_rules()):
            self.rules_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(rule.category, ", ".join(rule.keywords)),
            )

    def on_rule_selected(self, _event=None) -> None:
        selected_id = self._selected_rule_id()
        if selected_id is None:
            return
        values = self.rules_tree.item(str(selected_id), "values")
        if not values:
            return
        self.rule_category_var.set(str(values[0]))
        self.rule_keywords_var.set(str(values[1]))

    def _selected_rule_id(self) -> int | None:
        selected = self.rules_tree.selection()
        if not selected:
            return None
        return int(selected[0])

    def add_rule(self) -> None:
        try:
            self.rules_store.add_rule(
                self.rule_category_var.get(),
                parse_keywords(self.rule_keywords_var.get()),
            )
        except ValueError as exc:
            messagebox.showerror("Rules", str(exc))
            return
        self.rule_category_var.set("")
        self.rule_keywords_var.set("")
        self._render_rules()

    def update_selected_rule(self) -> None:
        selected_id = self._selected_rule_id()
        if selected_id is None:
            messagebox.showwarning("Rules", "Select a rule to update.")
            return
        try:
            self.rules_store.update_rule(
                selected_id,
                self.rule_category_var.get(),
                parse_keywords(self.rule_keywords_var.get()),
            )
        except (ValueError, IndexError) as exc:
            messagebox.showerror("Rules", str(exc))
            return
        self._render_rules()
        self.rules_tree.selection_set(str(selected_id))

    def delete_selected_rule(self) -> None:
        selected_id = self._selected_rule_id()
        if selected_id is None:
            messagebox.showwarning("Rules", "Select a rule to delete.")
            return
        try:
            self.rules_store.delete_rule(selected_id)
        except IndexError:
            messagebox.showerror("Rules", "Selected rule no longer exists.")
            return
        self.rule_category_var.set("")
        self.rule_keywords_var.set("")
        self._render_rules()

    def reset_default_rules(self) -> None:
        if not messagebox.askyesno("Rules", "Reset all category rules to defaults?"):
            return
        self.rules_store.reset_defaults()
        self.rule_category_var.set("")
        self.rule_keywords_var.set("")
        self._render_rules()

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
    app = FocusForensicsApp(root)
    root.mainloop()
