# PixelClick — Auto Click Detector

A Windows application that watches the screen for a target (an image or a color) and clicks it automatically.

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

For development (adds pytest):

```bash
pip install -r requirements-dev.txt
pytest tests
```

## Build a Windows .exe

```bash
pip install -r requirements-dev.txt
python build_exe.py
```

This produces a single file, `dist/PixelClick.exe`, that runs without Python installed. On first run it creates `config/`, `data/` (snipped images) and `logs/` next to itself, so keep it in a folder you can write to (not `C:\Program Files`).

## Hotkeys (work even when the window is not focused)

| Key | Action |
|-----|--------|
| `F6` | Start |
| `F7` | Stop |
| `F8` | Pause / Resume |
| `F9` | Select the area to scan |
| `F10` | Snip a target image from the screen |

Keys can be changed under `hotkeys` in `config/settings.json`. An invalid key name is reported in the status bar; the other hotkeys keep working.

## How to Use

The left panel is laid out in the order you set things up:

1. **What to click**
   - **Image**: add a picture of the target (**Add image**) or snip it straight from the screen (**Snip screen**, F10).
     - Each image has its own **delay before click** (0–10 s). After the image is found, PixelClick waits that long, checks the screen again, and clicks where the target is *now*. If it has gone, nothing is clicked.
     - With several images, choose **In sequence** (1, then 2, then 3, then over again) or **First match**.
     - Images can be added, removed or re-timed while running.
   - **Color**: pick a preset (Red, Green, Blue, Yellow) or fine-tune the HSV range. Clicks the largest area of that color.
2. **Where to look**: whole screen, or **Select area** (F9). A smaller area is faster and avoids clicking look-alikes.
3. **How to click**
   - **Match strictness** (image mode): higher means fewer wrong clicks, but the target may be missed.
   - **Wait between clicks**: the minimum time between any two clicks.
   - **Look for the target every**: how often the screen is scanned.
   - **Highlight target on screen**: draws a click-through box over the detected target. The box is hidden from screen capture, so it never affects detection.
   - **Advanced → Click method**: `sendinput` (fastest) or `normal` (PyAutoGUI). Both need the target window in focus.
4. Press **Start** (F6). It is disabled, with the reason shown, until there is something to look for.

**Compact view** replaces the window with a small always-on-top bar (status, click count, Start/Stop) that you can drag anywhere.

Settings, the image list with each image's delay, and the scan area are saved when you close the app.

## Safety

- **Emergency stop**: move the mouse to the top-left corner of the screen. This also works during a delay before click.
- **Wait between clicks** prevents clicking too fast. Clicking is also capped at 10 clicks per second (`max_clicks_per_second` in the config).
- **Re-check after delay**: a click never lands where the target used to be.
- **Match strictness**: no click if the match is below the threshold.

## Project Structure

```
PixelClick/
├── main.py                 # Entry point (sets DPI awareness, opens the window)
├── detection_worker.py     # Background thread: capture -> detect -> [wait -> re-check] -> click
├── requirements.txt / requirements-dev.txt
│
├── gui/
│   ├── theme.py            # Design tokens (colors, radii, fonts) and their rules
│   ├── main_window.py      # Main window, controls, hotkeys, persistence
│   ├── settings_frame.py   # Left setup panel (steps 1-3)
│   ├── preview_frame.py    # Live preview
│   ├── region_selector.py  # Drag-to-select overlay (area and snip)
│   ├── mini_hud.py         # Compact always-on-top bar
│   └── overlay.py          # Click-through target highlight
│
├── capture/
│   └── screen_capture.py   # MSS capture, one instance per thread
│
├── detection/
│   ├── base_detector.py    # DetectionResult + abstract base
│   ├── template_match.py   # OpenCV template matching
│   ├── multi_template.py   # Several images: sequence / first match, per-image delay
│   └── color_detector.py   # HSV color detection
│
├── mouse/
│   └── click_controller.py # Clicking, rate limit, FailSafe
│
├── utils/
│   ├── config.py           # JSON config load/save and migration
│   ├── mailbox.py          # Latest-only hand-off from worker thread to UI
│   ├── icon_loader.py      # SVG icon loader
│   └── logger.py           # Rotating log file
│
├── tests/                  # pytest suite
└── config/
    └── settings.json       # User settings
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| GUI | CustomTkinter (dark mode) |
| Screen Capture | MSS |
| Image Processing | OpenCV |
| Mouse Control | ctypes SendInput / PyAutoGUI |
| Global Hotkeys | keyboard |
| Config | JSON |
| Tests | pytest |
