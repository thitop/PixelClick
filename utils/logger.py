"""
utils/logger.py — Simple logger for Auto Click Detector
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

_fmt = logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def get_logger(name: str) -> logging.Logger:
    """Get or create a named logger with console and file handlers."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(_fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(LOG_DIR / "autoclick.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_fmt)
    logger.addHandler(fh)

    return logger
