from __future__ import annotations

import json
import tkinter as tk
from queue import Empty, Queue
from datetime import date, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from focus_forensics.analyzer import DailyReport, TrendReport, analyze_daily, analyze_trend
from focus_forensics.categorizer import CategoryRulesStore
from focus_forensics.exporter import export_csv, export_json, export_text
from focus_forensics.paths import data_file
from focus_forensics.storage import Storage
from focus_forensics.tray import TrayController
from focus_forensics.tracker import ActivityTracker


class FocusForensicsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Focus Forensics")
        self.root.geometry("980x700")

        self.storage = Storage(data_file("focus_forensics.db"))
        self.settings_path = data_file("settings.json")
        self._settings = self._load_settings()
        self.rules_store = CategoryRulesStore(data_file("category_rules.json"))
        self._unknown_queue: Queue[tuple[str, str]] = Queue()
        self._shutting_down = False
        self._shown_background_hint = False
        self.tracker = ActivityTracker(
            self.storage,
            rules_store=self.rules_store,
            unknown_app_callback=self._queue_unknown_app,
        )
        self.tray = TrayController(self._show_from_background, self._exit_from_tray)
        self._tray_enabled = self.tray.start()
        self._tracking = False
        self._refresh_job: str | None = None

        self.status_var = tk.StringVar(value="Stopped")
        self.window_var = tk.StringVar(value="(no data yet)")
        self.score_var = tk.StringVar(value="0")
        self.focus_var = tk.StringVar(value="0.0 h")
        self.spikes_var = tk.StringVar(value="0")
        self.weekly_summary_var = tk.StringVar(value="No data yet")
        self.monthly_summary_var = tk.StringVar(value="No data yet")
        self.rule_category_var = tk.StringVar(value="coding")
        self.rule_app_var = tk.StringVar(value="")
        self.rule_keyword_var = tk.StringVar(value="")
        self.rule_category_options = tuple(self.rules_store.get_categories())
        self.dark_mode_var = tk.BooleanVar(value=bool(self._settings.get("dark_mode", False)))
        self.style = ttk.Style(self.root)

        self._build_ui()
        self._apply_theme()
        self._refresh()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        top = ttk.Frame(frame)
        top.pack(fill=tk.X)

        ttk.Button(top, text="Start Tracking", command=self.start).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="Stop Tracking", command=self.stop).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top, text="Export Report", command=self.export_report).pack(side=tk.LEFT)
        ttk.Button(top, text="Clear History", command=self.clear_history).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(
            top,
            text="Dark Mode",
            variable=self.dark_mode_var,
            command=self._toggle_dark_mode,
        ).pack(side=tk.RIGHT)
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
        ttk.Label(form, text="Application").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(form, textvariable=self.rule_app_var, width=28).grid(row=0, column=1, sticky=tk.W)
        ttk.Label(form, text="Keyword").grid(row=0, column=2, sticky=tk.W, padx=(14, 8))
        ttk.Entry(form, textvariable=self.rule_keyword_var, width=28).grid(row=0, column=3, sticky=tk.W)
        ttk.Label(form, text="Category").grid(row=0, column=4, sticky=tk.W, padx=(14, 8))
        self.category_combo = ttk.Combobox(
            form,
            textvariable=self.rule_category_var,
            values=self.rule_category_options,
            width=16,
            state="readonly",
        )
        self.category_combo.grid(row=0, column=5, sticky=tk.W)

        buttons = ttk.Frame(rules)
        buttons.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(buttons, text="Add", command=self.add_rule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Delete", command=self.delete_selected_rule).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Add Category", command=self.add_category).pack(side=tk.LEFT, padx=(8, 8))
        ttk.Button(buttons, text="Delete Category", command=self.delete_category).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(buttons, text="Reset Defaults", command=self.reset_default_rules).pack(side=tk.LEFT)

        self.rules_tree = ttk.Treeview(
            rules,
            columns=("application", "keyword", "category"),
            show="headings",
            height=16,
        )
        self.rules_tree.heading("application", text="Application")
        self.rules_tree.heading("keyword", text="Keyword")
        self.rules_tree.heading("category", text="Category")
        self.rules_tree.column("application", width=320, anchor=tk.W)
        self.rules_tree.column("keyword", width=320, anchor=tk.W)
        self.rules_tree.column("category", width=180, anchor=tk.W)
        self.rules_tree.pack(fill=tk.BOTH, expand=True)
        self.rules_tree.bind("<<TreeviewSelect>>", self.on_rule_selected)

        self._render_rules()

        self.root.protocol("WM_DELETE_WINDOW", self._shutdown)
        self.root.bind("<Unmap>", self._on_window_unmap)

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

    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text(encoding="utf-8"))
        except Exception:
            return {"dark_mode": False}

    def _save_settings(self) -> None:
        self.settings_path.write_text(json.dumps(self._settings, indent=2), encoding="utf-8")

    def _toggle_dark_mode(self) -> None:
        self._settings["dark_mode"] = bool(self.dark_mode_var.get())
        self._save_settings()
        self._apply_theme()

    def _apply_theme(self) -> None:
        dark = bool(self.dark_mode_var.get())
        self.style.theme_use("clam")
        if dark:
            colors = {
                "bg": "#161b22",
                "panel": "#0f141b",
                "fg": "#e6edf3",
                "muted": "#9ba9b4",
                "accent": "#2f7ed8",
                "tree_bg": "#11161d",
                "tree_sel": "#1f4f82",
                "chart_bg": "#0f141b",
                "chart_axis": "#e6edf3",
                "chart_grid": "#2a3440",
                "bar": "#4c9ae8",
                "line": "#66b3ff",
            }
        else:
            colors = {
                "bg": "#f3f6fb",
                "panel": "#ffffff",
                "fg": "#1f2933",
                "muted": "#52606d",
                "accent": "#2f7ed8",
                "tree_bg": "#ffffff",
                "tree_sel": "#d9ebff",
                "chart_bg": "#ffffff",
                "chart_axis": "#1f2933",
                "chart_grid": "#d4dde8",
                "bar": "#2f7ed8",
                "line": "#2f7ed8",
            }

        self._theme_colors = colors
        self.root.configure(bg=colors["bg"])
        self.style.configure(".", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TFrame", background=colors["bg"])
        self.style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TLabelframe.Label", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        self.style.configure("TButton", background=colors["panel"], foreground=colors["fg"])
        self.style.configure("TCheckbutton", background=colors["bg"], foreground=colors["fg"])
        self.style.map(
            "TCheckbutton",
            background=[("active", colors["bg"])],
            foreground=[("active", colors["fg"])],
        )
        self.style.configure("TEntry", fieldbackground=colors["panel"], foreground=colors["fg"])
        self.style.configure("Treeview", background=colors["tree_bg"], foreground=colors["fg"], fieldbackground=colors["tree_bg"])
        self.style.configure("Treeview.Heading", background=colors["panel"], foreground=colors["fg"])
        self.style.map("Treeview", background=[("selected", colors["tree_sel"])], foreground=[("selected", colors["fg"])])
        self.style.configure("TNotebook", background=colors["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", background=colors["panel"], foreground=colors["fg"], padding=(10, 5))
        self.style.map("TNotebook.Tab", background=[("selected", colors["accent"])], foreground=[("selected", "#ffffff")])

        self.canvas.get_tk_widget().configure(bg=colors["chart_bg"], highlightthickness=0)
        self.trend_canvas.get_tk_widget().configure(bg=colors["chart_bg"], highlightthickness=0)
        self._apply_chart_theme()

    def _apply_chart_theme(self) -> None:
        colors = self._theme_colors
        for figure in (self.figure, self.trend_figure):
            figure.patch.set_facecolor(colors["chart_bg"])
        for axis in (self.ax, self.weekly_ax, self.monthly_ax):
            axis.set_facecolor(colors["chart_bg"])
            axis.tick_params(axis="x", colors=colors["chart_axis"])
            axis.tick_params(axis="y", colors=colors["chart_axis"])
            axis.xaxis.label.set_color(colors["chart_axis"])
            axis.yaxis.label.set_color(colors["chart_axis"])
            axis.title.set_color(colors["chart_axis"])
            for spine in axis.spines.values():
                spine.set_color(colors["chart_grid"])
            axis.grid(color=colors["chart_grid"], alpha=0.35, linewidth=0.7)

    def _refresh(self) -> None:
        self._process_unknown_prompts()
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
        self._apply_chart_theme()
        categories = list(report.category_breakdown_hours.keys())
        hours = [report.category_breakdown_hours[c] for c in categories]
        if categories:
            self.ax.bar(categories, hours, color=self._theme_colors["bar"])
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

    def _queue_unknown_app(self, process_name: str, window_title: str) -> None:
        self._unknown_queue.put((process_name, window_title))

    def _process_unknown_prompts(self) -> None:
        while True:
            try:
                process_name, window_title = self._unknown_queue.get_nowait()
            except Empty:
                return
            self._prompt_unknown_app(process_name, window_title)

    def _prompt_unknown_app(self, process_name: str, window_title: str) -> None:
        self._show_from_background_now()
        short_title = window_title[:90] if window_title else "(no title)"
        self._bring_prompt_to_front()
        category = simpledialog.askstring(
            "Uncategorized App Detected",
            (
                f"Focus Forensics detected an uncategorized app:\n\n"
                f"Process: {process_name}\n"
                f"Window: {short_title}\n\n"
                "Type the category to use (example: coding, browsing, gaming)."
            ),
            parent=self.root,
        )
        if not category:
            self.tracker.resolve_unknown_process(process_name, resolved=False)
            return

        default_keyword = process_name.rsplit(".", 1)[0].lower()
        keyword = simpledialog.askstring(
            "Keyword for Rule",
            (
                f"Enter a keyword that identifies {process_name}.\n"
                "This will be saved in the selected category rule."
            ),
            initialvalue=default_keyword,
            parent=self.root,
        )
        keyword_value = (keyword or default_keyword).strip().lower()
        if not keyword_value:
            self.tracker.resolve_unknown_process(process_name, resolved=False)
            return

        self._save_keyword_rule(process_name, category.strip().lower(), keyword_value)
        self._render_rules()
        self.tracker.resolve_unknown_process(process_name, resolved=True)

    def _save_keyword_rule(self, application: str, category: str, keyword: str) -> None:
        self.rules_store.upsert_app_rule(application, keyword, category)
        self._refresh_category_options()

    def _render_trend_plot(self, axis, trend: TrendReport, title: str) -> None:
        axis.clear()
        self._apply_chart_theme()
        labels = [point.day.strftime("%m-%d") for point in trend.points]
        values = [point.productivity_score for point in trend.points]
        if values:
            axis.plot(labels, values, marker="o", linewidth=1.8, color=self._theme_colors["line"])
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
        for index, rule in enumerate(self.rules_store.get_app_rules()):
            self.rules_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(rule.application, rule.keyword, rule.category),
            )

    def on_rule_selected(self, _event=None) -> None:
        selected_id = self._selected_rule_id()
        if selected_id is None:
            return
        values = self.rules_tree.item(str(selected_id), "values")
        if not values:
            return
        self.rule_app_var.set(str(values[0]))
        self.rule_keyword_var.set(str(values[1]))
        self.rule_category_var.set(str(values[2]))

    def _selected_rule_id(self) -> int | None:
        selected = self.rules_tree.selection()
        if not selected:
            return None
        return int(selected[0])

    def add_rule(self) -> None:
        try:
            self.rules_store.add_app_rule(
                self.rule_app_var.get(),
                self.rule_keyword_var.get(),
                self.rule_category_var.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Rules", str(exc))
            return
        self.rule_app_var.set("")
        self.rule_keyword_var.set("")
        self._refresh_category_options()
        self._render_rules()

    def delete_selected_rule(self) -> None:
        selected_id = self._selected_rule_id()
        if selected_id is None:
            messagebox.showwarning("Rules", "Select a rule to delete.")
            return
        try:
            self.rules_store.delete_app_rule(selected_id)
        except IndexError:
            messagebox.showerror("Rules", "Selected rule no longer exists.")
            return
        self.rule_app_var.set("")
        self.rule_keyword_var.set("")
        self._refresh_category_options()
        self._render_rules()

    def reset_default_rules(self) -> None:
        if not messagebox.askyesno("Rules", "Reset all category rules to defaults?"):
            return
        self.rules_store.reset_defaults()
        self.rule_app_var.set("")
        self.rule_keyword_var.set("")
        self._refresh_category_options(default_category="coding")
        self._render_rules()

    def add_category(self) -> None:
        name = simpledialog.askstring("Add Category", "Enter new category name:", parent=self.root)
        if not name:
            return
        try:
            self.rules_store.add_category(name)
        except ValueError as exc:
            messagebox.showerror("Category", str(exc))
            return
        self._refresh_category_options(default_category=name.strip().lower())

    def delete_category(self) -> None:
        category = self.rule_category_var.get().strip().lower()
        if not category:
            messagebox.showwarning("Category", "Select a category to delete.")
            return
        if not messagebox.askyesno("Delete Category", f"Delete category '{category}' and its mappings?"):
            return
        try:
            self.rules_store.delete_category(category)
        except ValueError as exc:
            messagebox.showerror("Category", str(exc))
            return
        self._refresh_category_options(default_category="coding")
        self._render_rules()

    def _refresh_category_options(self, default_category: str | None = None) -> None:
        categories = self.rules_store.get_categories()
        if not categories:
            categories = ["coding"]
        self.rule_category_options = tuple(categories)
        self.category_combo.configure(values=self.rule_category_options)
        target = (default_category or self.rule_category_var.get() or categories[0]).strip().lower()
        if target not in categories:
            target = categories[0]
        self.rule_category_var.set(target)

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

    def clear_history(self) -> None:
        if not messagebox.askyesno("Clear History", "Delete all previously recorded activity history?"):
            return
        self.storage.clear_all_samples()
        self._render_history()
        self._render_metrics(analyze_daily([]), [])
        self._render_chart(analyze_daily([]))
        self._render_trends()
        messagebox.showinfo("Clear History", "All recorded history has been deleted.")

    def _on_window_unmap(self, _event=None) -> None:
        if self._shutting_down:
            return
        if self.root.state() == "iconic":
            self._hide_to_background()

    def _hide_to_background(self) -> None:
        if not self._tray_enabled:
            return
        self.root.withdraw()
        if not self._shown_background_hint:
            self.tray.notify(
                "Focus Forensics",
                "App is running in background. Use the tray icon to restore.",
            )
            self._shown_background_hint = True

    def _show_from_background(self) -> None:
        self.root.after(0, self._restore_window)

    def _show_from_background_now(self) -> None:
        self._restore_window()

    def _restore_window(self) -> None:
        if self._shutting_down:
            return
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self.root.update_idletasks()

    def _bring_prompt_to_front(self) -> None:
        self.root.attributes("-topmost", True)
        self.root.after(250, lambda: self.root.attributes("-topmost", False))

    def _exit_from_tray(self) -> None:
        self.root.after(0, self._shutdown)

    def _shutdown(self) -> None:
        if self._shutting_down:
            return
        self._shutting_down = True
        if self._refresh_job:
            self.root.after_cancel(self._refresh_job)
        if self._tracking:
            self.tracker.stop()
        self.tray.stop()
        self.storage.close()
        self.root.destroy()


def run_app() -> None:
    root = tk.Tk()
    app = FocusForensicsApp(root)
    root.mainloop()
