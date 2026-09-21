"""
detection/template_match.py — OpenCV template matching detector
"""

from __future__ import annotations
from pathlib import Path
import time
import cv2
import numpy as np
from detection.base_detector import BaseDetector, DetectionResult
from utils.logger import get_logger

log = get_logger("template_match")
_WARN_THROTTLE_SEC = 5.0  # Log the same warning at most once per N seconds


class TemplateMatchDetector(BaseDetector):
    """
    Detects a target image inside a screenshot using OpenCV matchTemplate.
    Supports multi-scale detection for slight size differences.
    """

    def __init__(self, template_path: str | Path | None = None, threshold: float = 0.85):
        super().__init__(threshold)
        self._last_warn_time: float = 0.0
        self._template: np.ndarray | None = None
        self._template_gray: np.ndarray | None = None
        self._template_path: Path | None = None

        if template_path:
            self.load_template(template_path)

    def load_template(self, path: str | Path) -> bool:
        """Load template image from disk. Returns True on success."""
        path = Path(path)
        if not path.exists():
            log.error(f"Template not found: {path}")
            return False

        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            log.error(f"Failed to read template image: {path}")
            return False

        self._template = img
        self._template_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        self._template_path = path
        log.info(f"Template loaded: {path}  ({img.shape[1]}×{img.shape[0]})")
        return True

    def is_ready(self) -> bool:
        return self._template is not None

    def find_target(self, image: np.ndarray) -> DetectionResult:
        """Run template matching on the provided BGR image."""
        if not self.is_ready():
            return DetectionResult(found=False)

        img_gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        th, tw = self._template_gray.shape[:2]

        # Guard: template cannot be larger than image
        ih, iw = img_gray.shape[:2]
        if th > ih or tw > iw:
            now = time.monotonic()
            if now - self._last_warn_time >= _WARN_THROTTLE_SEC:
                log.warning(
                    f"Template ({tw}×{th}) is larger than the capture region ({iw}×{ih}). "
                    "Select a larger region or use full screen."
                )
                self._last_warn_time = now
            return DetectionResult(found=False, error="Template larger than region")

        result = cv2.matchTemplate(img_gray, self._template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        confidence = float(max_val)
        if confidence < self._threshold:
            return DetectionResult(found=False, confidence=confidence)

        top_left = max_loc
        center_x = top_left[0] + tw // 2
        center_y = top_left[1] + th // 2

        return DetectionResult(
            found=True,
            x=center_x,
            y=center_y,
            width=tw,
            height=th,
            confidence=confidence,
        )

    @property
    def template_size(self) -> tuple[int, int] | None:
        """Return (width, height) of loaded template, or None."""
        if self._template is not None:
            h, w = self._template.shape[:2]
            return w, h
        return None
