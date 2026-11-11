# PixelClick — Auto Click Detector

PixelClick watches your screen for a target — a picture you give it, or a color — and clicks it for you. It runs on Windows, works from global hotkeys while another app is in front, and has an emergency stop you can always reach.

![Python](https://img.shields.io/badge/python-3.11%2B-blue) ![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

---

## Quick start

```bash
pip install -r requirements.txt
python main.py
```

1. **What to click** — click **Snip screen** (or press `F10`) and drag a box around the button you want clicked.
2. **Where to look** — optional: **Select area** (`F9`) to scan only part of the screen.
3. Press **Start** (`F6`). Move the mouse to the **top-left corner** of the screen at any time to stop.

Prefer a single `.exe`? See [Build a Windows .exe](#build-a-windows-exe).

## Requirements

- Windows 10 version 2004 or newer (Windows 11 works)
- Python 3.11+ to run from source (not needed for the `.exe`)
- The app scans and clicks on the **primary monitor**

---

## Using PixelClick

The left panel is laid out in the order you set things up. The right side shows a live preview of what PixelClick sees, with the match boxed in green.

### 1. What to click

Choose **Image** or **Color** at the top.

**Image**
- **Add image** loads one or more PNG/JPG/BMP/WEBP files. **Snip screen** (`F10`) lets you drag a box on screen; the snip is saved in `data/` and added to the list.
- Each image in the list has a **delay before click** field (seconds, `0`–`10`, in 0.05 s steps). Type a value and press Enter (or click elsewhere). When the image is found, PixelClick waits that long, **looks again**, and clicks where the target is *now*. If it has disappeared, nothing is clicked. `0` clicks immediately.
- The **×** on a row removes that image.
- With two or more images, choose:
  - **In sequence** — click image 1, then 2, then 3, then start over. It only moves on after a successful click.
  - **First match** — click whichever image is found first.

**Color**
- Pick a preset (**Red**, **Green**, **Blue**, **Yellow**). The swatch beside it shows the color.
- **Fine-tune** opens hue, saturation and brightness sliders for a custom range.
- PixelClick clicks the center of the largest area of that color.

### 2. Where to look

- **Whole screen** by default.
- **Select area** (`F9`) — drag a box; only that part of the screen is scanned. **Reset** goes back to the whole screen.
- A smaller area scans faster and avoids clicking look-alikes elsewhere.
- Press `Esc` while selecting to cancel. A plain click (no drag) also cancels.

### 3. How to click

| Setting | Range | What it does |
|---|---|---|
| **Match strictness** | 50–100 % | Image mode only. Higher = fewer wrong clicks, but the target may be missed. |
| **Wait between clicks** | 0.05–2.00 s | Minimum time between any two clicks. |
| **Look for the target every** | 10–200 ms | How often the screen is scanned. |
| **Highlight target on screen** | on / off | Draws a blue box over the found target. Clicks pass through it, and it is hidden from screen capture, so it never affects detection. |
| **Advanced → Click method** | `sendinput` / `normal` | `sendinput` is fastest; `normal` uses PyAutoGUI. Both need the target window in focus. |

### Running

- **Start** (`F6`) is greyed out, with the reason shown above it, until there is something to look for (for example, no images added yet).
- **Pause / Resume** (`F8`) and **Stop** (`F7`).
- Changes apply **while running**: adding, removing or re-timing images, switching Image/Color, In sequence/First match, strictness, wait and scan speed. If you remove the last image (or switch to Image with no images), PixelClick stops by itself.
- **Snip screen** while running pauses clicking during the drag and resumes afterwards (unless you had paused it yourself). **Select area** is only available while stopped.

The stats under the preview:

| Stat | Meaning |
|---|---|
| **Target** | `Searching` · `Found` · `Waiting` (inside a delay before click) · `Paused` · `Error` (e.g. image larger than the scan area) |
| **Confidence** | How closely the best match fits |
| **Clicks** · **Elapsed** · **Scans/s** | Clicks this run, run time, scan rate |

### Compact view

**Compact view** (top right) swaps the window for a small always-on-top bar showing the status and click count, with one **Start/Stop** button and a button to return to the full window. Drag it anywhere by the dotted grip. Hotkeys keep working, and `F9`/`F10` hide the bar while you select so it is not in your snip.

---

## Hotkeys

They work even when PixelClick is not the active window.

| Key | Action |
|---|---|
| `F6` | Start |
| `F7` | Stop |
| `F8` | Pause / Resume |
| `F9` | Select the area to scan |
| `F10` | Snip a target image from the screen |

To change them, edit `hotkeys` in `config/settings.json` (keys: `start`, `stop`, `pause`, `select_region`, `snip_template`), using names like `"f2"` or `"ctrl+shift+s"`. The Start, Pause and Stop buttons and the compact bar show the keys you set (the Select area / Snip screen buttons always read F9 / F10). If a key name is invalid, the status bar says which one; the others keep working.

## Safety

- **Emergency stop: move the mouse to the top-left corner of the screen.** It is checked on every scan, including during a delay before click, and stops the run (status: *FailSafe triggered*). Only the top-left corner counts, so the Start button and Show desktop corners do not stop it by accident.
- **Wait between clicks** limits click speed. There is also a hard cap of 10 clicks per second (`max_clicks_per_second` in the settings file).
- **Re-check after a delay**: a delayed click never lands where the target *used to be*.
- **Match strictness**: no click unless the match is good enough.

---

## Settings and files

PixelClick keeps its files next to `main.py`, or next to `PixelClick.exe` when packaged:

| Path | Contents |
|---|---|
| `config/settings.json` | Your settings, image list (with each image's delay), scan area. Saved when you close the app; created with defaults if missing. |
| `data/` | Images saved by **Snip screen** |
| `logs/autoclick.log` | Log file (rotates at about 500 KB, keeps 3 old files) |

The settings file is safe to edit by hand. Values of the wrong type or out of range are replaced with defaults when the app starts, so a typo cannot stop it from opening. Images whose files no longer exist are skipped.

## Build a Windows .exe

```bash
pip install -r requirements-dev.txt
python build_exe.py
```

This creates a single file, `dist/PixelClick.exe`, that runs without Python. Put it in a folder you can write to (Desktop, Documents — not `C:\Program Files`), because it creates `config/`, `data/` and `logs/` beside itself.

The exe is not code-signed. The first time, Windows SmartScreen may warn you: choose **More info → Run anyway**. Some antivirus tools are suspicious of PyInstaller apps in general.

## Troubleshooting

| Problem | Try |
|---|---|
| It finds the target but clicks do nothing | Make sure the target window is focused. If the target app runs **as administrator**, run PixelClick as administrator too (Windows blocks input from normal apps into elevated ones; hotkeys are affected the same way). |
| It never finds the image | Snip again at the same zoom/scale the app is at now, lower **Match strictness** a little, or use **Select area** so the image is not larger than the scanned area. |
| It clicks the wrong thing | Raise **Match strictness**, use a more distinctive snip, or narrow the area with **Select area**. |
| The blue highlight box doesn't show over a game | Exclusive-fullscreen games can hide overlays; switch the game to borderless/windowed. Detection and clicking are unaffected. |
| Clicks land in the wrong place | PixelClick is DPI-aware and works on the primary monitor; move the target window to the primary monitor. |

---

## Development

```bash
pip install -r requirements-dev.txt
pytest tests
```

Some tests open real windows and are skipped automatically when no display is available.

### Project structure

```
PixelClick/
├── main.py                 # Entry point (sets DPI awareness, opens the window)
├── detection_worker.py     # Background thread: capture -> detect -> [wait -> re-check] -> click
├── build_exe.py            # Builds dist/PixelClick.exe with PyInstaller
├── requirements.txt / requirements-dev.txt
│
├── gui/
│   ├── theme.py            # Design tokens (colors, radii, fonts) and their rules
│   ├── main_window.py      # Main window, controls, hotkeys, saving/loading settings
│   ├── settings_frame.py   # Left setup panel (steps 1-3)
│   ├── preview_frame.py    # Live preview
│   ├── region_selector.py  # Drag-to-select overlay (area and snip)
│   ├── mini_hud.py         # Compact always-on-top bar
│   └── overlay.py          # Click-through target highlight
│
├── capture/
│   └── screen_capture.py   # MSS capture, one reusable instance per thread
│
├── detection/
│   ├── base_detector.py    # DetectionResult + abstract base
│   ├── template_match.py   # OpenCV template matching
│   ├── multi_template.py   # Several images: in sequence / first match, per-image delay
│   └── color_detector.py   # HSV color detection
│
├── mouse/
│   └── click_controller.py # Clicking, rate limit, emergency stop
│
├── utils/
│   ├── config.py           # Settings load/save, defaults, validation
│   ├── mailbox.py          # Latest-only hand-off from the worker thread to the UI
│   ├── icon_loader.py      # SVG icon loader
│   └── logger.py           # Rotating log file
│
├── assets/icons/           # SVG icons
├── logo/                   # App logo and .ico
└── tests/                  # pytest suite
```

### Tech stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| GUI | CustomTkinter |
| Screen capture | MSS |
| Image processing | OpenCV |
| Mouse control | Win32 SendInput (ctypes) / PyAutoGUI |
| Global hotkeys | keyboard |
| SVG icons | svglib + reportlab (cairo backend) |
| Packaging | PyInstaller |
| Tests | pytest |
