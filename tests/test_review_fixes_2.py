"""Regression tests for the second batch of code-review fixes."""
import sys
import threading
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Hotkeys: one bad key must not drop the others ──────────────────────────

def test_register_hotkeys_keeps_going_after_a_bad_key():
    from gui.main_window import register_hotkeys
    registered = []

    def fake_add(key, fn):
        if key == "f77":
            raise ValueError("bad key")
        registered.append(key)

    failed = register_hotkeys([("f6", None), ("f77", None), ("f8", None), ("f10", None)],
                              add=fake_add)
    assert failed == ["f77"]
    assert registered == ["f6", "f8", "f10"]


# ── Screen capture reuses one mss instance per thread ──────────────────────

def test_screen_capture_reuses_instance_per_thread():
    import capture.screen_capture as sc
    made = []

    class FakeSct:
        monitors = [None, {"left": 0, "top": 0, "width": 4, "height": 3}]

        def __init__(self):
            made.append(self)

        def grab(self, monitor):
            class Raw:
                width, height = monitor["width"], monitor["height"]
                raw = bytes(width * height * 4)
            return Raw()

        def close(self):
            self.closed = True

    with mock.patch.object(sc, "_MSS", FakeSct):
        cap = sc.ScreenCapture()
        cap.capture_screen(); cap.capture_region(0, 0, 2, 2)
        assert len(made) == 1                       # reused on this thread

        other = threading.Thread(target=cap.capture_screen)
        other.start(); other.join()
        assert len(made) == 2                       # separate instance per thread

        cap.close()
        assert getattr(made[0], "closed", False)    # this thread's instance closed
        cap.capture_screen()
        assert len(made) == 3                       # recreated after close


def test_worker_closes_capture_when_loop_ends():
    from detection_worker import DetectionWorker
    closed = threading.Event()

    class Cap:
        def capture_screen(self):
            return np.zeros((5, 5, 3), np.uint8)

        def close(self):
            closed.set()

    class Click:
        enabled = True
        click_count = 0
        def enable(self): pass
        def disable(self): pass
        def reset_counter(self): pass
        def ready(self, *a): return False
        def failsafe_tripped(self): return False

    w = DetectionWorker(Cap(), Click())
    assert w.start()
    w.stop()
    assert closed.wait(1.0)


# ── MainWindow behaviour (needs a display; `app` fixture in conftest.py) ──

from conftest import png as _png


def test_removing_an_image_while_running_updates_the_live_detector(app, tmp_path):
    from detection.multi_template import MultiTemplateDetector
    app._add_template(_png(tmp_path / "a.png", 1))
    app._add_template(_png(tmp_path / "b.png", 2))
    assert app._build_detector()
    app._running = True                      # as if started (no real thread)
    old = app._worker._detector
    app._remove_template(0)
    new = app._worker._detector
    assert new is not old and isinstance(new, MultiTemplateDetector)
    assert len(new._detectors) == 1


def test_removing_the_last_image_while_running_stops(app, tmp_path):
    app._add_template(_png(tmp_path / "a.png", 1))
    assert app._build_detector()
    app._running = True
    app._remove_template(0)
    assert app._running is False


def test_snip_from_compact_view_returns_to_compact_view(app):
    app._enter_mini_hud(); app.update()
    app._snip_template(); app.update()
    assert app._mini_hud._is_showing is False      # HUD must not be in the snip
    app._on_snip_cancel(); app.update()
    assert app._mini_hud._is_showing is True
    assert app.state() == "withdrawn"              # main window stays hidden


def test_start_error_in_compact_view_shows_main_window(app):
    import gui.main_window as mw
    app._enter_mini_hud(); app.update()
    with mock.patch.object(mw.mb, "showerror") as err:
        app._settings_frame.set_mode("Template Matching")
        app._start()                               # no images -> error
    app.update()
    assert err.called
    assert app.state() != "withdrawn"              # the error is visible
