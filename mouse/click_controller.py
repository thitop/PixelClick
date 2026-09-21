"""
mouse/click_controller.py — Mouse control with multiple click modes.

Click Modes:
  "normal"       — PyAutoGUI SendInput (requires Roblox to be focused)
  "sendinput"    — ctypes SendInput directly (fastest, still needs focus)
  "directwindow" — PostMessage WM_LBUTTONDOWN to target window handle
                   (works WITHOUT focus — best for fullscreen games)
"""

from __future__ import annotations
import time
import ctypes
from ctypes import wintypes
import threading
import pyautogui
from utils.logger import get_logger

log = get_logger("mouse")

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.005  # Reduce pyautogui inter-call pause

# ── ctypes structures for SendInput ────────────────────────────────────────
MOUSEEVENTF_MOVE        = 0x0001
MOUSEEVENTF_LEFTDOWN    = 0x0002
MOUSEEVENTF_LEFTUP      = 0x0004
MOUSEEVENTF_ABSOLUTE    = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

INPUT_MOUSE = 0

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx",          ctypes.c_long),
        ("dy",          ctypes.c_long),
        ("mouseData",   ctypes.c_ulong),
        ("dwFlags",     ctypes.c_ulong),
        ("time",        ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("_input", _INPUT_UNION)]

# ── Win32 window-message constants ─────────────────────────────────────────
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP   = 0x0202
MK_LBUTTON     = 0x0001


def _send_input_click(x: int, y: int):
    """Move mouse and click using ctypes SendInput (no pyautogui overhead)."""
    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)
    abs_x = int(x * 65535 / screen_w)
    abs_y = int(y * 65535 / screen_h)

    inputs = (INPUT * 3)()

    # Move
    inputs[0].type = INPUT_MOUSE
    inputs[0]._input.mi.dx = abs_x
    inputs[0]._input.mi.dy = abs_y
    inputs[0]._input.mi.dwFlags = MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

    # Down
    inputs[1].type = INPUT_MOUSE
    inputs[1]._input.mi.dx = abs_x
    inputs[1]._input.mi.dy = abs_y
    inputs[1]._input.mi.dwFlags = MOUSEEVENTF_LEFTDOWN | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

    # Up
    inputs[2].type = INPUT_MOUSE
    inputs[2]._input.mi.dx = abs_x
    inputs[2]._input.mi.dy = abs_y
    inputs[2]._input.mi.dwFlags = MOUSEEVENTF_LEFTUP | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK

    ctypes.windll.user32.SendInput(3, inputs, ctypes.sizeof(INPUT))


class ClickController:
    """
    Thread-safe mouse controller.

    click_mode:
      "normal"       — PyAutoGUI (needs focus)
      "sendinput"    — ctypes SendInput (needs focus, faster)
    """

    MODES = ["normal", "sendinput"]

    def __init__(
        self,
        cooldown_ms: int = 300,
        max_clicks_per_second: int = 10,
        click_mode: str = "sendinput",
    ):
        self._lock = threading.Lock()
        self._last_click_time: float = 0.0
        self._cooldown_sec: float = cooldown_ms / 1000.0
        self._min_interval: float = 1.0 / max_clicks_per_second
        self._enabled: bool = True
        self.click_count: int = 0
        self.click_mode: str = click_mode

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def cooldown_ms(self) -> int:
        return int(self._cooldown_sec * 1000)

    @cooldown_ms.setter
    def cooldown_ms(self, value: int):
        self._cooldown_sec = max(0, value) / 1000.0

    @property
    def max_clicks_per_second(self) -> int:
        return int(1.0 / self._min_interval) if self._min_interval > 0 else 999

    @max_clicks_per_second.setter
    def max_clicks_per_second(self, value: int):
        self._min_interval = 1.0 / max(1, value)

    def enable(self):
        self._enabled = True

    def disable(self):
        self._enabled = False

    def reset_counter(self):
        self.click_count = 0

    # ── Movement ───────────────────────────────────────────────────────

    def move_to(self, x: int, y: int, duration: float = 0.03) -> bool:
        """Move mouse to absolute screen coordinates."""
        if not self._enabled:
            return False
        try:
            pyautogui.moveTo(x, y, duration=duration)
            return True
        except pyautogui.FailSafeException:
            log.warning("FailSafe triggered — mouse at corner.")
            self.disable()
            return False
        except Exception as e:
            log.error(f"move_to error: {e}")
            return False

    # ── Click ──────────────────────────────────────────────────────────

    def click(self, x: int | None = None, y: int | None = None, override_delay_ms: int | None = None) -> bool:
        """Click at (x, y), respecting cooldown / rate limiting."""
        if not self._enabled:
            return False

        now = time.monotonic()
        with self._lock:
            elapsed = now - self._last_click_time
            cooldown = self._cooldown_sec if override_delay_ms is None else override_delay_ms / 1000.0
            if elapsed < max(cooldown, self._min_interval):
                return False

            try:
                self._do_click(x, y)
                self._last_click_time = time.monotonic()
                self.click_count += 1
                log.debug(f"Clicked at ({x}, {y})  mode={self.click_mode}  total={self.click_count}")
                return True
            except Exception as e:
                log.error(f"click error: {e}")
                return False

    def _do_click(self, x: int | None, y: int | None):
        """Dispatch to the appropriate click implementation."""
        mode = self.click_mode

        if mode == "sendinput":
            if x is not None and y is not None:
                _send_input_click(x, y)
            else:
                px, py = pyautogui.position()
                _send_input_click(px, py)

        else:  # "normal"
            try:
                if x is not None and y is not None:
                    pyautogui.click(x, y)
                else:
                    pyautogui.click()
            except pyautogui.FailSafeException:
                log.warning("FailSafe triggered during click.")
                self.disable()

    def move_and_click(self, x: int, y: int, duration: float = 0.03, override_delay_ms: int | None = None) -> bool:
        """Helper to move mouse and then click immediately."""
        if self.move_to(x, y, duration):
            return self.click(x, y, override_delay_ms)
        return False

    def double_click(self, x: int, y: int) -> bool:
        if not self._enabled:
            return False
        self._do_click(x, y)
        time.sleep(0.05)
        self._do_click(x, y)
        self.click_count += 2
        return True

