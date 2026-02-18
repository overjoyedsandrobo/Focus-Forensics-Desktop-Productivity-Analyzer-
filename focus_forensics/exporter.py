from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from focus_forensics.analyzer import DailyReport


def export_json(path: Path, target_day: date, report: DailyReport) -> None:
    payload = {
        "date": target_day.isoformat(),
        "total_hours": report.total_hours,
        "productive_hours": report.productive_hours,
        "idle_hours": report.idle_hours,
        "deep_focus_hours": report.deep_focus_hours,
        "distraction_spikes": report.distraction_spikes,
        "productivity_score": report.productivity_score,
        "category_breakdown_hours": report.category_breakdown_hours,
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
