"""
gui/overlay.py — Click-through highlight box drawn over the detected target.

Three Win32 properties make it safe to leave on while clicking:
  * WS_EX_TRANSPARENT  — mouse clicks pass through to the window below
  * WS_EX_NOACTIVATE   — showing it never steals focus from the game
  * display affinity   — excluded from screen capture, so the detector never
                         sees its own box (a blue box would otherwise be
                         matched / colour-detected as part of the scene)
"""

import ctypes
import tkinter as tk
import customtkinter as ctk

GWL_EXSTYLE          = -20
WS_EX_LAYERED        = 0x00080000
WS_EX_TRANSPARENT    = 0x00000020
WS_EX_TOOLWINDOW     = 0x00000080
WS_EX_NOACTIVATE     = 0x08000000
WDA_EXCLUDEFROMCAPTURE = 0x00000011


class OverlayWindow(ctk.CTkToplevel):
    def __init__(self, master, box_color="#2E86FF", **kwargs):
        super().__init__(master, **kwargs)
        self.title("PixelClick Overlay")
        self._box_color = box_color

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")

        self.overrideredirect(True)
        self.attributes("-transparentcolor", "black")
        self.attributes("-topmost", True)
        self.configure(fg_color="black")

        self._canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._rect = None

        self.update_idletasks()
        self._apply_win32_flags()

        self.withdraw()
        self._is_showing = False

    def _apply_win32_flags(self):
        user32 = ctypes.windll.user32
        hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(
            hwnd, GWL_EXSTYLE,
            style | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        # Windows 10 2004+; older builds simply ignore the call.
        self.capture_excluded = bool(
            user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE))

    def show(self):
        self.deiconify()
        self.attributes("-topmost", True)
        self._is_showing = True

    def hide(self):
        self.withdraw()
        self.clear_target()
        self._is_showing = False

    def clear_target(self):
        if self._rect:
            self._canvas.delete(self._rect)
            self._rect = None

    def update_target(self, found: bool, x: int, y: int, w: int, h: int):
        if not self._is_showing:
            return
        if not found or w <= 0 or h <= 0:
            self.clear_target()
            return
        if not self._rect:
            self._rect = self._canvas.create_rectangle(
                x, y, x + w, y + h, outline=self._box_color, width=3)
        else:
            self._canvas.coords(self._rect, x, y, x + w, y + h)
