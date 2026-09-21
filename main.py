"""
main.py — Application entry point for PixelClick Auto Click Detector
"""

import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH when running as a script
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.config import load_config
from utils.logger import get_logger
from gui.main_window import MainWindow

log = get_logger("main")


def main():
    log.info("PixelClick starting…")
    config = load_config()
    app = MainWindow(config)
    app.mainloop()
    log.info("PixelClick exited.")


if __name__ == "__main__":
    main()
