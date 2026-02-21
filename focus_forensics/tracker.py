from __future__ import annotations

import ctypes
import threading
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import psutil
from pynput import keyboard, mouse

from focus_forensics.categorizer import CategoryRulesStore
from focus_forensics.paths import data_file
from focus_forensics.storage import Storage


SYSTEM_IDLE_PROCESSES = {
    "applicationframehost.exe",
    "calc.exe",
    "calculatorapp.exe",
    "control.exe",
    "explorer.exe",
    "fileexplorer.exe",
    "lockapp.exe",
    "notepad.exe",
    "searchapp.exe",
    "searchhost.exe",
    "shellexperiencehost.exe",
    "startmenuexperiencehost.exe",
    "taskmgr.exe",
    "textinputhost.exe",
}

SYSTEM_IDLE_TITLE_KEYWORDS = (
    "search",
    "start menu",
    "task switching",
    "windows input experience",
)


@dataclass
class WindowInfo:
    title: str
    process_name: str


class ActivityTracker:
    def __init__(
        self,
        storage: Storage,
        rules_store: CategoryRulesStore | None = None,
        unknown_app_callback: Callable[[str, str], None] | None = None,
        sample_interval: float = 3.0,
        idle_threshold_seconds: float = 60.0,
        unknown_prompt_cooldown_seconds: float = 300.0,
    ) -> None:
        self.storage = storage
        self.rules_store = rules_store or CategoryRulesStore(data_file("category_rules.json"))
        self.unknown_app_callback = unknown_app_callback
        self.sample_interval = sample_interval
        self.idle_threshold_seconds = idle_threshold_seconds
        self.unknown_prompt_cooldown_seconds = unknown_prompt_cooldown_seconds

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_input = time.time()
        self._keyboard_events = 0
        self._mouse_events = 0
        self._keyboard_listener: keyboard.Listener | None = None
        self._mouse_listener: mouse.Listener | None = None
        self._pending_unknown_processes: set[str] = set()
        self._unknown_retry_after: dict[str, float] = {}
        self._internal_process_names = {"focusforensics.exe", "focusforensics"}

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
            if self._is_internal_window(window):
                elapsed = time.time() - loop_start
                time.sleep(max(0.05, self.sample_interval - elapsed))
                continue

            category = self._categorize_or_system_idle(window)
            process_key = window.process_name.lower()

            if category == "other":
                now_epoch = time.time()
                notify = False
                with self._lock:
                    retry_after = self._unknown_retry_after.get(process_key, 0.0)
                    if now_epoch >= retry_after and process_key not in self._pending_unknown_processes:
                        self._pending_unknown_processes.add(process_key)
                        notify = True
                if notify and self.unknown_app_callback:
                    self.unknown_app_callback(window.process_name, window.title)
                elapsed = time.time() - loop_start
                time.sleep(max(0.05, self.sample_interval - elapsed))
                continue

            now = time.time()
            with self._lock:
                keyboard_events = self._keyboard_events
                mouse_events = self._mouse_events
                self._keyboard_events = 0
                self._mouse_events = 0
                idle_seconds = max(0.0, now - self._last_input)

            force_idle = category == "system_idle"
            if force_idle:
                keyboard_events = 0
                mouse_events = 0
                idle_seconds = max(idle_seconds, self.sample_interval)
            is_idle = force_idle or idle_seconds >= self.idle_threshold_seconds
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

    def resolve_unknown_process(self, process_name: str, resolved: bool) -> None:
        process_key = process_name.lower()
        with self._lock:
            self._pending_unknown_processes.discard(process_key)
            if resolved:
                self._unknown_retry_after.pop(process_key, None)
            else:
                self._unknown_retry_after[process_key] = time.time() + self.unknown_prompt_cooldown_seconds

    def _is_internal_window(self, window: WindowInfo) -> bool:
        process = window.process_name.lower()
        title = window.title.lower()
        if process in self._internal_process_names:
            return True
        if "focus forensics" in title and process == "python.exe":
            return True
        if "focus forensics" in title and process == "pythonw.exe":
            return True
        return False

    def _categorize_or_system_idle(self, window: WindowInfo) -> str:
        process = window.process_name.lower()
        title = window.title.lower()
        if process in SYSTEM_IDLE_PROCESSES:
            return "system_idle"
        if any(keyword in title for keyword in SYSTEM_IDLE_TITLE_KEYWORDS):
            return "system_idle"
        return self.rules_store.categorize(window.process_name, window.title)


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
