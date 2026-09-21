"""
gui/settings_frame.py — Settings sidebar (scrollable) with redesigned compact layout
"""

from __future__ import annotations
import ctypes
from ctypes import wintypes
import tkinter as tk
import customtkinter as ctk
from typing import Callable
from pathlib import Path
from PIL import Image, ImageOps
from utils.icon_loader import load_svg_icon


class SettingsFrame(ctk.CTkScrollableFrame):
    """Scrollable left-side settings panel with card-style sections."""

    MODES       = ["Template Matching", "Color Detection"]
    INTERVALS   = ["10 ms", "20 ms", "50 ms", "100 ms", "200 ms"]
    CLICK_MODES = ["sendinput", "normal"]

    # ── Colors ────────────────────────────────────────────────────────
    C_CARD   = "#1F2937"
    C_BORDER = "#374151"
    C_BLUE   = "#2563EB"
    C_GREEN  = "#16A34A"
    C_AMBER  = "#D97706"
    C_PURPLE = "#7C3AED"
    C_RED    = "#DC2626"
    C_DIM    = "#6B7280"

    def __init__(self, master, on_mode_change=None, on_confidence_change=None,
                 on_delay_change=None, on_interval_change=None,
                 on_load_template=None, on_snip_template=None, on_clear_templates=None,
                 on_start=None, on_stop=None, on_pause=None, **kwargs):
        super().__init__(master, **kwargs)
        self._cbs = {
            "mode": on_mode_change, "confidence": on_confidence_change,
            "delay": on_delay_change, "interval": on_interval_change,
            "click_mode": None,
            "load": on_load_template, "snip": on_snip_template, "clear_templates": on_clear_templates,
            "start": on_start, "stop": on_stop, "pause": on_pause,
        }
        
        # Load Icons
        self._icons = {
            "search": load_svg_icon("assets/icons/search.svg", (14, 14)),
            "sliders": load_svg_icon("assets/icons/sliders-horizontal.svg", (14, 14)),
            "mouse": load_svg_icon("assets/icons/mouse-pointer-click.svg", (14, 14)),
            "folder": load_svg_icon("assets/icons/folder.svg", (14, 14)),
            "folder-open": load_svg_icon("assets/icons/folder-open.svg", (14, 14)),
            "scissors": load_svg_icon("assets/icons/scissors.svg", (14, 14)),
            "trash": load_svg_icon("assets/icons/trash-2.svg", (14, 14)),
        }
        
        self._build()

    # ── Build ──────────────────────────────────────────────────────────

    def _build(self):
        self._build_detection_section()
        self._build_thresholds_section()
        self._build_click_section()
        self._build_files_section()
        self._build_legend()

    def _build_detection_section(self):
        self._card_header("Detection", "#60A5FA", icon=self._icons.get("search"))

        card = self._card()
        self._sec_label(card, "Mode")
        self._mode_var = tk.StringVar(value=self.MODES[0])
        self._mode_menu = ctk.CTkOptionMenu(
            card, variable=self._mode_var, values=self.MODES,
            command=lambda v: self._cb("mode", v),
            fg_color="#1F2937", button_color="#2563EB", button_hover_color="#1D4ED8",
            dropdown_fg_color="#1F2937", dropdown_hover_color="#374151"
        )
        self._mode_menu.pack(padx=10, pady=(0, 10), fill="x")

        self._sec_label(card, "Interval")
        self._interval_var = tk.StringVar(value="50 ms")
        ctk.CTkOptionMenu(card, values=self.INTERVALS, variable=self._interval_var,
                          command=lambda v: self._cb("interval", int(v.replace(" ms", ""))),
                          fg_color="#0D1117", button_color=self.C_PURPLE,
                          button_hover_color="#6D28D9",
                          font=ctk.CTkFont("Segoe UI", 12),
                          height=30, corner_radius=6,
                          ).pack(padx=10, pady=(0, 10), fill="x")

    def _build_thresholds_section(self):
        self._card_header("Thresholds", "#34D399", icon=self._icons.get("sliders"))

        card = self._card()

        # Confidence
        row = self._inline_row(card)
        self._sec_label(row, "Confidence", expand=True)
        self._conf_val = ctk.CTkLabel(row, text="85%",
                                       font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                                       text_color="#60A5FA", width=40)
        self._conf_val.pack(side="right")
        self._conf_slider = ctk.CTkSlider(card, from_=50, to=100, number_of_steps=50,
                                           command=self._on_confidence,
                                           progress_color=self.C_BLUE,
                                           button_color="#60A5FA",
                                           button_hover_color="#93C5FD", height=16)
        self._conf_slider.set(85)
        self._conf_slider.pack(padx=10, pady=(0, 8), fill="x")

        # Click Delay
        row2 = self._inline_row(card)
        self._sec_label(row2, "Click Delay", expand=True)
        self._delay_val = ctk.CTkLabel(row2, text="0.30 s",
                                        font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                                        text_color="#34D399", width=50)
        self._delay_val.pack(side="right")
        self._delay_slider = ctk.CTkSlider(card, from_=5, to=200, number_of_steps=195,
                                            command=self._on_delay,
                                            progress_color=self.C_GREEN,
                                            button_color="#34D399",
                                            button_hover_color="#6EE7B7", height=16)
        self._delay_slider.set(30)
        self._delay_slider.pack(padx=10, pady=(0, 10), fill="x")

    def _build_click_section(self):
        self._card_header("Clicking", "#FBBF24", icon=self._icons.get("mouse"))

        card = self._card()
        self._click_mode_var = tk.StringVar(value="sendinput")
        ctk.CTkOptionMenu(card, values=self.CLICK_MODES,
                          variable=self._click_mode_var,
                          command=self._on_click_mode,
                          fg_color="#0D1117", button_color=self.C_RED,
                          button_hover_color="#B91C1C",
                          font=ctk.CTkFont("Segoe UI", 12),
                          height=30, corner_radius=6,
                          ).pack(padx=10, pady=(10, 6), fill="x")

        self._click_mode_desc = ctk.CTkLabel(card,
                                              text="⚡ SendInput — ต้องการ Focus",
                                              font=ctk.CTkFont("Segoe UI", 10),
                                              text_color=self.C_DIM, wraplength=200,
                                              justify="left")
        self._click_mode_desc.pack(padx=10, pady=(0, 6), fill="x")

    def _build_files_section(self):
        self._card_header("Targets", "#A78BFA", icon=self._icons.get("folder"))
        card = self._card()

        # Multi-Target Mode
        self._sec_label(card, "Target Mode")
        self._target_mode_var = tk.StringVar(value="Sequential")
        ctk.CTkOptionMenu(card, values=["Sequential", "First Found"],
                          variable=self._target_mode_var,
                          fg_color="#0D1117", button_color="#4B5563",
                          button_hover_color="#6B7280",
                          font=ctk.CTkFont("Segoe UI", 12),
                          height=30, corner_radius=6,
                          ).pack(padx=10, pady=(0, 10), fill="x")

        # Buttons Row: Load + Snip + Clear
        tmpl_row = ctk.CTkFrame(card, fg_color="transparent")
        tmpl_row.pack(padx=10, pady=(0, 8), fill="x")
        tmpl_row.grid_columnconfigure((0, 1, 2), weight=1)

        self._load_btn = ctk.CTkButton(tmpl_row, text=" Load", image=self._icons.get("folder-open"),
                                        fg_color="#0D1117", hover_color="#1A2233",
                                        border_color=self.C_BLUE, border_width=1,
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        height=28, corner_radius=6,
                                        command=lambda: self._cb("load"))
        self._load_btn.grid(row=0, column=0, padx=(0, 2), sticky="ew")

        self._snip_btn = ctk.CTkButton(tmpl_row, text=" Snip", image=self._icons.get("scissors"),
                                        fg_color="#0D1117", hover_color="#1A2233",
                                        border_color=self.C_BLUE, border_width=1,
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        height=28, corner_radius=6,
                                        command=lambda: self._cb("snip"))
        self._snip_btn.grid(row=0, column=1, padx=(2, 2), sticky="ew")

        self._clear_btn = ctk.CTkButton(tmpl_row, text=" Clear", image=self._icons.get("trash"),
                                        fg_color="#0D1117", hover_color="#450a0a",
                                        border_color=self.C_RED, border_width=1,
                                        font=ctk.CTkFont("Segoe UI", 11),
                                        height=28, corner_radius=6,
                                        command=lambda: self._cb("clear_templates"))
        self._clear_btn.grid(row=0, column=2, padx=(2, 0), sticky="ew")

        # List area
        self._tmpl_listbox = ctk.CTkTextbox(card, fg_color="#0D1117", corner_radius=6,
                                            border_color=self.C_BORDER, border_width=1,
                                            height=80, text_color=self.C_DIM,
                                            font=ctk.CTkFont("Consolas", 10))
        self._tmpl_listbox.pack(padx=10, pady=(0, 10), fill="x")
        self._tmpl_listbox.insert("1.0", "No templates loaded")
        self._tmpl_listbox.configure(state="disabled")

    def _build_legend(self):
        legend = ctk.CTkFrame(self, fg_color="#0D1117", corner_radius=8)
        legend.pack(padx=10, pady=(0, 10), fill="x")
        ctk.CTkLabel(legend,
                     text="F6 Start  •  F7 Stop  •  F8 Pause\nF10 Snip Template",
                     font=ctk.CTkFont("Segoe UI", 10),
                     text_color="#374151").pack(pady=6)

    # ── Small helpers ──────────────────────────────────────────────────

    def _card_header(self, text: str, color: str, icon=None):
        f = ctk.CTkFrame(self, fg_color="transparent", height=28)
        f.pack(padx=10, pady=(12, 2), fill="x")
        f.pack_propagate(False)
        # Accent bar
        bar = ctk.CTkFrame(f, fg_color=color, width=3, corner_radius=2)
        bar.pack(side="left", fill="y", padx=(0, 8))
        
        if icon:
            ctk.CTkLabel(f, text="", image=icon).pack(side="left", padx=(0, 6))
            
        ctk.CTkLabel(f, text=text,
                     font=ctk.CTkFont("Segoe UI", 11, weight="bold"),
                     text_color=color).pack(side="left", anchor="w")

    def _card(self) -> ctk.CTkFrame:
        card = ctk.CTkFrame(self, fg_color=self.C_CARD, corner_radius=10,
                             border_color=self.C_BORDER, border_width=1)
        card.pack(padx=10, pady=(0, 4), fill="x")
        return card

    def _sec_label(self, parent, text: str, expand=False):
        lbl = ctk.CTkLabel(parent, text=text,
                           font=ctk.CTkFont("Segoe UI", 11),
                           text_color=self.C_DIM, anchor="w")
        if expand:
            lbl.pack(side="left", padx=10, pady=(6, 0), fill="x", expand=True)
        else:
            lbl.pack(padx=10, pady=(6, 2), anchor="w")

    def _inline_row(self, parent) -> ctk.CTkFrame:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(padx=0, pady=(4, 0), fill="x")
        return row

    def _cb(self, key: str, *args):
        fn = self._cbs.get(key)
        if fn:
            fn(*args) if args else fn()

    # ── Internal callbacks ─────────────────────────────────────────────

    def _on_confidence(self, v: float):
        self._conf_val.configure(text=f"{int(v)}%")
        self._cb("confidence", v / 100.0)

    def _on_delay(self, v: float):
        self._delay_val.configure(text=f"{v/100.0:.2f} s")
        self._cb("delay", v / 100.0)

    _CLICK_DESC = {
        "sendinput":    "⚡ SendInput — ต้องการ Focus",
        "normal":       "🐢 Normal PyAutoGUI — ช้าสุด",
    }

    def _on_click_mode(self, v: str):
        self._click_mode_desc.configure(text=self._CLICK_DESC.get(v, ""))
        fn = self._cbs.get("click_mode")
        if fn:
            fn(v)

    # ── External API ───────────────────────────────────────────────────

    def get_mode(self) -> str:
        return self._mode_var.get()

    def get_overlay_enabled(self) -> bool:
        return False

    def get_confidence(self) -> float:
        return self._conf_slider.get() / 100.0

    def get_delay(self) -> float:
        return self._delay_slider.get() / 100.0

    def get_click_mode(self) -> str:
        return self._click_mode_var.get()

    def get_target_mode(self) -> str:
        return self._target_mode_var.get()

    def set_template_list(self, templates: list[dict]):
        self._tmpl_listbox.configure(state="normal")
        self._tmpl_listbox.delete("1.0", "end")
        
        if not templates:
            self._tmpl_listbox.insert("1.0", "No templates loaded")
        else:
            lines = []
            for i, tmpl in enumerate(templates):
                p = Path(tmpl["path"])
                delay_sec = tmpl.get("delay", 0) / 1000.0
                lines.append(f"{i+1}. {p.name} [{delay_sec:.2f}s]")
            self._tmpl_listbox.insert("1.0", "\n".join(lines))
            
        self._tmpl_listbox.configure(state="disabled")
