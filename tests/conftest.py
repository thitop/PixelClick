"""Shared fixtures."""
import sys
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def png(path, seed):
    """Write a small random PNG (unicode-safe) and return its path."""
    img = np.random.default_rng(seed).integers(0, 255, (30, 40, 3), dtype=np.uint8)
    cv2.imencode(".png", img)[1].tofile(str(path))
    return path


@pytest.fixture
def make_app():
    """Factory: build a MainWindow from a config without touching global
    hotkeys or the user's settings.json. Skips when there is no display."""
    import tkinter as tk
    import gui.main_window as mw
    from utils.config import load_config
    # Skip only when there is genuinely no display. Errors while building the
    # window are real failures and must not be turned into skips.
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError:
        pytest.skip("no display available")
    made = []
    patches = [mock.patch.object(mw.keyboard, "add_hotkey"),
               mock.patch.object(mw.keyboard, "unhook_all"),
               mock.patch.object(mw, "save_config", lambda c: True)]
    for p in patches:
        p.start()

    def factory(**overrides):
        cfg = load_config()
        cfg["templates"], cfg["region"] = [], None
        cfg.update(overrides)
        window = mw.MainWindow(cfg)
        window.update()
        made.append(window)
        return window

    yield factory
    for w in made:
        try:
            w._on_close()
        except Exception:
            pass
    for p in patches:
        p.stop()


@pytest.fixture
def app(make_app):
    return make_app()
