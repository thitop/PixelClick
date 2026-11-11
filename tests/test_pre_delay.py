"""Per-image 'delay before click' tests."""
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from detection.multi_template import MultiTemplateDetector
from utils.config import PRE_DELAY_MAX_MS, normalize_template


def _save_png(path: Path, img: np.ndarray):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))


@pytest.fixture
def scene():
    return np.random.default_rng(0).integers(0, 255, (200, 300, 3), dtype=np.uint8)


# ── Task 1: data model and detector ────────────────────────────────────────

def test_normalize_ignores_legacy_delay():
    assert normalize_template({"path": "a.png", "delay": 300})["pre_delay_ms"] == 0


def test_normalize_clamps():
    assert normalize_template({"path": "a.png", "pre_delay_ms": 99999})["pre_delay_ms"] == PRE_DELAY_MAX_MS
    assert normalize_template({"path": "a.png", "pre_delay_ms": -5})["pre_delay_ms"] == 0


def test_detector_reports_pre_delay_per_image(tmp_path, scene):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _save_png(a, scene[10:40, 10:40])
    _save_png(b, scene[100:140, 200:240])
    det = MultiTemplateDetector(
        [{"path": a, "pre_delay_ms": 0}, {"path": b, "pre_delay_ms": 700}],
        0.9, "First Found")
    # First Found returns the first image that matches; check each in turn
    assert det.find_target(scene).pre_click_delay_ms == 0
    only_b = MultiTemplateDetector([{"path": b, "pre_delay_ms": 700}], 0.9, "First Found")
    assert only_b.find_target(scene).pre_click_delay_ms == 700


def test_failed_load_does_not_shift_delays_and_edits_are_live(tmp_path, scene):
    good = tmp_path / "good.png"
    _save_png(good, scene[100:140, 200:240])
    templates = [
        {"path": tmp_path / "missing.png", "pre_delay_ms": 0},
        {"path": good, "pre_delay_ms": 700},
    ]
    det = MultiTemplateDetector(templates, 0.9, "First Found")
    assert det.find_target(scene).pre_click_delay_ms == 700
    templates[1]["pre_delay_ms"] = 200          # edited later, same dict object
    assert det.find_target(scene).pre_click_delay_ms == 200


# ── Task 2: worker wait and re-check ───────────────────────────────────────

import threading
import time

from detection.base_detector import DetectionResult
from detection_worker import DetectionWorker


class FakeCapture:
    def __init__(self):
        self.calls = 0

    def capture_screen(self):
        self.calls += 1
        return np.zeros((50, 50, 3), np.uint8)

    def capture_region(self, x, y, w, h):
        return self.capture_screen()


class FakeClick:
    def __init__(self, ready=True):
        self._ready = ready
        self.clicks = []
        self.click_count = 0
        self.failsafe = False       # test flips this to simulate the mouse hitting the corner
        self.disabled = False

    @property
    def enabled(self):
        return not self.disabled

    def failsafe_tripped(self):
        if self.failsafe:
            self.disabled = True
        return self.failsafe

    def ready(self, override_delay_ms=None):
        return self._ready

    def move_and_click(self, x, y, duration=0.03, override_delay_ms=None):
        self.clicks.append((x, y))
        self.click_count += 1
        return True

    def enable(self): pass
    def disable(self): pass
    def reset_counter(self): pass


class FakeDetector:
    """Returns scripted results in order; repeats the last one when exhausted."""
    def __init__(self, results):
        self.results = list(results)
        self.advanced = 0

    def is_ready(self):
        return True

    def find_target(self, image):
        return self.results.pop(0) if len(self.results) > 1 else self.results[0]

    def advance(self):
        self.advanced += 1


def _found(x, y, delay_ms=0, index=-1):
    return DetectionResult(found=True, x=x, y=y, width=10, height=10,
                           confidence=1.0, pre_click_delay_ms=delay_ms, template_index=index)


def _worker(results, ready=True, on_update=None):
    cap, click, det = FakeCapture(), FakeClick(ready), FakeDetector(results)
    w = DetectionWorker(cap, click, on_update=on_update)
    w._detector, w._running, w._auto_click = det, True, True
    return w, cap, click, det


def test_zero_delay_clicks_immediately_without_recapture():
    w, cap, click, det = _worker([_found(10, 10, 0)])
    w._step()
    assert click.clicks == [(10, 10)] and cap.calls == 1 and det.advanced == 1


def test_delay_then_clicks_new_position():
    w, cap, click, det = _worker([_found(10, 10, 100), _found(20, 25, 100)])
    t0 = time.monotonic()
    w._step()
    assert time.monotonic() - t0 >= 0.09
    assert click.clicks == [(20, 25)] and cap.calls == 2 and det.advanced == 1


def test_target_vanishes_during_wait():
    w, cap, click, det = _worker([_found(10, 10, 50), DetectionResult(found=False)])
    w._step()
    assert click.clicks == [] and det.advanced == 0


def _abort_during_wait(flag_setter):
    w, cap, click, det = _worker([_found(10, 10, 5000)])
    t = threading.Thread(target=w._step)
    t0 = time.monotonic()
    t.start()
    time.sleep(0.1)
    flag_setter(w)
    t.join(timeout=2)
    assert not t.is_alive() and time.monotonic() - t0 < 0.6
    assert click.clicks == [] and det.advanced == 0


