"""
detection/color_detector.py — HSV color-based detection
"""

from __future__ import annotations
import cv2
import numpy as np
from detection.base_detector import BaseDetector, DetectionResult
from utils.logger import get_logger

log = get_logger("color_detector")


class ColorDetector(BaseDetector):
    """
    Detects a colored target using HSV masking + contour analysis.
    Default preset: bright red target.
    """

    PRESETS = {
        "Red":   [(0, 100, 100), (10, 255, 255)],
        "Green": [(40, 70, 70),  (80, 255, 255)],
        "Blue":  [(100, 100, 100), (130, 255, 255)],
        "Yellow": [(20, 100, 100), (35, 255, 255)],
    }

    def __init__(
        self,
        hue_min: int = 0,
        hue_max: int = 10,
        sat_min: int = 100,
        sat_max: int = 255,
        val_min: int = 100,
        val_max: int = 255,
        min_area: int = 200,
        threshold: float = 0.85,
    ):
        super().__init__(threshold)
        self._lower = np.array([hue_min, sat_min, val_min], dtype=np.uint8)
        self._upper = np.array([hue_max, sat_max, val_max], dtype=np.uint8)
        self._min_area = min_area

    def set_color_range(
        self,
        hue_min: int,
        hue_max: int,
        sat_min: int,
        sat_max: int,
        val_min: int,
        val_max: int,
    ):
        self._lower = np.array([hue_min, sat_min, val_min], dtype=np.uint8)
        self._upper = np.array([hue_max, sat_max, val_max], dtype=np.uint8)

    def set_preset(self, name: str):
        """Apply a named color preset."""
        if name not in self.PRESETS:
            log.warning(f"Unknown color preset: {name}")
            return
        lower, upper = self.PRESETS[name]
        self._lower = np.array(lower, dtype=np.uint8)
        self._upper = np.array(upper, dtype=np.uint8)

    def find_target(self, image: np.ndarray) -> DetectionResult:
        """Detect colored target in BGR image using HSV masking."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, self._lower, self._upper)

        # Red wraps around hue 180, add second range
        if self._lower[0] <= 10:
            lower2 = np.array([170, self._lower[1], self._lower[2]], dtype=np.uint8)
            upper2 = np.array([180, self._upper[1], self._upper[2]], dtype=np.uint8)
            mask2 = cv2.inRange(hsv, lower2, upper2)
            mask = cv2.bitwise_or(mask, mask2)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best = None
        best_area = self._min_area

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > best_area:
                best_area = area
                best = cnt

        if best is None:
            return DetectionResult(found=False)

        x, y, w, h = cv2.boundingRect(best)
        cx = x + w // 2
        cy = y + h // 2
        # Confidence approximated as fill ratio of bounding box
        confidence = min(1.0, best_area / (w * h)) if (w * h) > 0 else 0.0

        if confidence < self._threshold:
            return DetectionResult(found=False, confidence=confidence)

        return DetectionResult(
            found=True,
            x=cx,
            y=cy,
            width=w,
            height=h,
            confidence=confidence,
        )
