"""Core regression tests (no GUI, no real input)."""
import sys
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mouse.click_controller as cc
from detection.color_detector import ColorDetector
from detection.multi_template import MultiTemplateDetector
from detection.template_match import TemplateMatchDetector
from utils.config import DEFAULT_CONFIG, _deep_merge


def _save_png(path: Path, img: np.ndarray):
    ok, buf = cv2.imencode(".png", img)
    assert ok
    buf.tofile(str(path))


@pytest.fixture
def scene():
    rng = np.random.default_rng(0)
    return rng.integers(0, 255, (200, 300, 3), dtype=np.uint8)


# ── Template matching ──────────────────────────────────────────────────────

def test_template_found_with_unicode_path(tmp_path, scene):
    d = tmp_path / "ทดสอบ"
    d.mkdir()
    p = d / "เป้า.png"
    _save_png(p, scene[50:90, 100:160])
    det = TemplateMatchDetector(p, 0.9)
    assert det.is_ready()
    r = det.find_target(scene)
    assert r.found and (r.x, r.y) == (130, 70)


def test_template_missing_file_not_ready(tmp_path):
    assert not TemplateMatchDetector(tmp_path / "nope.png").is_ready()


def test_flat_template_does_not_crash_or_match(tmp_path, scene):
    p = tmp_path / "flat.png"
    _save_png(p, np.full((20, 20, 3), 128, np.uint8))
    r = TemplateMatchDetector(p, 0.85).find_target(scene)
    assert not r.found


def test_template_larger_than_image(tmp_path, scene):
    p = tmp_path / "big.png"
    _save_png(p, np.zeros((400, 400, 3), np.uint8))
    r = TemplateMatchDetector(p).find_target(scene)
    assert not r.found and r.error


def test_sequential_advances_only_on_advance(tmp_path, scene):
    a, b = tmp_path / "a.png", tmp_path / "b.png"
    _save_png(a, scene[10:40, 10:40])
    _save_png(b, scene[100:140, 200:240])
    det = MultiTemplateDetector(
        [{"path": a, "pre_delay_ms": 100}, {"path": b, "pre_delay_ms": 200}], 0.9, "Sequential")
    r1 = det.find_target(scene)
    assert r1.found and r1.pre_click_delay_ms == 100
    assert det.find_target(scene).pre_click_delay_ms == 100  # not advanced yet
    det.advance()
    r2 = det.find_target(scene)
    assert r2.found and r2.pre_click_delay_ms == 200


# ── Colour detection ───────────────────────────────────────────────────────

def _disc(bgr):
    img = np.zeros((200, 200, 3), np.uint8)
    cv2.circle(img, (100, 80), 30, bgr, -1)
    return img


def test_red_disc_found_despite_round_shape():
    r = ColorDetector(threshold=0.85).find_target(_disc((0, 0, 255)))
    assert r.found and abs(r.x - 100) <= 2 and abs(r.y - 80) <= 2


def test_blue_disc_not_detected_as_red():
    assert not ColorDetector().find_target(_disc((255, 0, 0))).found


def test_non_red_range_not_mirrored():
    # Yellow-ish hue range starting low must not also match reds near 180
    det = ColorDetector(hue_min=20, hue_max=35)
    assert not det.find_target(_disc((0, 0, 255))).found


# ── Click controller ───────────────────────────────────────────────────────

def test_no_cursor_move_during_cooldown():
    c = cc.ClickController(cooldown_ms=500, click_mode="sendinput")
    with mock.patch.object(cc, "_send_input_click"), \
            mock.patch.object(cc.pyautogui, "moveTo") as mv:
        assert c.move_and_click(10, 10) is True
        moves = mv.call_count
        assert c.move_and_click(10, 10) is False
        assert mv.call_count == moves


def test_disabled_controller_never_moves():
    c = cc.ClickController()
    c.disable()
    with mock.patch.object(cc.pyautogui, "moveTo") as mv:
        assert c.move_and_click(1, 1) is False
        mv.assert_not_called()


# ── Config ─────────────────────────────────────────────────────────────────

def test_deep_merge_fills_missing_nested_keys():
    m = _deep_merge(DEFAULT_CONFIG, {"hotkeys": {"start": "f1"}})
    assert m["hotkeys"]["start"] == "f1"
    assert m["hotkeys"]["stop"] == DEFAULT_CONFIG["hotkeys"]["stop"]
    assert DEFAULT_CONFIG["hotkeys"]["start"] == "f6"  # defaults untouched
