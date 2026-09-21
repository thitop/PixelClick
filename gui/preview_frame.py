"""
gui/preview_frame.py — Live detection preview panel (redesigned)
"""

from __future__ import annotations
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk
import numpy as np
import cv2


class PreviewFrame(ctk.CTkFrame):
    """Live annotated-frame preview with detection overlay info."""

    PREVIEW_W = 480
    PREVIEW_H = 290

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._photo: ImageTk.PhotoImage | None = None
        self._build_ui()

    def _build_ui(self):
        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(header, text="🎯  Detection Preview",
                     font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
                     text_color="#A0C4FF").pack(side="left")

        self._live_badge = ctk.CTkLabel(header, text="● IDLE",
                                         font=ctk.CTkFont("Segoe UI", 10, weight="bold"),
                                         text_color="#4B5563")
        self._live_badge.pack(side="right")

        # Canvas
        canvas_container = ctk.CTkFrame(self, fg_color="#0A0F14", corner_radius=10,
                                         border_color="#21262D", border_width=1)
        canvas_container.pack(padx=14, pady=(0, 8), fill="both", expand=True)

        self._canvas = tk.Canvas(canvas_container,
                                  width=self.PREVIEW_W, height=self.PREVIEW_H,
                                  bg="#0A0F14", highlightthickness=0)
        self._canvas.pack(padx=2, pady=2)

        self._placeholder = self._canvas.create_text(
            self.PREVIEW_W // 2, self.PREVIEW_H // 2,
            text="No capture running",
            fill="#2D3748", font=("Segoe UI", 13))

        # Info bar
        info_bar = ctk.CTkFrame(self, fg_color="#0D1117", corner_radius=8)
        info_bar.pack(padx=14, pady=(0, 10), fill="x")

        self._pos_var  = tk.StringVar(value="Position:  —")
        self._conf_var = tk.StringVar(value="Confidence:  —")

        ctk.CTkLabel(info_bar, textvariable=self._pos_var,
                     font=ctk.CTkFont("Segoe UI Mono", 11),
                     text_color="#60A5FA").pack(side="left", padx=12, pady=6)

        ctk.CTkLabel(info_bar, textvariable=self._conf_var,
                     font=ctk.CTkFont("Segoe UI Mono", 11),
                     text_color="#34D399").pack(side="right", padx=12, pady=6)

    def update_frame(self, frame: np.ndarray | None, found: bool,
                     x: int, y: int, confidence: float):
        """Update preview. Must be called from the main (Tk) thread."""
        # Update live badge
        if frame is not None:
            if found:
                self._live_badge.configure(text="● FOUND", text_color="#22C55E")
            else:
                self._live_badge.configure(text="● SCANNING", text_color="#F59E0B")
        else:
            self._live_badge.configure(text="● IDLE", text_color="#4B5563")

        if frame is None:
            self._canvas.itemconfigure(self._placeholder, state="normal")
            self._pos_var.set("Position:  —")
            self._conf_var.set("Confidence:  —")
            return

        self._canvas.itemconfigure(self._placeholder, state="hidden")

        h, w = frame.shape[:2]
        scale = min(self.PREVIEW_W / w, self.PREVIEW_H / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_AREA)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        canvas_img = Image.new("RGB", (self.PREVIEW_W, self.PREVIEW_H), (10, 15, 20))
        ox, oy = (self.PREVIEW_W - nw) // 2, (self.PREVIEW_H - nh) // 2
        canvas_img.paste(Image.fromarray(rgb), (ox, oy))

        self._photo = ImageTk.PhotoImage(canvas_img)
        self._canvas.create_image(0, 0, anchor="nw", image=self._photo)

        # Info bar
        if found:
            self._pos_var.set(f"Position:  X={x}  Y={y}")
            self._conf_var.set(f"Confidence:  {confidence:.1%}")
        else:
            self._pos_var.set("Position:  —")
            self._conf_var.set(f"Confidence:  {confidence:.1%}" if confidence > 0 else "Confidence:  —")

    def clear(self):
        self._canvas.delete("all")
        self._placeholder = self._canvas.create_text(
            self.PREVIEW_W // 2, self.PREVIEW_H // 2,
            text="No capture running", fill="#2D3748", font=("Segoe UI", 13))
        self._live_badge.configure(text="● IDLE", text_color="#4B5563")
        self._pos_var.set("Position:  —")
        self._conf_var.set("Confidence:  —")
