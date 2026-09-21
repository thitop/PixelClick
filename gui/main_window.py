"""
gui/main_window.py — Main application window (redesigned)
"""

from __future__ import annotations
import sys
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import customtkinter as ctk
import keyboard
import cv2
from pathlib import Path
from PIL import Image, ImageTk

from capture.screen_capture import ScreenCapture
from detection.template_match import TemplateMatchDetector
from detection.multi_template import MultiTemplateDetector
from detection.color_detector import ColorDetector
from mouse.click_controller import ClickController
from detection_worker import DetectionWorker
from utils.config import load_config, save_config, get_resource_path
from utils.logger import get_logger
from gui.settings_frame import SettingsFrame
from gui.preview_frame import PreviewFrame
from gui.region_selector import RegionSelector
from gui.overlay import OverlayWindow
from gui.mini_hud import MiniHUD
from utils.icon_loader import load_svg_icon, load_colored_svg

log = get_logger("main_window")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Palette ────────────────────────────────────────────────────────────────
BG_ROOT  = "#0D1117"
BG_PANEL = "#161B22"
BG_CARD  = "#1C2333"
BORDER   = "#21262D"
TEXT_DIM = "#6B7280"
TEXT_LG  = "#E5E7EB"


class MetricCard(ctk.CTkFrame):
    """A single colored metric card for the status grid."""

    def __init__(self, master, label_text: str, value_text: str, color: str):
        super().__init__(master, fg_color="#1F2937", corner_radius=10, height=80)
        self.pack_propagate(False)

        # Left Accent Line
        accent = ctk.CTkFrame(self, fg_color=color, width=4, corner_radius=4)
        accent.pack(side="left", fill="y", padx=(0, 10))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, pady=12)

        ctk.CTkLabel(content, text=label_text,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color="#9CA3AF").pack(anchor="w")

        self._val_label = ctk.CTkLabel(content, text=value_text,
                                        font=ctk.CTkFont("Segoe UI", 16, weight="bold"),
                                        text_color=color)
        self._val_label.pack(anchor="w", pady=(2, 0))

    def set(self, text: str, color: str | None = None):
        self._val_label.configure(text=text)
        if color:
            self._val_label.configure(text_color=color)


