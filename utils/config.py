"""
utils/config.py — Configuration manager for Auto Click Detector
Loads and saves settings from/to config/settings.json
"""

import copy
import json
import os
import sys
from pathlib import Path

def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except Exception:
        base_path = Path(__file__).parent.parent
    return base_path / relative_path

def get_config_dir() -> Path:
    """Get path to config directory. If bundled, use the directory where the EXE is located."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent / "config"
    return Path(__file__).parent.parent / "config"


DEFAULT_CONFIG = {
    "detection_mode": "template",
    "confidence": 0.85,
    "click_delay": 0.30,
    "capture_region": {
        "x": 0,
        "y": 0,
        "width": 1920,
        "height": 1080
    },
    "hotkeys": {
        "start": "f6",
        "stop": "f7",
        "pause": "f8",
        "select_region": "f9",
        "snip_template": "f10"
    },
    "overlay": True,          # draw a box over the detected target
    "region": None,          # None = full screen, else [x, y, w, h]
    "templates": [],          # [{"path": str, "pre_delay_ms": int}]
    "max_clicks_per_second": 10,
    "cooldown_ms": 300,
    "detection_interval_ms": 50,
    "color_detection": {
        "hue_min": 0,
        "hue_max": 10,
        "sat_min": 100,
        "sat_max": 255,
        "val_min": 100,
        "val_max": 255
    }
}

CONFIG_PATH = get_config_dir() / "settings.json"

PRE_DELAY_MAX_MS = 10_000


def normalize_template(entry: dict) -> dict:
    """Saved/loaded template -> {"path": Path, "pre_delay_ms": int in 0..max}.

    The legacy "delay" key (a copy of the cooldown slider) is ignored on purpose.
    """
    try:  # a hand-edited / partially written config must not stop the app opening
        ms = int(entry.get("pre_delay_ms", 0))
    except (TypeError, ValueError):
        ms = 0
    return {"path": Path(entry["path"]), "pre_delay_ms": max(0, min(PRE_DELAY_MAX_MS, ms))}


_COLOR_MAX = {"hue_min": 180, "hue_max": 180, "sat_min": 255,
              "sat_max": 255, "val_min": 255, "val_max": 255}


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _clamped(v, lo, hi, default):
    return max(lo, min(hi, v)) if _is_num(v) else default


def sanitize_config(cfg: dict) -> dict:
    """Replace values with the wrong type/range by their defaults, so a hand-edited
    settings.json can never stop the app from opening. Returns a new dict."""
    d = DEFAULT_CONFIG
    out = copy.deepcopy(cfg)

    out["confidence"] = _clamped(cfg.get("confidence"), 0.5, 1.0, d["confidence"])
    out["click_delay"] = _clamped(cfg.get("click_delay"), 0.05, 2.0, d["click_delay"])

    mcps = cfg.get("max_clicks_per_second")
    out["max_clicks_per_second"] = int(mcps) if _is_num(mcps) and mcps >= 1 else d["max_clicks_per_second"]

    overlay = cfg.get("overlay")
    out["overlay"] = overlay if isinstance(overlay, bool) else d["overlay"]

    region = cfg.get("region")
    if (isinstance(region, (list, tuple)) and len(region) == 4
            and all(_is_num(v) for v in region) and region[2] > 0 and region[3] > 0):
        out["region"] = [int(v) for v in region]
    else:
        out["region"] = None

    templates = cfg.get("templates")
    out["templates"] = [
        t for t in templates
        if isinstance(t, dict) and isinstance(t.get("path"), str) and t["path"]
    ] if isinstance(templates, list) else []

    color = cfg.get("color_detection")
    color = color if isinstance(color, dict) else {}
    out["color_detection"] = {
        k: int(color[k]) if _is_num(color.get(k)) and 0 <= color[k] <= mx else d["color_detection"][k]
        for k, mx in _COLOR_MAX.items()
    }

    hotkeys = cfg.get("hotkeys")
    hotkeys = hotkeys if isinstance(hotkeys, dict) else {}
    out["hotkeys"] = {
        k: hotkeys[k] if isinstance(hotkeys.get(k), str) and hotkeys[k].strip() else default
        for k, default in d["hotkeys"].items()
    }
    return out


def load_config() -> dict:
    """Load configuration from JSON file. Returns defaults if file missing."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Merge with defaults so every key exists, then drop bad values
                return sanitize_config(_deep_merge(DEFAULT_CONFIG, data))
            print("[Config] settings.json is not an object; using defaults")
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Config] Failed to load config: {e}")
    return copy.deepcopy(DEFAULT_CONFIG)


def _deep_merge(defaults: dict, data: dict) -> dict:
    """Recursively overlay `data` on a deep copy of `defaults`."""
    merged = copy.deepcopy(defaults)
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def save_config(config: dict) -> bool:
    """Save configuration to JSON file."""
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return True
    except IOError as e:
        print(f"[Config] Failed to save config: {e}")
        return False
