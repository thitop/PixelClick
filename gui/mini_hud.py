"""
gui/mini_hud.py — Compact always-on-top controller.

One row: drag grip · status (+ clicks / hotkeys) · Start/Stop · expand.
Start and Stop share one button because only one of them is ever valid.
"""

import tkinter as tk
import customtkinter as ctk

from gui import theme as T


class MiniHUD(ctk.CTkToplevel):
    W, H = 300, 60

    def __init__(self, master, on_start, on_stop, on_expand, icons,
                 hotkeys: dict | None = None, **kwargs):
        super().__init__(master, **kwargs)

        self.title("PixelClick HUD")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.96)
        self.configure(fg_color=T.BG)

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_expand = on_expand
        self._icons = icons
        hk = hotkeys or {}
        self._start_key = hk.get("start", "f6").upper()
        self._stop_key = hk.get("stop", "f7").upper()
        self._running = False
        self._placed = False
        self._drag = (0, 0)

        self._build_ui()
        self.withdraw()
        self._is_showing = False

    # ── Build ──────────────────────────────────────────────────────────

    def _build_ui(self):
        bar = ctk.CTkFrame(self, fg_color=T.SURFACE, corner_radius=T.R_PANEL,
                           border_color=T.BORDER, border_width=1)
        bar.pack(fill="both", expand=True, padx=1, pady=1)
        bar.grid_columnconfigure(1, weight=1)
        bar.grid_rowconfigure(0, weight=1)

        # Drag grip (six dots) — also tells the user the HUD can be moved
        grip = tk.Canvas(bar, width=14, height=24, bg=T.SURFACE,
                         highlightthickness=0, cursor="fleur")
        for cx in (4, 10):
            for cy in (5, 12, 19):
                grip.create_oval(cx - 1, cy - 1, cx + 1, cy + 1, fill=T.DIM, outline="")
        grip.grid(row=0, column=0, padx=(10, 4))

        text = ctk.CTkFrame(bar, fg_color="transparent")
        text.grid(row=0, column=1, sticky="w")
        status_row = ctk.CTkFrame(text, fg_color="transparent")
        status_row.pack(anchor="w")
        self._dot = ctk.CTkLabel(status_row, text="●", font=T.font(11),
                                 text_color=T.DIM, width=14, height=18)
        self._dot.pack(side="left")
        self._status = ctk.CTkLabel(status_row, text="Stopped", height=18,
                                    font=T.font(13, True), text_color=T.TEXT)
        self._status.pack(side="left")
        self._detail = ctk.CTkLabel(text, text="", font=T.font(11), height=16,
                                    text_color=T.DIM, anchor="w")
        self._detail.pack(anchor="w", padx=(14, 0))

        self._toggle = ctk.CTkButton(
            bar, text="", image=self._icons.get("play"), compound="left",
            width=96, height=34, corner_radius=T.R_CTRL, font=T.font(12, True),
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ON_ACCENT,
            command=self._toggle_pressed)
        self._toggle.grid(row=0, column=2, padx=(6, 6))

        self._expand = ctk.CTkButton(
            bar, text="", image=self._icons.get("maximize"), width=34, height=34,
            corner_radius=T.R_CTRL, fg_color=T.RAISED, hover_color=T.HOVER,
            command=self._on_expand)
        self._expand.grid(row=0, column=3, padx=(0, 10))

        for w in (bar, grip, text, status_row, self._dot, self._status, self._detail):
            w.bind("<Button-1>", self._start_drag)
            w.bind("<B1-Motion>", self._do_drag)

        self._render(running=False, paused=False, clicks=0)

    # ── Drag ───────────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _do_drag(self, event):
        self.geometry(f"+{event.x_root - self._drag[0]}+{event.y_root - self._drag[1]}")

    # ── State ──────────────────────────────────────────────────────────

    def _toggle_pressed(self):
        (self._on_stop if self._running else self._on_start)()

    def update_status(self, is_running: bool, clicks: int, paused: bool = False):
        self._running = is_running
        self._render(is_running, paused, clicks)

    def _render(self, running: bool, paused: bool, clicks: int):
        if running and paused:
            self._dot.configure(text_color=T.WARN)
            self._status.configure(text="Paused")
        elif running:
            self._dot.configure(text_color=T.OK)
            self._status.configure(text="Running")
        else:
            self._dot.configure(text_color=T.DIM)
            self._status.configure(text="Stopped")

        if running:
            self._detail.configure(text=f"{clicks} click{'s' if clicks != 1 else ''}")
            self._toggle.configure(
                text=f"Stop  {self._stop_key}", image=self._icons.get("square"),
                fg_color=T.RAISED, hover_color=T.HOVER, text_color=T.ERR)
        else:
            self._detail.configure(text="Ready")
            self._toggle.configure(
                text=f"Start  {self._start_key}", image=self._icons.get("play"),
                fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ON_ACCENT)

    # ── Show / hide ────────────────────────────────────────────────────

    def show(self):
        if not self._placed:  # first time: top-right, clear of the taskbar
            sw = self.winfo_screenwidth()
            self.geometry(f"{self.W}x{self.H}+{sw - self.W - 24}+24")
            self._placed = True
        self.deiconify()
        self.attributes("-topmost", True)
        self._is_showing = True

    def hide(self):
        self.withdraw()
        self._is_showing = False
