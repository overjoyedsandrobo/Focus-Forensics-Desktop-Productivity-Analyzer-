from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any


PRODUCTIVE_CATEGORIES = {"coding", "writing", "design"}
DISTRACTING_CATEGORIES = {"gaming", "video"}


@dataclass
class DailyReport:
    total_hours: float
    productive_hours: float
    idle_hours: float
    deep_focus_hours: float
    distraction_spikes: int
    productivity_score: int
    category_breakdown_hours: dict[str, float]


def analyze_daily(samples: list[dict[str, Any]]) -> DailyReport:
    if not samples:
        return DailyReport(0.0, 0.0, 0.0, 0.0, 0, 0, {})

    total_seconds = sum(float(s["sample_seconds"]) for s in samples)
    productive_seconds = 0.0
    idle_seconds = 0.0
    category_breakdown_seconds: dict[str, float] = defaultdict(float)
    distraction_spikes = 0

    focus_blocks: list[float] = []
    current_focus_block = 0.0
    previous_category: str | None = None

    for sample in samples:
        seconds = float(sample["sample_seconds"])
        category = str(sample["category"])
        is_idle = bool(sample["is_idle"])

        category_breakdown_seconds[category] += seconds
        if is_idle:
            idle_seconds += seconds

        if category in PRODUCTIVE_CATEGORIES and not is_idle:
            productive_seconds += seconds
            current_focus_block += seconds
        else:
            if current_focus_block > 0:
                focus_blocks.append(current_focus_block)
                current_focus_block = 0.0

        if (
            previous_category in PRODUCTIVE_CATEGORIES
            and category in DISTRACTING_CATEGORIES
            and not is_idle
        ):
            distraction_spikes += 1
        previous_category = category

    if current_focus_block > 0:
        focus_blocks.append(current_focus_block)

    deep_focus_seconds = sum(block for block in focus_blocks if block >= 20 * 60)
    productive_ratio = productive_seconds / total_seconds if total_seconds else 0.0
    deep_focus_bonus = min(20.0, deep_focus_seconds / 3600.0 * 10.0)
    distraction_penalty = min(30.0, distraction_spikes * 3.5)
    score = int(max(0.0, min(100.0, productive_ratio * 80.0 + deep_focus_bonus - distraction_penalty)))

    return DailyReport(
        total_hours=round(total_seconds / 3600.0, 2),
        productive_hours=round(productive_seconds / 3600.0, 2),
        idle_hours=round(idle_seconds / 3600.0, 2),
        deep_focus_hours=round(deep_focus_seconds / 3600.0, 2),
        distraction_spikes=distraction_spikes,
        productivity_score=score,
        category_breakdown_hours={
            category: round(seconds / 3600.0, 2)
            for category, seconds in sorted(category_breakdown_seconds.items(), key=lambda item: item[1], reverse=True)
        },
    )
