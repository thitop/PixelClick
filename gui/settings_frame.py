"""
gui/settings_frame.py — Setup panel.

Reads top to bottom as the order a person actually sets things up:
  1. What to click   (images, or a colour)
  2. Where to look   (whole screen, or a region)
  3. How to click    (strictness, pacing, advanced)
"""

from __future__ import annotations
import colorsys
import math
from pathlib import Path
import tkinter as tk
import customtkinter as ctk

from gui import theme as T
from utils.config import PRE_DELAY_MAX_MS
from utils.icon_loader import load_svg_icon


def parse_pre_delay(text: str) -> float | None:
    """Seconds typed into a row's field -> value snapped to 0.05 s, or None if
    it is not a number or lies outside 0..PRE_DELAY_MAX_MS."""
    try:
        v = float(text.strip())
    except ValueError:
        return None
    if not math.isfinite(v) or v < 0 or v > PRE_DELAY_MAX_MS / 1000:
        return None
    return round(round(v / 0.05) * 0.05, 2)


class SettingsFrame(ctk.CTkScrollableFrame):

    MODE_LABELS   = {"Image": "Template Matching", "Color": "Color Detection"}
    ORDER_LABELS  = {"In sequence": "Sequential", "First match": "First Found"}
    INTERVALS     = ["10 ms", "20 ms", "50 ms", "100 ms", "200 ms"]
    CLICK_MODES   = ["sendinput", "normal"]
    CLICK_DESC = {
        "sendinput": "Fastest. The target window must be in focus.",
        "normal":    "Slower, uses PyAutoGUI. The target window must be in focus.",
    }
    COLOR_FIELDS = [  # (config key, label, max)
        ("hue_min", "Hue min", 180), ("hue_max", "Hue max", 180),
        ("sat_min", "Saturation min", 255), ("sat_max", "Saturation max", 255),
        ("val_min", "Brightness min", 255), ("val_max", "Brightness max", 255),
    ]

    def __init__(self, master,
                 on_mode_change=None, on_confidence_change=None,
                 on_delay_change=None, on_interval_change=None,
                 on_click_mode_change=None,
                 on_load_template=None, on_snip_template=None,
                 on_clear_templates=None, on_remove_template=None,
                 on_template_delay_change=None, on_target_mode_change=None,
                 on_select_region=None, on_clear_region=None,
                 on_color_change=None, **kwargs):
        super().__init__(master, **kwargs)
        self._cbs = {
            "mode": on_mode_change, "confidence": on_confidence_change,
            "delay": on_delay_change, "interval": on_interval_change,
            "click_mode": on_click_mode_change,
            "load": on_load_template, "snip": on_snip_template,
            "clear_templates": on_clear_templates,
            "remove_template": on_remove_template,
            "template_delay": on_template_delay_change,
            "target_mode": on_target_mode_change,
            "select_region": on_select_region, "clear_region": on_clear_region,
            "color": on_color_change,
        }
        self._icons = {
            "folder": load_svg_icon("assets/icons/folder-open.svg", (14, 14)),
            "scissors": load_svg_icon("assets/icons/scissors.svg", (14, 14)),
            "maximize": load_svg_icon("assets/icons/maximize.svg", (14, 14)),
            "x": load_svg_icon("assets/icons/x.svg", (12, 12)),
        }
        self._build_target()
        self._build_area()
        self._build_tuning()
        self.set_mode("Template Matching")

    # ── Small building blocks ──────────────────────────────────────────

    def _section(self, number: int, title: str, first: bool = False) -> ctk.CTkFrame:
        if not first:
            ctk.CTkFrame(self, fg_color=T.BORDER, height=1).pack(
                fill="x", padx=T.PAD, pady=(T.PAD, 0))
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=T.PAD, pady=(T.PAD, 8))
        ctk.CTkLabel(head, text=str(number), width=20, height=20, corner_radius=10,
                     fg_color=T.RAISED, text_color=T.MUTED,
                     font=T.font(11, True)).pack(side="left")
        ctk.CTkLabel(head, text=title, font=T.font(13, True),
                     text_color=T.TEXT).pack(side="left", padx=(8, 0))
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="x", padx=T.PAD)
        return body

    def _button(self, parent, text, command, icon=None, **kw) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, image=icon, command=command, compound="left",
            fg_color=T.RAISED, hover_color=T.HOVER, text_color=T.TEXT,
            border_width=1, border_color=T.BORDER, corner_radius=T.R_CTRL,
            height=32, font=T.font(12), **kw)

    def _link(self, parent, text, command) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=command, width=0, height=22,
            fg_color="transparent", hover_color=T.HOVER, text_color=T.MUTED,
            corner_radius=T.R_CTRL, font=T.font(11))

    def _slider_row(self, parent, label, hint, lo, hi, steps, command):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 2))
        ctk.CTkLabel(row, text=label, font=T.font(12), text_color=T.TEXT,
                     anchor="w").pack(side="left")
        value = ctk.CTkLabel(row, text="", font=T.font(12, True), text_color=T.TEXT)
        value.pack(side="right")
        slider = ctk.CTkSlider(
            parent, from_=lo, to=hi, number_of_steps=steps, command=command,
            height=14, fg_color=T.BORDER, progress_color=T.ACCENT,
            button_color=T.ACCENT, button_hover_color=T.ACCENT_HOVER)
        slider.pack(fill="x", pady=(2, 0))
        if hint:
            ctk.CTkLabel(parent, text=hint, font=T.font(11), text_color=T.DIM,
                         anchor="w", wraplength=260, justify="left").pack(
                fill="x", pady=(2, 10))
        else:
            ctk.CTkFrame(parent, fg_color="transparent", height=8).pack()
        return slider, value

    def _menu(self, parent, values, variable, command) -> ctk.CTkOptionMenu:
        return ctk.CTkOptionMenu(
            parent, values=values, variable=variable, command=command,
            fg_color=T.RAISED, button_color=T.RAISED, button_hover_color=T.HOVER,
            dropdown_fg_color=T.RAISED, dropdown_hover_color=T.HOVER,
            text_color=T.TEXT, corner_radius=T.R_CTRL, height=32,
            font=T.font(12), dropdown_font=T.font(12))

    def _expander(self, parent, title: str):
        """Collapsed-by-default group. Returns (header button, body frame)."""
        body = ctk.CTkFrame(parent, fg_color="transparent")
        state = {"open": False}
        # A label (not a button) so the text sits flush with the column edge.
        btn = ctk.CTkLabel(
            parent, text=f"{title}  (show)", anchor="w", height=26,
            text_color=T.MUTED, font=T.font(11), cursor="hand2")

        def toggle(_e=None):
            state["open"] = not state["open"]
            if state["open"]:
                body.pack(fill="x", pady=(4, 0))
            else:
                body.pack_forget()
            btn.configure(text=f"{title}  ({'hide' if state['open'] else 'show'})")

        btn.bind("<Button-1>", toggle)
        btn.bind("<Enter>", lambda e: btn.configure(text_color=T.TEXT))
        btn.bind("<Leave>", lambda e: btn.configure(text_color=T.MUTED))
        btn.pack(fill="x")
        return btn, body

    def _cb(self, key: str, *args):
        fn = self._cbs.get(key)
        if fn:
            fn(*args)

    # ── 1. What to click ───────────────────────────────────────────────

    def _build_target(self):
        body = self._section(1, "What to click", first=True)

        self._mode_seg = ctk.CTkSegmentedButton(
            body, values=list(self.MODE_LABELS), command=self._on_mode_seg,
            fg_color=T.RAISED, selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER, unselected_color=T.RAISED,
            unselected_hover_color=T.HOVER, text_color=T.TEXT,
            corner_radius=T.R_CTRL, font=T.font(12), height=30)
        self._mode_seg.pack(fill="x")

        # Image mode
        self._image_box = ctk.CTkFrame(body, fg_color="transparent")
        self._tmpl_list = ctk.CTkFrame(self._image_box, fg_color=T.RAISED,
                                       corner_radius=T.R_CTRL)
        self._tmpl_list.pack(fill="x", pady=(10, 8))

        row = ctk.CTkFrame(self._image_box, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1), weight=1, uniform="a")
        self._button(row, "Add image", lambda: self._cb("load"),
                     self._icons["folder"]).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self._button(row, "Snip screen  F10", lambda: self._cb("snip"),
                     self._icons["scissors"]).grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._order_row = ctk.CTkFrame(self._image_box, fg_color="transparent")
        ctk.CTkLabel(self._order_row, text="With several images", font=T.font(12),
                     text_color=T.TEXT).pack(anchor="w", pady=(12, 4))
        self._order_seg = ctk.CTkSegmentedButton(
            self._order_row, values=list(self.ORDER_LABELS),
            fg_color=T.RAISED, selected_color=T.ACCENT,
            selected_hover_color=T.ACCENT_HOVER, unselected_color=T.RAISED,
            unselected_hover_color=T.HOVER, text_color=T.TEXT,
            corner_radius=T.R_CTRL, font=T.font(12), height=28)
        self._order_seg.set("In sequence")
        self._order_seg.pack(fill="x")
        self._order_hint = ctk.CTkLabel(
            self._order_row, text="", font=T.font(11), text_color=T.DIM,
            anchor="w", wraplength=260, justify="left")
        self._order_hint.pack(fill="x", pady=(4, 0))
        self._order_seg.configure(command=self._on_order)
        self._update_order_hint("In sequence")

        # Colour mode
        self._color_box = ctk.CTkFrame(body, fg_color="transparent")
        self._build_color(self._color_box)

        self.set_template_list([])

    def _on_order(self, label: str):
        self._update_order_hint(label)
        self._cb("target_mode", self.ORDER_LABELS[label])

    def _update_order_hint(self, label: str):
        self._order_hint.configure(text={
            "In sequence": "Clicks image 1, then 2, then 3, then starts over.",
            "First match": "Clicks whichever image appears first.",
        }[label])

    def _build_color(self, parent):
        from detection.color_detector import ColorDetector
        self._presets = {
            name: dict(zip(("hue_min", "sat_min", "val_min"), lo))
            | dict(zip(("hue_max", "sat_max", "val_max"), hi))
            for name, (lo, hi) in ColorDetector.PRESETS.items()
        }
        top = ctk.CTkFrame(parent, fg_color="transparent")
        top.pack(fill="x", pady=(10, 4))
        self._preset_var = tk.StringVar(value="Red")
        self._menu(top, list(self._presets) + ["Custom"], self._preset_var,
                   self._on_preset).pack(side="left", fill="x", expand=True)
        self._swatch = ctk.CTkFrame(top, width=32, height=32,
                                    corner_radius=T.R_CTRL, fg_color=T.RAISED)
        self._swatch.pack(side="left", padx=(8, 0))
        ctk.CTkLabel(parent, text="Finds the largest area of this color.",
                     font=T.font(11), text_color=T.DIM, anchor="w").pack(fill="x")

        _, fine = self._expander(parent, "Fine-tune")
        self._color_sliders: dict[str, ctk.CTkSlider] = {}
        self._color_vals: dict[str, ctk.CTkLabel] = {}
        for key, label, mx in self.COLOR_FIELDS:
            s, v = self._slider_row(fine, label, None, 0, mx, mx,
                                    lambda val, k=key: self._on_color_slider(k, val))
            self._color_sliders[key] = s
            self._color_vals[key] = v
        self.set_color_range(self._presets["Red"])

    # ── 2. Where to look ───────────────────────────────────────────────

    def _build_area(self):
        body = self._section(2, "Where to look")
        self._region_label = ctk.CTkLabel(
            body, text="Whole screen", font=T.font(12), text_color=T.TEXT, anchor="w")
        self._region_label.pack(fill="x", pady=(0, 8))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        row.grid_columnconfigure((0, 1), weight=1, uniform="b")
        self._button(row, "Select area  F9", lambda: self._cb("select_region"),
                     self._icons["maximize"]).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self._button(row, "Reset", lambda: self._cb("clear_region")
                     ).grid(row=0, column=1, padx=(4, 0), sticky="ew")
        ctk.CTkLabel(body, text="A smaller area is faster and avoids clicking look-alikes.",
                     font=T.font(11), text_color=T.DIM, anchor="w",
                     wraplength=260, justify="left").pack(fill="x", pady=(6, 0))

    # ── 3. How to click ────────────────────────────────────────────────

    def _build_tuning(self):
        body = self._section(3, "How to click")
        # Strictness only applies to image matching; hidden in Color mode.
        self._conf_box = ctk.CTkFrame(body, fg_color="transparent")
        self._conf_box.pack(fill="x")
        self._conf_slider, self._conf_val = self._slider_row(
            self._conf_box, "Match strictness",
            "Higher means fewer wrong clicks, but may miss the target.",
            50, 100, 50, self._on_confidence)
        self._delay_box = ctk.CTkFrame(body, fg_color="transparent")
        self._delay_box.pack(fill="x")
        self._delay_slider, self._delay_val = self._slider_row(
            self._delay_box, "Wait between clicks",
            "Minimum time between two clicks.", 5, 200, 195, self._on_delay)
        self.set_confidence(0.85)
        self.set_delay(0.30)

        ctk.CTkLabel(body, text="Look for the target every", font=T.font(12),
                     text_color=T.TEXT, anchor="w").pack(fill="x", pady=(8, 4))
        self._interval_var = tk.StringVar(value="50 ms")
        self._menu(body, self.INTERVALS, self._interval_var,
                   lambda v: self._cb("interval", int(v.replace(" ms", "")))
                   ).pack(fill="x", pady=(0, 12))

        self._overlay_var = tk.BooleanVar(value=True)
        ctk.CTkSwitch(
            body, text="Highlight target on screen", variable=self._overlay_var,
            font=T.font(12), text_color=T.TEXT, progress_color=T.ACCENT,
            fg_color=T.BORDER, button_color=T.TEXT, button_hover_color=T.TEXT,
        ).pack(anchor="w", pady=(0, 10))

        _, adv = self._expander(body, "Advanced")
        ctk.CTkLabel(adv, text="Click method", font=T.font(12), text_color=T.TEXT,
                     anchor="w").pack(fill="x", pady=(0, 4))
        self._click_mode_var = tk.StringVar(value="sendinput")
        self._menu(adv, self.CLICK_MODES, self._click_mode_var,
                   self._on_click_mode).pack(fill="x")
        self._click_desc = ctk.CTkLabel(
            adv, text=self.CLICK_DESC["sendinput"], font=T.font(11),
            text_color=T.DIM, anchor="w", wraplength=260, justify="left")
        self._click_desc.pack(fill="x", pady=(4, 0))
        ctk.CTkFrame(self, fg_color="transparent", height=T.PAD).pack()

    # ── Internal callbacks ─────────────────────────────────────────────

    def _on_mode_seg(self, label: str):
        self.set_mode(self.MODE_LABELS[label])
        self._cb("mode", self.MODE_LABELS[label])

    def _on_confidence(self, v: float):
        self._conf_val.configure(text=f"{int(v)}%")
        self._cb("confidence", v / 100.0)

    def _on_delay(self, v: float):
        self._delay_val.configure(text=f"{v / 100.0:.2f} s")
        self._cb("delay", v / 100.0)

    def _on_click_mode(self, v: str):
        self._click_desc.configure(text=self.CLICK_DESC.get(v, ""))
        self._cb("click_mode", v)

    def _on_preset(self, name: str):
        if name in self._presets:
            self.set_color_range(self._presets[name])
            self._cb("color", self.get_color_range())

    def _on_color_slider(self, key: str, v: float):
        self._color_vals[key].configure(text=str(int(v)))
        self._preset_var.set("Custom")
        self._update_swatch()
        self._cb("color", self.get_color_range())

    def _update_swatch(self):
        r = self.get_color_range()
        h = (r["hue_min"] + r["hue_max"]) / 2 / 180
        s = max(0.35, (r["sat_min"] + r["sat_max"]) / 2 / 255)
        v = max(0.45, (r["val_min"] + r["val_max"]) / 2 / 255)
        rr, gg, bb = colorsys.hsv_to_rgb(h, s, v)
        self._swatch.configure(fg_color="#%02x%02x%02x" % (int(rr * 255), int(gg * 255), int(bb * 255)))

    # ── External API ───────────────────────────────────────────────────

    def set_mode(self, mode: str):
        """Show the controls for `mode` ('Template Matching' / 'Color Detection')."""
        label = next(k for k, v in self.MODE_LABELS.items() if v == mode)
        self._mode_seg.set(label)
        if mode == "Color Detection":
            self._image_box.pack_forget()
            self._color_box.pack(fill="x")
            self._conf_box.pack_forget()
        else:
            self._color_box.pack_forget()
            self._image_box.pack(fill="x")
            self._conf_box.pack(fill="x", before=self._delay_box)

    def get_mode(self) -> str:
        return self.MODE_LABELS[self._mode_seg.get()]

    def get_overlay_enabled(self) -> bool:
        return bool(self._overlay_var.get())

    def set_overlay_enabled(self, enabled: bool):
        self._overlay_var.set(bool(enabled))

    def set_confidence(self, value: float):
        pct = max(50, min(100, round(value * 100)))
        self._conf_slider.set(pct)
        self._conf_val.configure(text=f"{pct}%")

    def get_confidence(self) -> float:
        return self._conf_slider.get() / 100.0

    def set_delay(self, seconds: float):
        v = max(5, min(200, round(seconds * 100)))
        self._delay_slider.set(v)
        self._delay_val.configure(text=f"{v / 100.0:.2f} s")

    def get_delay(self) -> float:
        return self._delay_slider.get() / 100.0

    def get_interval_ms(self) -> int:
        return int(self._interval_var.get().replace(" ms", ""))

    def get_click_mode(self) -> str:
        return self._click_mode_var.get()

    def get_target_mode(self) -> str:
        return self.ORDER_LABELS[self._order_seg.get()]

    def set_region_label(self, text: str):
        self._region_label.configure(text=text)

    def set_color_range(self, rng: dict):
        for key, _, mx in self.COLOR_FIELDS:
            if key in rng:
                v = max(0, min(mx, int(rng[key])))
                self._color_sliders[key].set(v)
                self._color_vals[key].configure(text=str(v))
        self._preset_var.set("Custom")
        for name, p in self._presets.items():
            if all(int(rng.get(k, -1)) == p[k] for k in p):
                self._preset_var.set(name)
                break
        self._update_swatch()

    def get_color_range(self) -> dict:
        return {k: int(self._color_sliders[k].get()) for k, _, _ in self.COLOR_FIELDS}

    def _delay_entry(self, parent, index: int, tmpl: dict) -> ctk.CTkEntry:
        """Seconds to wait after this image is found, before clicking it."""
        entry = ctk.CTkEntry(
            parent, width=52, height=24, justify="center", font=T.font(12),
            fg_color=T.BG, border_color=T.BORDER, text_color=T.TEXT,
            corner_radius=T.R_CTRL)
        entry.insert(0, f"{tmpl.get('pre_delay_ms', 0) / 1000:.2f}")

        def commit(_event=None):
            current_ms = int(tmpl.get("pre_delay_ms", 0))
            val = parse_pre_delay(entry.get())
            if val is None:                    # junk or out of range: put the old value back
                val = current_ms / 1000
            entry.delete(0, "end")
            entry.insert(0, f"{val:.2f}")
            if int(round(val * 1000)) != current_ms:
                self._cb("template_delay", index, val)

        entry.bind("<Return>", commit)
        entry.bind("<FocusOut>", commit)
        self._row_commits.append(commit)
        return entry

    def commit_pending(self):
        """Apply any delay typed into a row but not yet committed (Enter or
        focus-out). Call before starting a run or saving, since global hotkeys
        and closing the window never move focus out of the field."""
        for commit in list(self._row_commits):
            commit()

    def set_template_list(self, templates: list[dict]):
        self._row_commits = []
        for w in self._tmpl_list.winfo_children():
            w.destroy()

        if not templates:
            ctk.CTkLabel(
                self._tmpl_list, text="No images yet", font=T.font(12, True),
                text_color=T.MUTED).pack(pady=(14, 0))
            ctk.CTkLabel(
                self._tmpl_list,
                text="Add a picture of the thing to click,\nor snip it straight from the screen.",
                font=T.font(11), text_color=T.DIM, justify="center").pack(pady=(2, 14))
            self._order_row.pack_forget()
            return

        for i, tmpl in enumerate(templates):
            name = Path(tmpl["path"]).name
            if len(name) > 16:
                name = name[:15] + "…"
            row = ctk.CTkFrame(self._tmpl_list, fg_color="transparent", height=30)
            row.pack(fill="x", padx=(10, 4), pady=(4 if i == 0 else 0, 4 if i == len(templates) - 1 else 0))
            ctk.CTkLabel(row, text=f"{i + 1}", width=16, font=T.font(11),
                         text_color=T.DIM).pack(side="left")
            ctk.CTkLabel(row, text=name, font=T.font(12), text_color=T.TEXT,
                         anchor="w").pack(side="left", padx=(4, 0))
            ctk.CTkButton(
                row, text="", image=self._icons["x"], width=26, height=26,
                fg_color="transparent", hover_color=T.HOVER, corner_radius=T.R_CTRL,
                command=lambda idx=i: self._cb("remove_template", idx)
            ).pack(side="right")
            ctk.CTkLabel(row, text="s", font=T.font(11), text_color=T.DIM,
                         width=10).pack(side="right")
            self._delay_entry(row, i, tmpl).pack(side="right", padx=(0, 2))

        if len(templates) > 1:
            self._order_row.pack(fill="x")
        else:
            self._order_row.pack_forget()
