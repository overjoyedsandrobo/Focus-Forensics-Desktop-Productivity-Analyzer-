from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


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