class MainWindow(ctk.CTk):

    APP_TITLE = "PixelClick"
    APP_W, APP_H = 1050, 700

    def __init__(self, config: dict):
        super().__init__()
        self._config = config
        self._running = False
        self._paused = False
        self._templates: list[dict] = []

        self._capture   = ScreenCapture()
        self._click_ctrl = ClickController(
            cooldown_ms=config.get("cooldown_ms", 300),
            max_clicks_per_second=config.get("max_clicks_per_second", 10),
        )
        self._worker = DetectionWorker(
            capture=self._capture,
            click_ctrl=self._click_ctrl,
            on_update=self._on_worker_update,
        )

        self._load_icons()
        self._setup_window()
        self._overlay = OverlayWindow(self, box_color="#3B82F6")
        self._mini_hud = MiniHUD(
            self,
            on_start=self._start,
            on_stop=self._stop,
            on_expand=self._exit_mini_hud,
            icons=self._icons
        )
        self._build_ui()
        self._setup_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        log.info("MainWindow initialized.")

    def _load_icons(self):
        self._icons = {
            "logo": ctk.CTkImage(light_image=Image.open(get_resource_path("logo/PixelClick_logo.png")), size=(24, 24)),
            "zap": load_svg_icon("assets/icons/zap.svg", (22, 22)),
            "play": load_svg_icon("assets/icons/play.svg", (18, 18)),
            "square": load_svg_icon("assets/icons/square.svg", (18, 18)),
            "pause": load_svg_icon("assets/icons/pause.svg", (16, 16)),
            "bar-chart": load_svg_icon("assets/icons/bar-chart-2.svg", (16, 16)),
            "alert": load_svg_icon("assets/icons/alert-triangle.svg", (14, 14)),
            "maximize": load_svg_icon("assets/icons/maximize.svg", (14, 14)),
        }

    # ── Window ─────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(self.APP_TITLE)
        try:
            self.iconbitmap(get_resource_path("logo/PixelClick_logo.ico"))
        except Exception as e:
            log.warning(f"Could not set window icon: {e}")
        self.configure(fg_color=BG_ROOT)
        self.minsize(900, 620)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (sw - self.APP_W) // 2
        y = (sh - self.APP_H) // 2
        self.geometry(f"{self.APP_W}x{self.APP_H}+{x}+{y}")

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Left column
        left_pane = ctk.CTkFrame(body, fg_color="transparent", width=280)
        left_pane.pack(side="left", fill="y", padx=(0, 8))
        left_pane.pack_propagate(False)

        # Settings (scrollable)
        self._settings_frame = SettingsFrame(
            left_pane,
            fg_color=BG_PANEL,
            scrollbar_fg_color=BG_PANEL,
            corner_radius=12,
            on_mode_change=self._on_mode_change,
            on_confidence_change=self._on_confidence_change,
            on_delay_change=self._on_delay_change,
            on_interval_change=self._on_interval_change,
            on_load_template=self._load_template,
            on_snip_template=self._snip_template,
            on_clear_templates=self._clear_templates,
        )
        self._settings_frame._cbs["click_mode"] = self._on_click_mode_change
        self._settings_frame.pack(fill="both", expand=True)

        # Control Panel (Start/Stop) fixed at bottom
        self._build_control_panel(left_pane)

        # Right
        right = ctk.CTkFrame(body, fg_color="transparent")
        right.pack(side="left", fill="both", expand=True)

        # Preview
        preview_card = ctk.CTkFrame(right, fg_color=BG_PANEL, corner_radius=12)
        preview_card.pack(fill="both", expand=True, pady=(0, 8))
        self._preview = PreviewFrame(preview_card, fg_color="transparent")
        self._preview.pack(fill="both", expand=True)

        # Metric cards grid
        self._build_metrics(right)

        self._build_footer()

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=BG_PANEL, height=52, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo
        logo = ctk.CTkFrame(hdr, fg_color="transparent")
        logo.pack(side="left", padx=16, pady=8)

        ctk.CTkLabel(logo, text="", image=self._icons.get("logo")).pack(side="left")
        ctk.CTkLabel(logo, text="PixelClick",
                     font=ctk.CTkFont("Segoe UI", 18, weight="bold"),
                     text_color="#F9FAFB").pack(side="left", padx=(4, 8))

        sep = ctk.CTkFrame(hdr, fg_color=BORDER, width=1)
        sep.pack(side="left", fill="y", padx=0, pady=10)

        ctk.CTkLabel(hdr, text="Auto Click Detector  v1.0",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=TEXT_DIM).pack(side="left", padx=12)

        self._status_pill = ctk.CTkFrame(hdr, fg_color="#1A2636", corner_radius=20)
        self._status_pill.pack(side="right", padx=16, pady=12)
        self._status_dot = ctk.CTkLabel(self._status_pill, text="●",
                                         font=ctk.CTkFont("Segoe UI", 12),
                                         text_color="#4B5563")
        self._status_dot.pack(side="left", padx=(10, 4))
        self._status_text = ctk.CTkLabel(self._status_pill, text="Stopped",
                                          font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                                          text_color="#6B7280")
        self._status_text.pack(side="left", padx=(0, 10))

        # Mini HUD button
        self._hud_btn = ctk.CTkButton(
            hdr, text="", image=self._icons.get("maximize") or self._icons.get("bar-chart"),
            width=32, height=32, corner_radius=8,
            fg_color="#1F2937", hover_color="#374151",
            command=self._enter_mini_hud
        )
        self._hud_btn.pack(side="right", padx=(0, 16))

    def _build_control_panel(self, parent):
        ctrl = ctk.CTkFrame(parent, fg_color=BG_PANEL, corner_radius=12, height=130)
        ctrl.pack(fill="x", pady=(8, 0))
        ctrl.pack_propagate(False)

        # START / STOP row
        row = ctk.CTkFrame(ctrl, fg_color="transparent")
        row.pack(padx=12, pady=(16, 8), fill="x")

        self._start_btn = ctk.CTkButton(
            row, text=" START", image=self._icons.get("play"),
            fg_color="#166534", hover_color="#15803D",
            font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
            height=44, corner_radius=10,
            command=self._start)
        self._start_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        self._stop_btn = ctk.CTkButton(
            row, text=" STOP", image=self._icons.get("square"),
            fg_color="#7F1D1D", hover_color="#B91C1C",
            font=ctk.CTkFont("Segoe UI", 14, weight="bold"),
            height=44, corner_radius=10,
            command=self._stop,
            state="disabled")
        self._stop_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

        self._pause_btn = ctk.CTkButton(
            ctrl, text=" PAUSE", image=self._icons.get("pause"),
            fg_color="#78350F", hover_color="#B45309",
            font=ctk.CTkFont("Segoe UI", 13, weight="bold"),
            height=36, corner_radius=8,
            command=self._pause_toggle,
            state="disabled")
        self._pause_btn.pack(padx=12, pady=(0, 12), fill="x")

    def _build_metrics(self, parent):
        grid_frame = ctk.CTkFrame(parent, fg_color=BG_PANEL, corner_radius=12)
        grid_frame.pack(fill="x")

        ctk.CTkLabel(grid_frame, text=" Metrics", image=self._icons.get("bar-chart"), compound="left",
                     font=ctk.CTkFont("Segoe UI", 12, weight="bold"),
                     text_color="#A0C4FF").pack(anchor="w", padx=14, pady=(10, 6))

        cards_row = ctk.CTkFrame(grid_frame, fg_color="transparent")
        cards_row.pack(fill="x", padx=10, pady=(0, 10))

        metrics_cfg = [
            ("Target",     "Not Found", "#EF4444"),
            ("Confidence", "0.00%",     "#60A5FA"),
            ("Clicks",     "0",         "#34D399"),
            ("FPS",        "0",         "#A78BFA"),
            ("Template",   "None",      "#6B7280"),
            ("Time",       "00:00",     "#F59E0B"), # Just a placeholder since we removed Region
        ]

        self._cards: dict[str, MetricCard] = {}
        for i, (label, default, color) in enumerate(metrics_cfg):
            card = MetricCard(cards_row, label_text=label, value_text=default, color=color)
            card.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="nsew")
            self._cards[label] = card

        for c in range(3):
            cards_row.grid_columnconfigure(c, weight=1)

    def _build_footer(self):
        ftr = ctk.CTkFrame(self, fg_color=BG_PANEL, height=28, corner_radius=0)
        ftr.pack(fill="x", side="bottom")
        ftr.pack_propagate(False)
        ctk.CTkLabel(ftr,
                     text=" FailSafe: Move mouse to top-left corner to emergency stop",
                     image=self._icons.get("alert"), compound="left",
                     font=ctk.CTkFont("Segoe UI", 9),
                     text_color="#374151").pack(side="left", padx=14)

    # ── Hotkeys ────────────────────────────────────────────────────────

    def _setup_hotkeys(self):
        hk = self._config.get("hotkeys", {})
        try:
            keyboard.add_hotkey(hk.get("start", "f6"),          self._start)
            keyboard.add_hotkey(hk.get("stop",  "f7"),          self._stop)
            keyboard.add_hotkey(hk.get("pause", "f8"),          self._pause_toggle)
            keyboard.add_hotkey(hk.get("snip_template", "f10"), self._snip_template)
            log.info("Global hotkeys registered.")
        except Exception as e:
            log.warning(f"Could not register hotkeys: {e}")

    # ── Worker callback ────────────────────────────────────────────────

    def _on_worker_update(self, status: dict):
        self.after(0, self._apply_status, status)

    def _apply_status(self, status: dict):
        found      = status.get("found", False)
        conf       = status.get("confidence", 0.0)
        clicks     = status.get("clicks", 0)
        fps        = status.get("fps", 0.0)
        x, y       = status.get("x", 0), status.get("y", 0)
        error      = status.get("error", "")

        if error:
            self._cards["Target"].set(f"⚠ Error", "#F87171")
        elif found:
            self._cards["Target"].set("Found ✓", "#22C55E")
        else:
            self._cards["Target"].set("Not Found", "#9CA3AF")

        self._cards["Confidence"].set(f"{conf:.1%}")
        self._cards["Clicks"].set(str(clicks))
        self._cards["FPS"].set(f"{fps:.0f}")

        frame = self._worker.last_frame
        self._preview.update_frame(frame, found, x, y, conf)

        # Update Overlay
        if self._running and self._settings_frame.get_overlay_enabled():
            if not self._overlay._is_showing:
                self._overlay.show()
                
            x = status.get("x", 0)
            y = status.get("y", 0)
            w = status.get("width", 0)
            h = status.get("height", 0)
            self._overlay.update_target(found, x, y, w, h)
        else:
            if self._overlay._is_showing:
                self._overlay.hide()

        # Update Mini HUD
        if hasattr(self, "_mini_hud"):
            self._mini_hud.update_status(self._running, self._click_ctrl.click_count)

    # ── Controls ───────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return
        if not self._build_detector():
            return
        self._running = True
        self._worker.start()
        
        self._start_btn.configure(state="disabled", fg_color="#0F3B20")
        self._stop_btn.configure(state="normal", fg_color="#7F1D1D")
        self._pause_btn.configure(state="normal")
        
        self._set_status("Running", "#22C55E")

    def _stop(self):
        if not self._running:
            return
        self._running = False
        self._paused = False
        self._worker.stop()
        
        if self._overlay._is_showing:
            self._overlay.hide()
        
        self._start_btn.configure(state="normal", fg_color="#166534")
        self._stop_btn.configure(state="disabled", fg_color="#1F2937")
        self._pause_btn.configure(state="disabled", text="⏸  PAUSE", image=self._icons.get("pause"))
        
        self._set_status("Stopped", "#9CA3AF")
        self._preview.clear()

    def _enter_mini_hud(self):
        """Hides main window and shows mini HUD"""
        self.withdraw()
        self._mini_hud.show()
        
    def _exit_mini_hud(self):
        """Hides mini HUD and shows main window"""
        self._mini_hud.hide()
        self.deiconify()

    def _pause_toggle(self):
        if not self._running:
            return
        self._paused = not self._paused
        if self._paused:
            self._worker.pause()
            self._set_status("Paused", "#F59E0B")
            self._pause_btn.configure(text=" RESUME", image=self._icons.get("play"))
        else:
            self._worker.resume()
            self._set_status("Running", "#22C55E")
            self._pause_btn.configure(text=" PAUSE", image=self._icons.get("pause"))

    def _build_detector(self) -> bool:
        mode       = self._settings_frame.get_mode()
        confidence = self._settings_frame.get_confidence()
        delay_sec  = self._settings_frame.get_delay()

        self._click_ctrl.cooldown_ms   = int(delay_sec * 1000)
        self._click_ctrl.click_mode    = self._settings_frame.get_click_mode()
        self._worker.set_interval_ms(
            int(self._settings_frame._interval_var.get().replace(" ms", ""))
        )
        self._worker.clear_region()

        if mode == "Template Matching":
            if not self._templates:
                mb.showerror("No Templates",
                             "Please load or snip at least one template image first.",
                             parent=self)
                return False
            
            target_mode = self._settings_frame.get_target_mode()
            detector = MultiTemplateDetector(self._templates, threshold=confidence, mode=target_mode)
        else:
            detector = ColorDetector(threshold=confidence)

        self._worker.set_detector(detector)
        return True

    def _load_template(self):
        path = fd.askopenfilename(
            title="Select Template Image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("All files", "*.*")],
            parent=self)
        if path:
            p = Path(path)
            delay_ms = int(self._settings_frame.get_delay() * 1000)
            self._templates.append({"path": p, "delay": delay_ms})
            self._cards["Template"].set(f"{len(self._templates)} loaded", "#A78BFA")
            self._settings_frame.set_template_list(self._templates)
            log.info(f"Template added: {path} (Delay: {delay_ms}ms)")

    def _clear_templates(self):
        self._templates.clear()
        self._cards["Template"].set("None", "#6B7280")
        self._settings_frame.set_template_list(self._templates)
        log.info("Cleared all templates.")

    # ── Snip Template ──────────────────────────────────────────────────

    def _snip_template(self):
        self.withdraw()
        self.after(200, self._open_snip_selector)

    def _open_snip_selector(self):
        RegionSelector(self, on_select=self._on_snip_selected,
                       on_cancel=self._on_snip_cancel)

    def _on_snip_selected(self, x, y, w, h):
        self.after(0, self.deiconify)
        try:
            frame = self._capture.capture_region(x, y, w, h)
            # Create data folder if not exists
            data_dir = Path("data")
            # Save snippet with unique name
            import time
            timestamp = int(time.time())
            path = data_dir / f"snip_{timestamp}.png"
            
            # Save snippet
            cv2.imwrite(str(path), frame)
            
            # Add to template list
            p = path.absolute()
            delay_ms = int(self._settings_frame.get_delay() * 1000)
            self._templates.append({"path": p, "delay": delay_ms})
            self._cards["Template"].set(f"{len(self._templates)} loaded", "#A78BFA")
            self._settings_frame.set_template_list(self._templates)
            log.info(f"Snipped template saved to {p} (Delay: {delay_ms}ms)")
            
            # Auto-switch mode
            self._settings_frame._mode_var.set("Template Matching")
            self._settings_frame._cb("mode", "Template Matching")
            
        except Exception as e:
            log.error(f"Failed to snip template: {e}")
            mb.showerror("Snip Error", f"Could not save snipped template:\n{e}")

    def _on_snip_cancel(self):
        self.after(0, self.deiconify)

    # ── Status pill ────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status_dot.configure(text_color=color)
        self._status_text.configure(text=text, text_color=color)

    # ── Callbacks from SettingsFrame ───────────────────────────────────

    def _on_mode_change(self, mode: str):
        log.debug(f"Mode: {mode}")

    def _on_confidence_change(self, value: float):
        if self._worker._detector:
            self._worker._detector.threshold = value

    def _on_delay_change(self, value: float):
        self._click_ctrl.cooldown_ms = int(value * 1000)

    def _on_interval_change(self, ms: int):
        self._worker.set_interval_ms(ms)

    def _on_click_mode_change(self, mode: str):
        self._click_ctrl.click_mode = mode
        log.info(f"Click mode: {mode}")

    # ── Config / Lifecycle ─────────────────────────────────────────────

    def _save_config_state(self):
        self._config["confidence"]  = self._settings_frame.get_confidence()
        self._config["click_delay"] = self._settings_frame.get_delay()
        save_config(self._config)

    def _on_close(self):
        self._stop()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self._save_config_state()
        self.destroy()
