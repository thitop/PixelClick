"""
utils/config.py — Configuration manager for Auto Click Detector
Loads and saves settings from/to config/settings.json
"""

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
        "select_region": "f9"
    },
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


def load_config() -> dict:
    """Load configuration from JSON file. Returns defaults if file missing."""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
    except (json.JSONDecodeError, IOError) as e:
        print(f"[Config] Failed to load config: {e}")
    return DEFAULT_CONFIG.copy()


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
