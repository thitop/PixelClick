"""Regression tests for the code-review fixes (stop freeze, snip tint,
normal-mode FailSafe counting, malformed config values)."""
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mouse.click_controller as cc
from utils.config import normalize_template


# ── Malformed pre_delay_ms must not crash startup ──────────────────────────

@pytest.mark.parametrize("raw,expected", [
    (None, 0), ("abc", 0), ("0.5", 0), ("250", 250), (250.7, 250), ([], 0),
])
def test_normalize_template_tolerates_bad_values(raw, expected):
    assert normalize_template({"path": "a.png", "pre_delay_ms": raw})["pre_delay_ms"] == expected


# ── FailSafe in "normal" click mode is not a successful click ──────────────

def test_normal_mode_failsafe_is_not_counted_as_click():
    c = cc.ClickController(cooldown_ms=0, click_mode="normal")
    with mock.patch.object(cc.pyautogui, "click", side_effect=cc.pyautogui.FailSafeException):
        assert c.click(10, 10) is False
    assert c.click_count == 0 and not c.enabled


# ── Status hand-off never touches Tk from the worker thread ────────────────

def test_latest_only_mailbox_keeps_newest_and_empties():
    from utils.mailbox import LatestOnly
    box = LatestOnly()
    assert box.take() is None
    box.put({"n": 1}); box.put({"n": 2})
    assert box.take() == {"n": 2}
    assert box.take() is None


def test_worker_start_refuses_while_previous_thread_alive():
    from detection_worker import DetectionWorker
    click = SimpleNamespace(enable=lambda: None, disable=lambda: None,
                            reset_counter=lambda: None)
    w = DetectionWorker(capture=None, click_ctrl=click)
    w._join_timeout = 0.1
    gate = threading.Event()
    w._thread = threading.Thread(target=gate.wait, daemon=True)  # a stuck old worker
    w._thread.start()
    try:
        assert w.start() is False
        assert w._running is False
    finally:
        gate.set()


# ── Snip: the dimming overlay must be gone before the screen is captured ───

def test_region_selector_hides_before_reporting_selection():
    import tkinter as tk
    from gui.region_selector import RegionSelector
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    try:
        seen = []
        sel = RegionSelector(root, on_select=lambda *a: seen.append((a, sel.winfo_exists() and sel.winfo_viewable())))
        root.update()
        sel._on_press(SimpleNamespace(x_root=100, y_root=100, x=100, y=100))
        sel._on_release(SimpleNamespace(x_root=300, y_root=250, x=300, y=250))
        assert seen == []                       # not reported synchronously
        t0 = time.monotonic()
        while not seen and time.monotonic() - t0 < 2:
            root.update(); time.sleep(0.01)
        assert seen, "selection never reported"
        args, still_visible = seen[0]
        assert args == (100, 100, 200, 150)
        assert not still_visible                # overlay hidden when capture runs
    finally:
        root.destroy()
