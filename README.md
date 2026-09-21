# PixelClick — Auto Click Detector

A Windows application for screen capturing, detecting specific targets, and automatically moving the mouse to click on the detected targets.

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

## Hotkeys (Works even when the window is not focused)

| Key | Action |
|-----|--------|
| `F6` | Start detection |
| `F7` | Stop detection |
| `F8` | Pause / Resume |
| `F9` | Select capture region |

## How to Use

1. **Load Template** — Load the target image you want to search for (PNG/JPG)
2. **Select Area** — Drag and select the screen area to scan (Not selected = Full screen)
3. **Adjust Confidence** — The minimum accuracy value before clicking (default 85%)
4. **Adjust Click Delay** — The cooldown period between clicks
5. **START** — Start the automatic detection and clicking process

## Safety Features

- **PyAutoGUI Failsafe** — Move the mouse to the top-left corner for an emergency stop
- **Cooldown Protection** — Prevents repetitive clicking that is too fast
- **Max Click Rate** — Limited to a maximum of 10 clicks/second
- **Confidence Threshold** — Does not click if confidence is below the set threshold

## Project Structure

```
PixelClick/
├── main.py                 # Entry point
├── detection_worker.py     # Background worker thread
├── requirements.txt
│
├── gui/
│   ├── main_window.py      # Main window
│   ├── settings_frame.py   # Settings panel
│   ├── preview_frame.py    # Live preview
│   ├── region_selector.py  # Drag-select region overlay
│   ├── mini_hud.py         # Mini floating HUD
│   └── overlay.py          # Click-through overlay window
│
├── capture/
│   └── screen_capture.py   # MSS screen capture
│
├── detection/
│   ├── base_detector.py    # Abstract base
│   ├── template_match.py   # OpenCV template matching
│   └── color_detector.py   # HSV color detection
│
├── mouse/
│   └── click_controller.py # PyAutoGUI mouse control
│
├── utils/
│   ├── config.py           # JSON config manager
│   ├── icon_loader.py      # Icon loader utility
│   └── logger.py           # Logging
│
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
| Mouse Control | PyAutoGUI |
| Global Hotkeys | keyboard |
| Config | JSON |
