"""
build_exe.py — Build dist/PixelClick.exe with PyInstaller.

    pip install -r requirements-dev.txt
    python build_exe.py

The exe is a single file. On first run it creates, next to itself:
    config/settings.json   saved settings and image list
    data/                  snipped images
    logs/                  log files
"""

from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent


def main():
    PyInstaller.__main__.run([
        str(ROOT / "main.py"),
        "--name", "PixelClick",
        "--onefile",
        "--windowed",                                   # no console window
        "--icon", str(ROOT / "logo" / "PixelClick_logo.ico"),
        "--noconfirm", "--clean",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        # Bundled resources, read through utils.config.get_resource_path
        "--add-data", f"{ROOT / 'assets'};assets",
        "--add-data", f"{ROOT / 'logo'};logo",
        # CustomTkinter ships theme JSON/fonts it loads at runtime
        "--collect-data", "customtkinter",
        # SVG icons: reportlab picks its renderPM backend by name at runtime,
        # so PyInstaller cannot see it; pycairo carries native DLLs
        "--hidden-import", "rlPyCairo",
        "--collect-all", "rlPyCairo",
        "--collect-all", "cairo",
        "--collect-data", "reportlab",
    ])


if __name__ == "__main__":
    main()
