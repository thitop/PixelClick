"""
gui/region_selector.py — Transparent overlay window for dragging a capture region.
Draws a red rectangle while the user drags, then calls the callback with (x, y, w, h).
"""

from __future__ import annotations
import tkinter as tk
from typing import Callable


class RegionSelector(tk.Toplevel):
    """
    Full-screen transparent window that lets the user drag-select a region.
    Calls on_select(x, y, width, height) when done.
    Calls on_cancel() if the user presses Escape.
    """

    def __init__(
        self,
        master,
        on_select: Callable[[int, int, int, int], None],
        on_cancel: Callable[[], None] | None = None,
    ):
        super().__init__(master)
        self._on_select = on_select
        self._on_cancel = on_cancel

        self._start_x = 0
        self._start_y = 0
        self._rect_id = None

        self._setup_window()
        self._canvas = tk.Canvas(
            self,
            cursor="crosshair",
            bg="black",
            highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._canvas.create_text(
            self.winfo_screenwidth() // 2,
            self.winfo_screenheight() // 2,
            text="Drag to select detection region • Press ESC to cancel",
            fill="white",
            font=("Segoe UI", 16),
        )

        self._canvas.bind("<ButtonPress-1>", self._on_press)
        self._canvas.bind("<B1-Motion>", self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Escape>", self._on_escape)

    def _setup_window(self):
        self.attributes("-fullscreen", True)
        self.attributes("-alpha", 0.35)
        self.attributes("-topmost", True)
        self.overrideredirect(True)
        self.lift()
        self.focus_force()

    def _on_press(self, event):
        self._start_x = event.x_root
        self._start_y = event.y_root
        if self._rect_id:
            self._canvas.delete(self._rect_id)
        self._rect_id = self._canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#FF4444", width=2,
        )

    def _on_drag(self, event):
        if self._rect_id:
            sx = self._start_x - self.winfo_x()
            sy = self._start_y - self.winfo_y()
            self._canvas.coords(self._rect_id, sx, sy, event.x, event.y)

    def _on_release(self, event):
        end_x = event.x_root
        end_y = event.y_root

        x = min(self._start_x, end_x)
        y = min(self._start_y, end_y)
        w = abs(end_x - self._start_x)
        h = abs(end_y - self._start_y)

        self.destroy()

        if w > 10 and h > 10:
            self._on_select(x, y, w, h)

    def _on_escape(self, event):
        self.destroy()
        if self._on_cancel:
            self._on_cancel()
