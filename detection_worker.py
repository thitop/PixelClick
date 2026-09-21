"""
detection_worker.py — Background detection thread
Runs capture → detect → click loop without blocking the GUI.
Communicates back via callbacks (called on worker thread, use after() for GUI updates).
"""

from __future__ import annotations
import threading
import time
from typing import Callable, Optional
import numpy as np
import cv2

from capture.screen_capture import ScreenCapture
from detection.base_detector import BaseDetector, DetectionResult
from detection.template_match import TemplateMatchDetector
from detection.color_detector import ColorDetector
from mouse.click_controller import ClickController
from utils.logger import get_logger

log = get_logger("worker")

StatusCallback = Callable[[dict], None]


class DetectionWorker:
    """
    Background worker that runs the capture → detect → click loop.

    Thread model:
      - Main thread: GUI (CustomTkinter)
      - Worker thread: Capture + Detect + Click (this class)
      - Status updates are pushed via on_update callback; GUI should
        schedule them with after() to stay thread-safe.
    """

    def __init__(
        self,
        capture: ScreenCapture,
        click_ctrl: ClickController,
        on_update: StatusCallback | None = None,
    ):
        self._capture = capture
        self._click = click_ctrl
        self._on_update = on_update

        self._detector: BaseDetector | None = None
        self._region: dict | None = None  # {x, y, width, height} or None = full screen
        self._interval_ms: int = 50
        self._auto_click: bool = True

        self._running: bool = False
        self._paused: bool = False
        self._thread: threading.Thread | None = None

        # Metrics
        self._fps: float = 0.0
        self._frame_times: list[float] = []
        self._last_result: DetectionResult | None = None
        self._last_frame: np.ndarray | None = None  # BGR preview frame

    # ── Configuration ──────────────────────────────────────────────────

    def set_detector(self, detector: BaseDetector):
        self._detector = detector

    def set_region(self, x: int, y: int, width: int, height: int):
        self._region = {"x": x, "y": y, "width": width, "height": height}

    def clear_region(self):
        """Reset to full-screen capture."""
        self._region = None

    def set_interval_ms(self, ms: int):
        self._interval_ms = max(10, ms)

    def set_auto_click(self, enabled: bool):
        self._auto_click = enabled

    # ── Control ────────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._paused = False
        self._click.enable()
        self._click.reset_counter()
        self._thread = threading.Thread(target=self._run, daemon=True, name="DetectionWorker")
        self._thread.start()
        log.info("Detection worker started.")

    def stop(self):
        self._running = False
        self._click.disable()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        log.info("Detection worker stopped.")

    def pause(self):
        self._paused = True
        log.info("Detection worker paused.")

    def resume(self):
        self._paused = False
        log.info("Detection worker resumed.")

    def toggle_pause(self):
        if self._paused:
            self.resume()
        else:
            self.pause()

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def fps(self) -> float:
        return self._fps

    @property
    def last_frame(self) -> np.ndarray | None:
        return self._last_frame

    # ── Worker loop ────────────────────────────────────────────────────

    def _run(self):
        """Main detection loop running on the worker thread."""
        while self._running:
            if self._paused:
                time.sleep(0.05)
                continue

            t_start = time.monotonic()

            try:
                frame = self._capture_frame()
                result = self._detect(frame)
                annotated = self._annotate(frame.copy(), result)
                self._last_frame = annotated

                if result.found and self._auto_click:
                    rx = self._region["x"] if self._region else 0
                    ry = self._region["y"] if self._region else 0
                    abs_x = result.x + rx
                    abs_y = result.y + ry
                    
                    delay = result.action_delay_ms if result.action_delay_ms >= 0 else None
                    clicked = self._click.move_and_click(abs_x, abs_y, override_delay_ms=delay)
                    
                    if clicked and self._detector:
                        self._detector.advance()

                self._push_update(result)

            except Exception as e:
                log.error(f"Worker loop error: {e}", exc_info=True)

            # FPS tracking
            elapsed = time.monotonic() - t_start
            self._update_fps(elapsed)

            # Sleep remainder of interval
            sleep_sec = max(0.0, self._interval_ms / 1000.0 - elapsed)
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def _capture_frame(self) -> np.ndarray:
        if self._region:
            r = self._region
            return self._capture.capture_region(r["x"], r["y"], r["width"], r["height"])
        return self._capture.capture_screen()

    def _detect(self, frame: np.ndarray) -> DetectionResult:
        if self._detector and self._detector.is_ready():
            return self._detector.find_target(frame)
        return DetectionResult(found=False)

    def _annotate(self, frame: np.ndarray, result: DetectionResult) -> np.ndarray:
        """Draw detection overlay on the frame."""
        if result.found:
            cx, cy = result.x, result.y
            hw, hh = result.width // 2, result.height // 2

            # Bounding box
            cv2.rectangle(
                frame,
                (cx - hw, cy - hh),
                (cx + hw, cy + hh),
                (0, 255, 0), 2
            )
            # Center crosshair
            cv2.drawMarker(frame, (cx, cy), (0, 255, 255),
                           cv2.MARKER_CROSS, 20, 2)
            # Confidence label
            label = f"{result.confidence:.1%}"
            cv2.putText(frame, label, (cx - hw, cy - hh - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return frame

    def _push_update(self, result: DetectionResult):
        if self._on_update:
            status = {
                "found": result.found,
                "confidence": result.confidence,
                "x": result.x,
                "y": result.y,
                "error": result.error,
                "clicks": self._click.click_count,
                "fps": round(self._fps, 1),
                "paused": self._paused,
            }
            self._on_update(status)

    def _update_fps(self, elapsed: float):
        now = time.monotonic()
        self._frame_times.append(now)
        cutoff = now - 1.0  # Keep last 1 second of timestamps
        self._frame_times = [t for t in self._frame_times if t > cutoff]
        self._fps = len(self._frame_times)