def test_stop_during_wait_aborts():
    _abort_during_wait(lambda w: setattr(w, "_running", False))


def test_pause_during_wait_aborts():
    _abort_during_wait(lambda w: setattr(w, "_paused", True))


def test_cooldown_blocks_wait():
    w, cap, click, det = _worker([_found(10, 10, 5000)], ready=False)
    t0 = time.monotonic()
    w._step()
    assert time.monotonic() - t0 < 0.3 and click.clicks == [] and cap.calls == 1


# ── Task 3: UI field parsing ───────────────────────────────────────────────

from gui.settings_frame import parse_pre_delay


@pytest.mark.parametrize("text,expected", [
    ("0.3", 0.3), ("0.12", 0.1), ("0", 0.0), ("10", 10.0), (" 0.5 ", 0.5), ("1,5", None),
])
def test_parse_pre_delay_valid_and_snapped(text, expected):
    assert parse_pre_delay(text) == expected


@pytest.mark.parametrize("text", ["abc", "-1", "11", "", "nan", "inf"])
def test_parse_pre_delay_invalid_returns_none(text):
    assert parse_pre_delay(text) is None


# ── Final-review fixes ─────────────────────────────────────────────────────

def test_detector_reports_template_index(tmp_path, scene):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _save_png(a, scene[10:40, 10:40])
    _save_png(b, scene[100:140, 200:240])
    ts = [{"path": a, "pre_delay_ms": 0}, {"path": b, "pre_delay_ms": 0}]
    ff = MultiTemplateDetector(ts, 0.9, "First Found")
    assert ff.find_target(scene).template_index == 0
    seq = MultiTemplateDetector(ts, 0.9, "Sequential")
    seq.advance()
    assert seq.find_target(scene).template_index == 1


def test_recheck_finding_a_different_image_does_not_click():
    # First Found: we waited for image 1 (3 s rule) but image 0 now matches first.
    w, cap, click, det = _worker([_found(10, 10, 50, index=1), _found(30, 30, 0, index=0)])
    w._step()
    assert click.clicks == [] and det.advanced == 0


def test_failsafe_during_wait_aborts_and_disables():
    w, cap, click, det = _worker([_found(10, 10, 5000)])
    t = threading.Thread(target=w._step)
    t0 = time.monotonic()
    t.start()
    time.sleep(0.1)
    click.failsafe = True
    t.join(timeout=2)
    assert not t.is_alive() and time.monotonic() - t0 < 0.6
    assert click.clicks == [] and click.disabled


def test_click_controller_failsafe_tripped_in_corner_only():
    from unittest import mock
    import mouse.click_controller as cc
    c = cc.ClickController()
    with mock.patch.object(cc.pyautogui, "position", return_value=(500, 400)):
        assert c.failsafe_tripped() is False and c.enabled
    with mock.patch.object(cc.pyautogui, "position", return_value=(0, 0)):
        assert c.failsafe_tripped() is True and not c.enabled


# ── Minor fixes: pause status, live updates while waiting, pending edits ───

def test_pause_during_wait_clears_waiting_status():
    statuses = []
    w, cap, click, det = _worker([_found(10, 10, 5000)], on_update=statuses.append)
    t = threading.Thread(target=w._step)
    t.start()
    time.sleep(0.1)
    w._paused = True
    t.join(timeout=2)
    assert statuses[0]["waiting"] is True
    assert statuses[-1]["waiting"] is False and statuses[-1]["paused"] is True


def test_status_and_preview_keep_updating_during_a_long_wait():
    statuses = []
    w, cap, click, det = _worker([_found(10, 10, 1000), _found(10, 10, 1000)],
                                 on_update=statuses.append)
    w._step()
    waiting = [s for s in statuses if s["waiting"]]
    assert len(waiting) >= 3            # initial push + roughly every 250 ms
    assert cap.calls >= 4               # live preview frames while waiting + the re-check


def test_commit_pending_applies_uncommitted_typed_delay():
    import tkinter as tk
    import customtkinter as ctk
    from gui.settings_frame import SettingsFrame
    try:
        root = ctk.CTk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    try:
        changes = []
        tmpl = {"path": Path("a.png"), "pre_delay_ms": 0}

        def on_change(i, v):                      # mirrors MainWindow._on_template_delay
            changes.append((i, v))
            tmpl["pre_delay_ms"] = int(round(v * 1000))
        frame = SettingsFrame(root, on_template_delay_change=on_change)
        frame.pack()
        frame.set_template_list([tmpl])

        def find_entry(w):
            for c in w.winfo_children():
                if isinstance(c, ctk.CTkEntry):
                    return c
                r = find_entry(c)
                if r:
                    return r
        entry = find_entry(frame._tmpl_list)
        entry.delete(0, "end"); entry.insert(0, "2")      # typed, never committed
        frame.commit_pending()
        assert changes == [(0, 2.0)] and entry.get() == "2.00"
        frame.commit_pending()                              # idempotent
        assert changes == [(0, 2.0)]
    finally:
        root.destroy()
