"""
capture/screen_capture.py — Screen capture using MSS
Supports full-screen and region captures.

NOTE: MSS uses Windows GDI internally and an instance must be used on the
thread that created it. We keep one instance per thread (thread-local) and
reuse it across frames, instead of building and tearing one down per capture.
The detection worker calls close() on its own thread when its loop ends.
"""

from __future__ import annotations
import threading
import numpy as np
import mss
from utils.logger import get_logger

# mss >= 10 renamed mss.mss -> mss.MSS; support both.
_MSS = getattr(mss, "MSS", None) or mss.mss

log = get_logger("capture")


class ScreenCapture:
    """Thread-safe screen capture manager: one reusable MSS instance per thread."""

    def __init__(self):
        self._local = threading.local()

    def _sct(self):
        sct = getattr(self._local, "sct", None)
        if sct is None:
            sct = _MSS()
            self._local.sct = sct
        return sct

    def capture_screen(self) -> np.ndarray:
        """Capture the entire primary screen. Returns BGR numpy array."""
        sct = self._sct()
        return self._grab_to_bgr(sct, sct.monitors[1])  # 1 = primary screen

    def capture_region(self, x: int, y: int, width: int, height: int) -> np.ndarray:
        """Capture a specific screen region. Returns BGR numpy array."""
        monitor = {"top": y, "left": x, "width": max(1, width), "height": max(1, height)}
        return self._grab_to_bgr(self._sct(), monitor)

    def get_screen_size(self) -> tuple[int, int]:
        """Return (width, height) of the primary monitor."""
        m = self._sct().monitors[1]
        return m["width"], m["height"]

    @staticmethod
    def _grab_to_bgr(sct, monitor: dict) -> np.ndarray:
        """Grab monitor area and convert BGRA → BGR."""
        raw = sct.grab(monitor)
        img = np.frombuffer(raw.raw, dtype=np.uint8).reshape(raw.height, raw.width, 4)
        return img[:, :, :3]  # Drop alpha channel

    def close(self):
        """Release the calling thread's MSS instance (recreated on next use)."""
        sct = getattr(self._local, "sct", None)
        if sct is not None:
            self._local.sct = None
            try:
                sct.close()
            except Exception as e:
                log.debug(f"mss close failed: {e}")
