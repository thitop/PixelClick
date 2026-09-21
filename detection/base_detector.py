"""
detection/base_detector.py — Abstract base class for all detectors
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class DetectionResult:
    """Standardized detection result returned by all detectors."""
    found: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    error: str = ""   # Non-empty when something is misconfigured
    action_delay_ms: int = -1

    @property
    def center(self) -> tuple[int, int]:
        return self.x, self.y

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "confidence": self.confidence,
        }


class BaseDetector(ABC):
    """Abstract base class for detection strategies."""

    def __init__(self, threshold: float = 0.85):
        self._threshold = threshold

    @property
    def threshold(self) -> float:
        return self._threshold

    @threshold.setter
    def threshold(self, value: float):
        self._threshold = max(0.0, min(1.0, value))

    @abstractmethod
    def find_target(self, image: np.ndarray) -> DetectionResult:
        """
        Search for the target in the provided BGR image.
        Returns a DetectionResult.
        """
        ...

    def is_ready(self) -> bool:
        """Return True if this detector is configured and ready to run."""
        return True

    def advance(self):
        """Called when the application successfully acts on the detection result."""
        pass
