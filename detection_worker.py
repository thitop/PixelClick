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
        self._join_timeout: float = 2.0

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

    def start(self) -> bool:
        if self._running:
            return False
        # Never run two loops at once: if a previous thread outlived stop()'s
        # join (e.g. a slow full-screen detect), wait for it or refuse.
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._join_timeout)
            if self._thread.is_alive():
                log.warning("Previous detection thread still running; not starting.")
                return False
        self._running = True
        self._paused = False
        self._click.enable()
        self._click.reset_counter()
        self._thread = threading.Thread(target=self._run, daemon=True, name="DetectionWorker")
        self._thread.start()
        log.info("Detection worker started.")
        return True

    def stop(self):
        self._running = False
        self._click.disable()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._join_timeout)
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
        try:
            self._loop()
        finally:
            # The capture keeps a per-thread GDI handle; release it on this thread.
            close = getattr(self._capture, "close", None)
            if close:
                close()

    def _loop(self):
        while self._running:
            if self._paused:
                time.sleep(0.05)
                continue

            t_start = time.monotonic()

            try:
                self._step()
            except Exception as e:
                log.error(f"Worker loop error: {e}", exc_info=True)

            # FPS tracking
            elapsed = time.monotonic() - t_start
            self._update_fps(elapsed)

            # Sleep remainder of interval
            sleep_sec = max(0.0, self._interval_ms / 1000.0 - elapsed)
            if sleep_sec > 0:
                time.sleep(sleep_sec)

    def _step(self):
        """One iteration: capture -> detect -> [wait -> re-detect] -> click -> report."""
        # Emergency stop must work even when nothing is about to be clicked
        # (no target, or cooling down); PyAutoGUI only checks inside its calls.
        if self._click.failsafe_tripped():
            self._push_update(DetectionResult(found=False))  # carries failsafe=True
            return
        frame = self._capture_frame()
        result = self._detect(frame)
        self._last_frame = self._annotate(frame.copy(), result)

        if result.found and self._auto_click and self._click.ready():
            delay_s = result.pre_click_delay_ms / 1000.0
            if delay_s > 0:
                first = result
                waited_for = first.template_index
                self._push_update(first, waiting=True)

                def tick():  # keep preview, timer and status alive during a long wait
                    now_frame = self._capture_frame()
                    self._last_frame = self._annotate(now_frame.copy(), first)
                    self._push_update(first, waiting=True)

                if not self._wait_interruptible(delay_s, on_tick=tick):
                    # Stop / Pause / FailSafe during the wait: no click. Clear the
                    # "waiting" flag so the UI does not claim a click is coming.
                    self._push_update(first)
                    return
                # The screen may have changed while we waited: look again and
                # click where the target is now (or not at all if it is gone).
                frame = self._capture_frame()
                result = self._detect(frame)
                self._last_frame = self._annotate(frame.copy(), result)
                if result.found and result.template_index != waited_for:
                    # A different image matched (First Found mode). Its own wait
                    # has not happened yet, so do not click; the next step will
                    # start that image's wait.
                    self._push_update(result)
                    return

            if result.found:
                rx = self._region["x"] if self._region else 0
                ry = self._region["y"] if self._region else 0
                clicked = self._click.move_and_click(result.x + rx, result.y + ry)
                if clicked and self._detector:
                    self._detector.advance()

        self._push_update(result)

    def _wait_interruptible(self, seconds: float, on_tick=None, tick_every: float = 0.25) -> bool:
        """Sleep in 20 ms steps, calling on_tick every `tick_every` s.
        False if stopped, paused or FailSafe-tripped before it elapsed."""
        deadline = time.monotonic() + seconds
        next_tick = time.monotonic() + tick_every
        while time.monotonic() < deadline:
            if not self._running or self._paused:
                return False
            if self._click.failsafe_tripped():
                return False
            if on_tick and time.monotonic() >= next_tick:
                on_tick()
                next_tick += tick_every
            time.sleep(0.02)
        return self._running and not self._paused

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

    def _push_update(self, result: DetectionResult, waiting: bool = False):
        if self._on_update:
            status = {
                "waiting": waiting,
                "found": result.found,
                "confidence": result.confidence,
                "x": result.x,
                "y": result.y,
                "width": result.width,
                "height": result.height,
                # Absolute screen top-left of the detected box (for overlay)
                "box_x": result.x - result.width // 2 + (self._region["x"] if self._region else 0),
                "box_y": result.y - result.height // 2 + (self._region["y"] if self._region else 0),
                "error": result.error,
                "clicks": self._click.click_count,
                "fps": round(self._fps, 1),
                "paused": self._paused,
                # ClickController disables itself when PyAutoGUI FailSafe fires
                "failsafe": self._running and not self._click.enabled,
            }
            self._on_update(status)

    def _update_fps(self, elapsed: float):
        now = time.monotonic()
        self._frame_times.append(now)
        cutoff = now - 1.0  # Keep last 1 second of timestamps
        self._frame_times = [t for t in self._frame_times if t > cutoff]
        self._fps = len(self._frame_times)
