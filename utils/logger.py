"""
utils/logger.py — Simple logger for Auto Click Detector
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

def get_log_dir() -> Path:
    """logs/ next to the .exe when packaged (the bundle's own folder is a temp
    dir deleted on exit), otherwise next to the project's source."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "logs"
    return Path(__file__).resolve().parent.parent / "logs"


LOG_DIR = get_log_dir()
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
    fh = RotatingFileHandler(LOG_DIR / "autoclick.log", maxBytes=512_000,
                             backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_fmt)
    logger.addHandler(fh)

    return logger
