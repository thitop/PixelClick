"""
detection/multi_template.py — Manages multiple template detectors (Sequential or First Found)
"""

from __future__ import annotations
from pathlib import Path
import numpy as np
from detection.base_detector import BaseDetector, DetectionResult
from detection.template_match import TemplateMatchDetector
from utils.logger import get_logger

log = get_logger("multi_template")

class MultiTemplateDetector(BaseDetector):
    """
    Manages multiple TemplateMatchDetectors.
    Supports two modes:
    - Sequential: Look for templates in order, progressing only when found.
    - First Found (Any): Look for all templates and return the first one found.
    """

    def __init__(self, templates: list[dict], threshold: float = 0.85, mode: str = "Sequential"):
        super().__init__(threshold)
        self._mode = mode
        # Each detector keeps a reference to its source dict so pre_delay_ms edits
        # made later (from the UI) are picked up without rebuilding.
        self._detectors: list[tuple[TemplateMatchDetector, dict]] = []
        
        for tmpl in templates:
            path = tmpl.get("path")
            if not path: continue
            
            detector = TemplateMatchDetector(path, threshold)
            if detector.is_ready():
                self._detectors.append((detector, tmpl))
        
        log.info(f"Initialized MultiTemplateDetector with {len(self._detectors)} templates (Mode: {mode})")
        self._current_index = 0

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        self._threshold = max(0.0, min(1.0, value))
        for d, _ in self._detectors:
            d.threshold = self._threshold

    def is_ready(self) -> bool:
        # Ready if we have at least one successfully loaded template
        return len(self._detectors) > 0 and all(d.is_ready() for d, _ in self._detectors)

    def advance(self):
        if self._mode == "Sequential" and self._detectors:
            self._current_index = (self._current_index + 1) % len(self._detectors)

    def find_target(self, image: np.ndarray) -> DetectionResult:
        if not self._detectors:
            return DetectionResult(found=False, error="No templates loaded")

        if self._mode == "Sequential":
            detector, entry = self._detectors[self._current_index]
            res = detector.find_target(image)
            if res.found:
                res.pre_click_delay_ms = int(entry.get("pre_delay_ms", 0))
                res.template_index = self._current_index
            return res

        else:  # First Found
            for index, (detector, entry) in enumerate(self._detectors):
                res = detector.find_target(image)
                if res.found:
                    res.pre_click_delay_ms = int(entry.get("pre_delay_ms", 0))
                    res.template_index = index
                    return res
            return DetectionResult(found=False)
