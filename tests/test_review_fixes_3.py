"""Regression tests for the third bug sweep."""
import time
from types import SimpleNamespace
from unittest import mock

import numpy as np
import pytest

from conftest import png


# ── 1. A click / tiny drag in the selector must count as cancel ────────────

def test_tiny_drag_in_selector_reports_cancel():
    import tkinter as tk
    from gui.region_selector import RegionSelector
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    try:
        calls = []
        sel = RegionSelector(root, on_select=lambda *a: calls.append("select"),
                             on_cancel=lambda: calls.append("cancel"))
        root.update()
        sel._on_press(SimpleNamespace(x_root=200, y_root=200, x=200, y=200))
        sel._on_release(SimpleNamespace(x_root=203, y_root=202, x=203, y=202))
        t0 = time.monotonic()
        while not calls and time.monotonic() - t0 < 1:
            root.update(); time.sleep(0.01)
        assert calls == ["cancel"]
    finally:
        root.destroy()


def test_tiny_drag_brings_main_window_back(app):
    app._snip_template(); app.update()
    assert app.state() == "withdrawn"
    app._on_snip_cancel(); app.update()           # what a tiny drag now triggers
    assert app.state() != "withdrawn"


# ── 2. Snip while running pauses clicking, then resumes ────────────────────

def test_snip_while_running_pauses_then_resumes(app):
    app._running = True                            # as if started
    app._snip_template(); app.update()
    assert app._paused and app._worker.is_paused
    app._on_snip_cancel(); app.update()
    assert not app._paused and not app._worker.is_paused


def test_snip_while_already_paused_stays_paused(app):
    app._running = True
    app._pause_toggle()
    app._snip_template(); app.update()
    app._on_snip_cancel(); app.update()
    assert app._paused                             # user's own pause is kept


# ── 3. Emergency stop works even with no click attempt ─────────────────────

def test_failsafe_corner_stops_without_a_target():
    import mouse.click_controller as cc
    from detection_worker import DetectionWorker
    from detection.base_detector import DetectionResult

    class Cap:
        def capture_screen(self): return np.zeros((5, 5, 3), np.uint8)

    class Det:
        def is_ready(self): return True
        def find_target(self, img): return DetectionResult(found=False)

    statuses = []
    ctrl = cc.ClickController()
    w = DetectionWorker(Cap(), ctrl, on_update=statuses.append)
    w._detector, w._running = Det(), True
    with mock.patch.object(cc.pyautogui, "position", return_value=(0, 0)):
        w._step()
    assert not ctrl.enabled
    assert statuses and statuses[-1]["failsafe"] is True


# ── 4. Only the top-left corner is the emergency stop (as the UI says) ─────

def test_only_top_left_corner_is_failsafe():
    import mouse.click_controller as cc
    assert cc.pyautogui.FAILSAFE_POINTS == [(0, 0)]
    c = cc.ClickController()
    with mock.patch.object(cc.pyautogui, "position", return_value=(0, 1079)):
        assert c.failsafe_tripped() is False and c.enabled


# ── 5. Malformed settings fall back to defaults instead of crashing ────────

@pytest.mark.parametrize("key,bad", [
    ("confidence", "abc"), ("click_delay", None), ("region", ["a", 0, 10, 10]),
    ("templates", ["not-a-dict"]), ("color_detection", {"hue_min": "x"}),
    ("hotkeys", {"start": 123}), ("overlay", "yes"), ("max_clicks_per_second", 0),
    ("templates", "oops"), ("color_detection", "red"), ("hotkeys", None),
])
def test_sanitize_config_replaces_bad_values(key, bad):
    from utils.config import DEFAULT_CONFIG, sanitize_config, _deep_merge
    cfg = _deep_merge(DEFAULT_CONFIG, {})
    cfg[key] = bad
    clean = sanitize_config(cfg)
    expected = DEFAULT_CONFIG[key]
    if key == "templates" and isinstance(bad, list):
        expected = []
    if key in ("color_detection", "hotkeys") and isinstance(bad, dict):
        expected = dict(DEFAULT_CONFIG[key])
    assert clean[key] == expected


def test_sanitize_config_keeps_good_values():
    from utils.config import DEFAULT_CONFIG, sanitize_config, _deep_merge
    cfg = _deep_merge(DEFAULT_CONFIG, {
        "confidence": 0.9, "click_delay": 1.5, "region": [1, 2, 300, 200],
        "templates": [{"path": "a.png", "pre_delay_ms": 500}],
        "hotkeys": {"start": "f2"}, "color_detection": {"hue_min": 20},
    })
    clean = sanitize_config(cfg)
    assert clean["confidence"] == 0.9 and clean["click_delay"] == 1.5
    assert clean["region"] == [1, 2, 300, 200]
    assert clean["templates"] == [{"path": "a.png", "pre_delay_ms": 500}]
    assert clean["hotkeys"]["start"] == "f2" and clean["hotkeys"]["stop"] == "f7"
    assert clean["color_detection"]["hue_min"] == 20


def test_app_opens_with_bad_hotkey_value(make_app):
    app = make_app(hotkeys={"start": 123})
    assert app.winfo_exists()


# ── 6/7. Order and mode changes apply to a running scan ────────────────────

def _running_with_images(app, tmp_path):
    app._add_template(png(tmp_path / "a.png", 1))
    app._add_template(png(tmp_path / "b.png", 2))
    assert app._build_detector()
    app._running = True


def test_changing_order_while_running_applies(app, tmp_path):
    _running_with_images(app, tmp_path)
    assert app._worker._detector._mode == "Sequential"
    sf = app._settings_frame
    sf._order_seg.set("First match")
    sf._on_order("First match")
    assert app._worker._detector._mode == "First Found"


def test_switching_mode_while_running_swaps_detector(app, tmp_path):
    from detection.color_detector import ColorDetector
    from detection.multi_template import MultiTemplateDetector
    _running_with_images(app, tmp_path)
    sf = app._settings_frame
    sf._on_mode_seg("Color")
    assert isinstance(app._worker._detector, ColorDetector)
    sf._on_mode_seg("Image")
    assert isinstance(app._worker._detector, MultiTemplateDetector)


def test_switching_to_image_mode_with_no_images_stops(app):
    from detection.color_detector import ColorDetector
    app._settings_frame.set_mode("Color Detection")
    assert app._build_detector()
    app._running = True
    app._settings_frame._on_mode_seg("Image")
    assert app._running is False


def test_snip_during_color_run_switches_scan_to_images(app, tmp_path):
    import gui.main_window as mw
    from detection.multi_template import MultiTemplateDetector
    app._settings_frame.set_mode("Color Detection")
    assert app._build_detector()
    app._running = True
    with mock.patch.object(mw, "get_config_dir", lambda: tmp_path / "config"):
        app._on_snip_selected(10, 10, 40, 30)      # snip saved under tmp_path/data
    assert app._settings_frame.get_mode() == "Template Matching"
    assert isinstance(app._worker._detector, MultiTemplateDetector)
