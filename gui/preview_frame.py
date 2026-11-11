"""
gui/preview_frame.py — Live preview of what the detector is seeing.
The canvas fills the available space and scales the frame to fit.
"""

from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np
import cv2

from gui import theme as T

_CANVAS_BG = "#0A0D12"


class PreviewFrame(ctk.CTkFrame):

    IDLE_TEXT = "Preview appears here once you press Start."

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._photo: ImageTk.PhotoImage | None = None
        self._has_frame = False
        self._build_ui()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=T.PAD, pady=(T.PAD - 2, 8))
        ctk.CTkLabel(header, text="Preview", font=T.font(13, True),
                     text_color=T.TEXT).pack(side="left")
        self._state = ctk.CTkLabel(header, text="Not running", font=T.font(12),
                                   text_color=T.DIM)
        self._state.pack(side="right")

        wrap = ctk.CTkFrame(self, fg_color=_CANVAS_BG, corner_radius=T.R_CTRL)
        wrap.pack(fill="both", expand=True, padx=T.PAD, pady=(0, T.PAD))
        self._canvas = tk.Canvas(wrap, bg=_CANVAS_BG, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True, padx=2, pady=2)
        self._canvas.bind("<Configure>", lambda e: self._draw_placeholder())
        self._draw_placeholder()

    def _draw_placeholder(self):
        if self._has_frame:
            return
        self._canvas.delete("all")
        w, h = self._canvas.winfo_width(), self._canvas.winfo_height()
        self._canvas.create_text(w // 2, h // 2, text=self.IDLE_TEXT,
                                 fill=T.DIM, font=("Segoe UI", 12))

    def update_frame(self, frame: np.ndarray | None, found: bool,
                     x: int, y: int, confidence: float):
        """Update preview. Must be called from the main (Tk) thread."""
        if frame is None:
            self.clear()
            return

        self._has_frame = True
        self._state.configure(text="Found" if found else "Searching",
                              text_color=T.OK if found else T.MUTED)

        cw = max(100, self._canvas.winfo_width())
        ch = max(100, self._canvas.winfo_height())
        h, w = frame.shape[:2]
        scale = min(cw / w, ch / h)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
        self._canvas.delete("all")
        self._canvas.create_image(cw // 2, ch // 2, anchor="center", image=self._photo)

    def clear(self):
        self._has_frame = False
        self._photo = None
        self._state.configure(text="Not running", text_color=T.DIM)
        self._draw_placeholder()
