from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class CategoryRule:
    category: str
    keywords: tuple[str, ...]


DEFAULT_RULES: tuple[CategoryRule, ...] = (
    CategoryRule("coding", ("code", "pycharm", "visual studio", "terminal", "powershell", "cmd", "github")),
    CategoryRule("browsing", ("chrome", "firefox", "edge", "browser")),
    CategoryRule("communication", ("teams", "slack", "discord", "mail", "outlook", "zoom")),
    CategoryRule("gaming", ("steam", "epicgames", "riot", "game")),
    CategoryRule("video", ("youtube", "netflix", "twitch", "vlc")),
    CategoryRule("design", ("figma", "photoshop", "illustrator", "canva")),
    CategoryRule("writing", ("word", "notion", "obsidian", "docs")),
)


def categorize(process_name: str, window_title: str, rules: Iterable[CategoryRule] = DEFAULT_RULES) -> str:
    haystack = f"{process_name} {window_title}".lower()
    for rule in rules:
        if any(keyword in haystack for keyword in rule.keywords):
            return rule.category
    return "other"


def parse_keywords(raw: str) -> tuple[str, ...]:
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


class CategoryRulesStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._rules: list[CategoryRule] = []
        self._load_or_defaults()

    def _load_or_defaults(self) -> None:
        if not self.path.exists():
            self._rules = list(DEFAULT_RULES)
            self.save()
            return

        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self._rules = self._deserialize_rules(payload.get("rules", []))
            if not self._rules:
                self._rules = list(DEFAULT_RULES)
        except Exception:
            self._rules = list(DEFAULT_RULES)

    def _deserialize_rules(self, rows: list[dict[str, Any]]) -> list[CategoryRule]:
        rules: list[CategoryRule] = []
        for row in rows:
            category = str(row.get("category", "")).strip().lower()
            keywords_raw = row.get("keywords", [])
            keywords = tuple(
                str(keyword).strip().lower()
                for keyword in keywords_raw
                if str(keyword).strip()
            )
            if category and keywords:
                rules.append(CategoryRule(category=category, keywords=keywords))
        return rules

    def get_rules(self) -> list[CategoryRule]:
        with self._lock:
            return list(self._rules)

    def add_rule(self, category: str, keywords: Iterable[str]) -> None:
        normalized = self._normalize_rule(category, keywords)
        with self._lock:
            self._rules.append(normalized)
            self.save()

    def update_rule(self, index: int, category: str, keywords: Iterable[str]) -> None:
        normalized = self._normalize_rule(category, keywords)
        with self._lock:
            self._rules[index] = normalized
            self.save()

    def delete_rule(self, index: int) -> None:
        with self._lock:
            del self._rules[index]
            self.save()

    def reset_defaults(self) -> None:
        with self._lock:
            self._rules = list(DEFAULT_RULES)
            self.save()

    def _normalize_rule(self, category: str, keywords: Iterable[str]) -> CategoryRule:
        clean_category = category.strip().lower()
        clean_keywords = tuple(keyword.strip().lower() for keyword in keywords if keyword.strip())
        if not clean_category or not clean_keywords:
            raise ValueError("Category and keywords are required.")
        return CategoryRule(category=clean_category, keywords=clean_keywords)

    def save(self) -> None:
        payload = {
            "rules": [
                {"category": rule.category, "keywords": list(rule.keywords)}
                for rule in self._rules
            ]
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def categorize(self, process_name: str, window_title: str) -> str:
        with self._lock:
            current_rules = list(self._rules)
        return categorize(process_name, window_title, current_rules)
