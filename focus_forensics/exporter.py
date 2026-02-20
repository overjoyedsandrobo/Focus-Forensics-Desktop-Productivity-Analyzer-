from __future__ import annotations

import csv
import json
from datetime import date, datetime
from pathlib import Path

from focus_forensics.analyzer import DailyReport


def export_json(path: Path, target_day: date, report: DailyReport) -> None:
    total_hours = max(report.total_hours, 0.0)
    category_items = []
    for category, hours in report.category_breakdown_hours.items():
        percent = round((hours / total_hours) * 100.0, 1) if total_hours > 0 else 0.0
        category_items.append(
            {
                "category": category,
                "hours": hours,
                "percent_of_day": percent,
            }
        )

    insights: list[str] = []
    if report.productivity_score >= 80:
        insights.append("Strong day: productivity score is in a high-performance range.")
    elif report.productivity_score >= 60:
        insights.append("Moderate day: productivity score is stable with room to improve.")
    else:
        insights.append("Low-productivity day: focus quality and distractions need attention.")

    if report.distraction_spikes > 0:
        insights.append(f"{report.distraction_spikes} distraction spike(s) detected from productive to distracting apps.")
    if report.deep_focus_hours > 0:
        insights.append(f"Deep-focus sessions totaled {report.deep_focus_hours} hour(s).")

    payload = {
        "report_name": "Focus Forensics Daily Report",
        "date": target_day.isoformat(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overview": {
            "total_hours": report.total_hours,
            "productive_hours": report.productive_hours,
            "idle_hours": report.idle_hours,
            "deep_focus_hours": report.deep_focus_hours,
            "distraction_spikes": report.distraction_spikes,
            "productivity_score": report.productivity_score,
        },
        "category_breakdown": category_items,
        "insights": insights,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def export_csv(path: Path, target_day: date, report: DailyReport) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", target_day.isoformat()])
        writer.writerow(["metric", "value"])
        writer.writerow(["total_hours", report.total_hours])
        writer.writerow(["productive_hours", report.productive_hours])
        writer.writerow(["idle_hours", report.idle_hours])
        writer.writerow(["deep_focus_hours", report.deep_focus_hours])
        writer.writerow(["distraction_spikes", report.distraction_spikes])
        writer.writerow(["productivity_score", report.productivity_score])
        writer.writerow([])
        writer.writerow(["category", "hours"])
        for category, hours in report.category_breakdown_hours.items():
            writer.writerow([category, hours])


def export_text(path: Path, target_day: date, report: DailyReport) -> None:
    lines = [
        f"Focus Forensics Daily Summary - {target_day.isoformat()}",
        "",
        f"Total tracked hours: {report.total_hours}",
        f"Productive hours: {report.productive_hours}",
        f"Idle hours: {report.idle_hours}",
        f"Deep focus hours: {report.deep_focus_hours}",
        f"Distraction spikes: {report.distraction_spikes}",
        f"Productivity score: {report.productivity_score}/100",
        "",
        "Category breakdown (hours):",
    ]
    for category, hours in report.category_breakdown_hours.items():
        lines.append(f"- {category}: {hours}")
    path.write_text("\n".join(lines), encoding="utf-8")
