from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import psutil
from pynput import keyboard, mouse

from focus_forensics.categorizer import CategoryRulesStore
from focus_forensics.storage import Storage


@dataclass
class WindowInfo:
    title: str
    process_name: str


class ActivityTracker:
    def __init__(
        self,
        storage: Storage,
        rules_store: CategoryRulesStore | None = None,
        sample_interval: float = 3.0,
        idle_threshold_seconds: float = 60.0,
    ) -> None:
        self.storage = storage
        self.rules_store = rules_store or CategoryRulesStore(Path("category_rules.json"))
        self.sample_interval = sample_interval
        self.idle_threshold_seconds = idle_threshold_seconds

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_input = time.time()
        self._keyboard_events = 0
        self._mouse_events = 0
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None

    def _on_key(self, _key: keyboard.KeyCode) -> None:
        with self._lock:
            self._keyboard_events += 1
            self._last_input = time.time()

    def _on_move(self, _x: int, _y: int) -> None:
        with self._lock:
            self._mouse_events += 1
            self._last_input = time.time()

    def _on_click(self, _x: int, _y: int, _button: mouse.Button, _pressed: bool) -> None:
        with self._lock:
            self._mouse_events += 1
            self._last_input = time.time()

    def _on_scroll(self, _x: int, _y: int, _dx: int, _dy: int) -> None:
        with self._lock:
            self._mouse_events += 1
            self._last_input = time.time()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._keyboard_listener = keyboard.Listener(on_press=self._on_key)
        self._mouse_listener = mouse.Listener(
            on_move=self._on_move,
            on_click=self._on_click,
            on_scroll=self._on_scroll,
        )
        self._keyboard_listener.start()
        self._mouse_listener.start()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while self._running:
            loop_start = time.time()
            window = get_active_window_info()
            category = self.rules_store.categorize(window.process_name, window.title)

            now = time.time()
            with self._lock:
                keyboard_events = self._keyboard_events
                mouse_events = self._mouse_events
                self._keyboard_events = 0
                self._mouse_events = 0
                idle_seconds = max(0.0, now - self._last_input)

            is_idle = idle_seconds >= self.idle_threshold_seconds
            ts = datetime.now().isoformat(timespec="seconds")
            self.storage.insert_sample(
                ts=ts,
                window_title=window.title,
                process_name=window.process_name,
                category=category,
                keyboard_events=keyboard_events,
                mouse_events=mouse_events,
                idle_seconds=idle_seconds,
                is_idle=is_idle,
                sample_seconds=self.sample_interval,
            )
            elapsed = time.time() - loop_start
            time.sleep(max(0.05, self.sample_interval - elapsed))


def get_active_window_info() -> WindowInfo:
    title = "Unknown Window"
    process_name = "unknown.exe"
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            length = user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value or title

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                process_name = psutil.Process(pid.value).name()
    except Exception:
        pass
    return WindowInfo(title=title, process_name=process_name)
