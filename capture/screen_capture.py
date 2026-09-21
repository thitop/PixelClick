"""
capture/screen_capture.py — Screen capture using MSS
Supports full-screen and region captures.

NOTE: MSS uses Windows GDI internally. Each MSS instance MUST be created
and destroyed on the same thread. We therefore create a fresh context
manager per capture call instead of keeping a persistent instance.
"""

from __future__ import annotations
import numpy as np
import mss
from utils.logger import get_logger

log = get_logger("capture")


class ScreenCapture:
    """
    Thread-safe screen capture manager using MSS.
    Creates a fresh mss context per call to avoid cross-thread GDI errors.
    """

    def capture_screen(self) -> np.ndarray:
        """Capture the entire primary screen. Returns BGR numpy array."""
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Monitor index 1 = primary screen
            return self._grab_to_bgr(sct, monitor)

    def capture_region(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Capture a specific screen region. Returns BGR numpy array."""
        with mss.mss() as sct:
            monitor = {"top": y, "left": x, "width": max(1, width), "height": max(1, height)}
            return self._grab_to_bgr(sct, monitor)

    def get_screen_size(self) -> tuple[int, int]:
        """Return (width, height) of the primary monitor."""
        with mss.mss() as sct:
            m = sct.monitors[1]
            return m["width"], m["height"]

    @staticmethod
    def _grab_to_bgr(sct: mss.mss, monitor: dict) -> np.ndarray:
        """Grab monitor area and convert BGRA → BGR."""
        raw = sct.grab(monitor)
        img = np.frombuffer(raw.raw, dtype=np.uint8).reshape(
            raw.height, raw.width, 4
        )
        return img[:, :, :3]  # Drop alpha channel

    def close(self):
        """No-op: MSS contexts are closed after each capture call."""
        pass
