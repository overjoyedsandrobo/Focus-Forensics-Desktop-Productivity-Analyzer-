from __future__ import annotations

import threading
from typing import Callable

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover - optional runtime dependency
    pystray = None
    Image = None
    ImageDraw = None


class TrayController:
    def __init__(self, on_show: Callable[[], None], on_exit: Callable[[], None]) -> None:
        self._on_show = on_show
        self._on_exit = on_exit
        self._icon = None
        self._thread: threading.Thread | None = None

    @property
    def available(self) -> bool:
        return pystray is not None and Image is not None and ImageDraw is not None

    def start(self) -> bool:
        if not self.available or self._thread is not None:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Show Focus Forensics", self._handle_show),
            pystray.MenuItem("Exit", self._handle_exit),
        )
        self._icon = pystray.Icon("focus_forensics", self._build_icon_image(), "Focus Forensics", menu)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()
        self._icon = None
        self._thread = None

    def notify(self, title: str, message: str) -> None:
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
            except Exception:
                pass

    def _handle_show(self, _icon, _item) -> None:
        self._on_show()

    def _handle_exit(self, _icon, _item) -> None:
        self._on_exit()

    @staticmethod
    def _build_icon_image():
        image = Image.new("RGB", (64, 64), "#1f2a44")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 54, 54), fill="#2f7ed8")
        draw.rectangle((18, 18, 46, 46), fill="#ffffff")
        draw.rectangle((24, 24, 40, 40), fill="#2f7ed8")
        return image
