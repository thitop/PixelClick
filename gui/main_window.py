"""
gui/main_window.py — Main application window.

Layout: setup flow + actions on the left, live preview + quiet stats on the right.
All colours / radii come from gui/theme.py.
"""

from __future__ import annotations
import time
import tkinter.filedialog as fd
import tkinter.messagebox as mb
import customtkinter as ctk
import keyboard
import cv2
from pathlib import Path
from PIL import Image

from capture.screen_capture import ScreenCapture
from detection.multi_template import MultiTemplateDetector
from detection.color_detector import ColorDetector
from mouse.click_controller import ClickController
from detection_worker import DetectionWorker
from utils.config import (save_config, get_resource_path, get_config_dir,
                          normalize_template, sanitize_config)
from utils.logger import get_logger
from utils.mailbox import LatestOnly
from gui import theme as T
from gui.settings_frame import SettingsFrame
from gui.preview_frame import PreviewFrame
from gui.region_selector import RegionSelector
from gui.overlay import OverlayWindow
from gui.mini_hud import MiniHUD
from utils.icon_loader import load_svg_icon

log = get_logger("main_window")

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


def register_hotkeys(bindings, add=None) -> list[str]:
    """Register each (key, callback) on its own so one invalid key name does
    not silently drop the rest. Returns the keys that failed."""
    add = add or keyboard.add_hotkey
    failed = []
    for key, fn in bindings:
        try:
            add(key, fn)
        except Exception as e:
            log.warning(f"Could not register hotkey {key!r}: {e}")
            failed.append(key)
    return failed


class Stat(ctk.CTkFrame):
    """Label over value. Plain text, no card."""

    def __init__(self, master, label: str, value: str = "—"):
        super().__init__(master, fg_color="transparent")
        ctk.CTkLabel(self, text=label, font=T.font(11), text_color=T.DIM,
                     anchor="w").pack(anchor="w")
        self._val = ctk.CTkLabel(self, text=value, font=T.font(15, True),
                                 text_color=T.TEXT, anchor="w")
        self._val.pack(anchor="w")

    def set(self, text: str, color: str = T.TEXT):
        self._val.configure(text=text, text_color=color)


class MainWindow(ctk.CTk):

    APP_TITLE = "PixelClick"
    APP_W, APP_H = 1000, 760
    LEFT_W = 340

    def __init__(self, config: dict):
        super().__init__()
        self._config = sanitize_config(config)  # bad hand-edited values -> defaults
        self._running = False
        self._paused = False
        self._templates: list[dict] = []
        self._region: tuple[int, int, int, int] | None = None
        self._started_at: float = 0.0
        self._status_box = LatestOnly()
        self._compact = False  # True while the mini HUD replaces the window
        self._resume_after_pick = False  # snip paused a running scan

        self._capture = ScreenCapture()
        self._click_ctrl = ClickController(
            cooldown_ms=int(config.get("click_delay", 0.3) * 1000),
            max_clicks_per_second=config.get("max_clicks_per_second", 10),
        )
        self._worker = DetectionWorker(
            capture=self._capture,
            click_ctrl=self._click_ctrl,
            on_update=self._on_worker_update,
        )

        self._load_icons()
        self._setup_window()
        self._overlay = OverlayWindow(self, box_color=T.ACCENT)
        self._mini_hud = MiniHUD(
            self,
            on_start=self._start,
            on_stop=self._stop,
            on_expand=self._exit_mini_hud,
            icons=self._icons,
            hotkeys=self._config.get("hotkeys", {}),
        )
        self._build_ui()
        self._restore_state()
        self._refresh_start_state()
        self._setup_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(33, self._poll_status)
        log.info("MainWindow initialized.")

    def _load_icons(self):
        self._icons = {
            "logo": ctk.CTkImage(
                light_image=Image.open(get_resource_path("logo/PixelClick_logo.png")),
                size=(24, 24)),
            "play": load_svg_icon("assets/icons/play.svg", (16, 16)),
            "square": load_svg_icon("assets/icons/square.svg", (16, 16)),
            "pause": load_svg_icon("assets/icons/pause.svg", (16, 16)),
            "maximize": load_svg_icon("assets/icons/maximize.svg", (14, 14)),
        }

    # ── Window ─────────────────────────────────────────────────────────

    def _setup_window(self):
        self.title(self.APP_TITLE)
        try:
            self.iconbitmap(get_resource_path("logo/PixelClick_logo.ico"))
        except Exception as e:
            log.warning(f"Could not set window icon: {e}")
        self.configure(fg_color=T.BG)
        self.minsize(900, 620)
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        h = min(self.APP_H, sh - 100)  # leave room for the taskbar on small screens
        x = (sw - self.APP_W) // 2
        y = max(0, (sh - h) // 2 - 20)
        self.geometry(f"{self.APP_W}x{h}+{x}+{y}")

    # ── UI ─────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_header()
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=T.PAD, pady=(0, T.PAD))

        left = ctk.CTkFrame(body, fg_color="transparent", width=self.LEFT_W)
        left.pack(side="left", fill="y", padx=(0, T.GAP + 4))
        left.pack_propagate(False)

        self._settings_frame = SettingsFrame(
            left,
            fg_color=T.SURFACE, corner_radius=T.R_PANEL,
            scrollbar_fg_color=T.SURFACE,
            scrollbar_button_color=T.BORDER,
            scrollbar_button_hover_color=T.HOVER,
            on_mode_change=self._on_mode_change,
            on_confidence_change=self._on_confidence_change,
            on_delay_change=self._on_delay_change,
            on_interval_change=self._on_interval_change,
            on_click_mode_change=self._on_click_mode_change,
            on_load_template=self._load_template,
            on_snip_template=self._snip_template,
            on_clear_templates=self._clear_templates,
            on_remove_template=self._remove_template,
            on_template_delay_change=self._on_template_delay,
            on_target_mode_change=self._on_target_mode_change,
            on_select_region=self._select_region,
            on_clear_region=self._clear_region,
            on_color_change=self._on_color_change,
        )
        self._build_actions(left)          # packed first at the bottom
        self._settings_frame.pack(fill="both", expand=True, pady=(0, T.GAP + 4))

        right = ctk.CTkFrame(body, fg_color=T.SURFACE, corner_radius=T.R_PANEL)
        right.pack(side="left", fill="both", expand=True)
        self._preview = PreviewFrame(right, fg_color="transparent")
        self._preview.pack(fill="both", expand=True)
        self._build_stats(right)

    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=T.SURFACE, height=48, corner_radius=0)
        hdr.pack(fill="x", pady=(0, T.PAD))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr, text="", image=self._icons["logo"]).pack(
            side="left", padx=(T.PAD, 8))
        ctk.CTkLabel(hdr, text="PixelClick", font=T.font(15, True),
                     text_color=T.TEXT).pack(side="left")

        ctk.CTkButton(
            hdr, text="Compact view", image=self._icons["maximize"], compound="left",
            width=0, height=30, fg_color=T.RAISED, hover_color=T.HOVER,
            text_color=T.TEXT, corner_radius=T.R_CTRL, font=T.font(12),
            command=self._enter_mini_hud,
        ).pack(side="right", padx=T.PAD)

        status = ctk.CTkFrame(hdr, fg_color="transparent")
        status.pack(side="right", padx=(0, T.PAD))
        self._status_dot = ctk.CTkLabel(status, text="●", font=T.font(12), text_color=T.DIM)
        self._status_dot.pack(side="left", padx=(0, 6))
        self._status_text = ctk.CTkLabel(status, text="Stopped", font=T.font(12, True),
                                         text_color=T.MUTED)
        self._status_text.pack(side="left")

    def _build_actions(self, parent):
        hk = self._config.get("hotkeys", {})
        key = lambda name, d: hk.get(name, d).upper()

        bar = ctk.CTkFrame(parent, fg_color=T.SURFACE, corner_radius=T.R_PANEL)
        bar.pack(side="bottom", fill="x")

        self._start_hint = ctk.CTkLabel(
            bar, text="", height=16, font=T.font(11), text_color=T.WARN, anchor="w")
        # Only shown (packed) while START is blocked; see _refresh_start_state.

        self._start_btn = ctk.CTkButton(
            bar, text=f"Start    {key('start', 'f6')}", image=self._icons["play"],
            compound="left", height=44, corner_radius=T.R_CTRL,
            fg_color=T.ACCENT, hover_color=T.ACCENT_HOVER, text_color=T.ON_ACCENT,
            text_color_disabled=T.DIM, font=T.font(14, True), command=self._start)
        self._start_btn.pack(fill="x", padx=T.PAD, pady=(T.PAD, 0))

        row = ctk.CTkFrame(bar, fg_color="transparent")
        row.pack(fill="x", padx=T.PAD, pady=(8, 0))
        row.grid_columnconfigure((0, 1), weight=1, uniform="c")

        self._pause_btn = ctk.CTkButton(
            row, text=f"Pause    {key('pause', 'f8')}", image=self._icons["pause"],
            compound="left", height=36, corner_radius=T.R_CTRL,
            fg_color=T.RAISED, hover_color=T.HOVER, text_color=T.TEXT,
            text_color_disabled=T.DIM, font=T.font(12),
            command=self._pause_toggle, state="disabled")
        self._pause_btn.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._stop_btn = ctk.CTkButton(
            row, text=f"Stop    {key('stop', 'f7')}", image=self._icons["square"],
            compound="left", height=36, corner_radius=T.R_CTRL,
            fg_color=T.RAISED, hover_color=T.HOVER, text_color=T.TEXT,
            text_color_disabled=T.DIM, font=T.font(12),
            command=self._stop, state="disabled")
        self._stop_btn.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        ctk.CTkLabel(
            bar, text="Emergency stop: move the mouse to the top-left corner.",
            font=T.font(10), text_color=T.DIM, anchor="w",
        ).pack(fill="x", padx=T.PAD, pady=(8, 12))

    def _build_stats(self, parent):
        ctk.CTkFrame(parent, fg_color=T.BORDER, height=1).pack(fill="x")
        strip = ctk.CTkFrame(parent, fg_color="transparent")
        strip.pack(fill="x", padx=T.PAD, pady=12)
        self._stats: dict[str, Stat] = {}
        for i, label in enumerate(("Target", "Confidence", "Clicks", "Elapsed", "Scans/s")):
            s = Stat(strip, label)
            s.grid(row=0, column=i, sticky="w", padx=(0, 8))
            strip.grid_columnconfigure(i, weight=1, uniform="s")
            self._stats[label] = s
        self._stats["Clicks"].set("0")
        self._stats["Elapsed"].set("00:00")

    # ── Start button state ─────────────────────────────────────────────

    def _refresh_start_state(self):
        """Enable START only when it can work; say why when it cannot."""
        if self._running:
            return
        blocked = ""
        if self._settings_frame.get_mode() == "Template Matching" and not self._templates:
            blocked = "Add or snip an image first."
        self._start_hint.configure(text=blocked)
        if blocked:
            self._start_hint.pack(fill="x", padx=T.PAD, pady=(12, 0), before=self._start_btn)
            self._start_btn.configure(state="disabled", fg_color=T.RAISED)
        else:
            self._start_hint.pack_forget()
            self._start_btn.configure(state="normal", fg_color=T.ACCENT)

    # ── Hotkeys ────────────────────────────────────────────────────────

    def _setup_hotkeys(self):
        hk = self._config.get("hotkeys", {})

        # `keyboard` fires callbacks on its own thread; tkinter is not
        # thread-safe, so marshal every action onto the Tk main loop.
        def on_main(fn):
            return lambda: self.after(0, fn)

        failed = register_hotkeys([
            (hk.get("start", "f6"),          on_main(self._start)),
            (hk.get("stop",  "f7"),          on_main(self._stop)),
            (hk.get("pause", "f8"),          on_main(self._pause_toggle)),
            (hk.get("select_region", "f9"),  on_main(self._select_region)),
            (hk.get("snip_template", "f10"), on_main(self._snip_template)),
        ])
        if failed:
            self._set_status(f"Invalid hotkey in settings: {', '.join(failed)}", T.WARN)
        else:
            log.info("Global hotkeys registered.")

    # ── Worker callback ────────────────────────────────────────────────

    def _on_worker_update(self, status: dict):
        # Called on the worker thread: never touch Tk here (a cross-thread
        # after() blocks until the Tk loop is free, which deadlocks with
        # Stop's join). Just drop the newest status in the mailbox.
        self._status_box.put(status)

    def _poll_status(self):
        status = self._status_box.take()
        if status is not None:
            self._apply_status(status)
        self.after(33, self._poll_status)

    def _apply_status(self, status: dict):
        if not self._running:
            return  # late update queued before STOP; ignore
        if status.get("failsafe"):
            log.warning("FailSafe triggered — stopping.")
            self._stop()
            self._set_status("FailSafe triggered", T.ERR)
            return

        found = status.get("found", False)
        conf = status.get("confidence", 0.0)

        if status.get("error"):
            self._stats["Target"].set("Error", T.ERR)
        elif status.get("paused"):
            self._stats["Target"].set("Paused", T.MUTED)
        elif status.get("waiting"):
            self._stats["Target"].set("Waiting", T.WARN)
        elif found:
            self._stats["Target"].set("Found", T.OK)
        else:
            self._stats["Target"].set("Searching", T.MUTED)

        self._stats["Confidence"].set(f"{conf:.0%}" if conf > 0 else "—")
        self._stats["Clicks"].set(str(status.get("clicks", 0)))
        self._stats["Scans/s"].set(f"{status.get('fps', 0.0):.0f}")
        self._stats["Elapsed"].set(self._elapsed_text())

        self._preview.update_frame(
            self._worker.last_frame, found,
            status.get("x", 0), status.get("y", 0), conf)

        if self._settings_frame.get_overlay_enabled():
            if not self._overlay._is_showing:
                self._overlay.show()
            self._overlay.update_target(
                found,
                status.get("box_x", 0), status.get("box_y", 0),
                status.get("width", 0), status.get("height", 0),
            )
        elif self._overlay._is_showing:
            self._overlay.hide()

        self._mini_hud.update_status(self._running, self._click_ctrl.click_count, self._paused)

    # ── Controls ───────────────────────────────────────────────────────

    def _start(self):
        if self._running:
            return
        self._settings_frame.commit_pending()
        if not self._build_detector():
            return
        self._status_box.take()  # drop any status left over from the last run
        if not self._worker.start():
            self._set_status("Still stopping, try again", T.WARN)
            return
        self._running = True
        self._started_at = time.monotonic()

        self._start_hint.pack_forget()
        self._start_btn.configure(state="disabled", fg_color=T.RAISED)
        self._stop_btn.configure(state="normal", text_color=T.ERR)
        self._pause_btn.configure(state="normal")
        self._set_status("Running", T.OK)

    def _stop(self):
        if not self._running:
            return
        self._running = False
        self._paused = False
        self._worker.stop()

        if self._overlay._is_showing:
            self._overlay.hide()

        self._stop_btn.configure(state="disabled", text_color=T.TEXT)
        self._pause_btn.configure(
            state="disabled", text=self._pause_text("Pause"), image=self._icons["pause"])
        self._set_status("Stopped", T.MUTED)
        self._preview.clear()
        for k in ("Target", "Confidence", "Scans/s"):
            self._stats[k].set("—")
        self._mini_hud.update_status(False, self._click_ctrl.click_count)
        self._refresh_start_state()

    def _pause_text(self, word: str) -> str:
        key = self._config.get("hotkeys", {}).get("pause", "f8").upper()
        return f"{word}    {key}"

    def _pause_toggle(self):
        if not self._running:
            return
        self._paused = not self._paused
        if self._paused:
            self._worker.pause()
            self._set_status("Paused", T.WARN)
            self._pause_btn.configure(text=self._pause_text("Resume"), image=self._icons["play"])
        else:
            self._worker.resume()
            self._set_status("Running", T.OK)
            self._pause_btn.configure(text=self._pause_text("Pause"), image=self._icons["pause"])
        self._mini_hud.update_status(True, self._click_ctrl.click_count, self._paused)

    def _elapsed_text(self) -> str:
        secs = int(time.monotonic() - self._started_at)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _enter_mini_hud(self):
        self._compact = True
        self.withdraw()
        self._mini_hud.show()

    def _exit_mini_hud(self):
        self._compact = False
        self._mini_hud.hide()
        self.deiconify()

    def _hide_for_screen_pick(self):
        """Hide whatever PixelClick has on screen so it is not in the pick/snip."""
        self.withdraw()
        if self._compact:
            self._mini_hud.hide()

    def _restore_after_screen_pick(self):
        if self._compact:
            self._mini_hud.show()
        else:
            self.deiconify()
        if self._resume_after_pick:
            self._resume_after_pick = False
            if self._running and self._paused:
                self._pause_toggle()

    def _show_error(self, title: str, message: str):
        """Error dialogs need a visible parent; leave compact view first."""
        if self._compact:
            self._exit_mini_hud()
        mb.showerror(title, message, parent=self)

    def _build_detector(self) -> bool:
        sf = self._settings_frame
        mode = sf.get_mode()

        self._click_ctrl.cooldown_ms = int(sf.get_delay() * 1000)
        self._click_ctrl.click_mode = sf.get_click_mode()
        self._worker.set_interval_ms(sf.get_interval_ms())

        if self._region:
            self._worker.set_region(*self._region)
        else:
            self._worker.clear_region()

        if mode == "Template Matching":
            if not self._templates:
                self._show_error("No images", "Add or snip at least one image first.")
                return False
            detector = self._make_template_detector()
            if not detector.is_ready():
                self._show_error("Images could not be loaded",
                                 "None of the images could be read. Check that the files still exist.")
                return False
        else:
            cd = sf.get_color_range()
            detector = ColorDetector(
                hue_min=cd["hue_min"], hue_max=cd["hue_max"],
                sat_min=cd["sat_min"], sat_max=cd["sat_max"],
                val_min=cd["val_min"], val_max=cd["val_max"],
                threshold=sf.get_confidence(),
            )

        self._worker.set_detector(detector)
        return True

    def _make_template_detector(self) -> MultiTemplateDetector:
        sf = self._settings_frame
        return MultiTemplateDetector(
            self._templates, threshold=sf.get_confidence(), mode=sf.get_target_mode())

    # ── Templates ──────────────────────────────────────────────────────

    def _on_templates_changed(self):
        self._settings_frame.set_template_list(self._templates)
        if self._running and self._settings_frame.get_mode() == "Template Matching":
            # Keep the running scan in step with the list on screen.
            if not self._templates:
                self._stop()
                self._set_status("Stopped: no images left", T.WARN)
                return
            detector = self._make_template_detector()
            if detector.is_ready():
                self._worker.set_detector(detector)
            else:
                log.warning("Updated image list could not be loaded; keeping the previous one.")
        self._refresh_start_state()

    def _add_template(self, path: Path):
        self._templates.append({"path": path, "pre_delay_ms": 0})
        self._on_templates_changed()
        log.info(f"Template added: {path}")

    def _load_template(self):
        paths = fd.askopenfilenames(
            title="Select target image",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                       ("All files", "*.*")],
            parent=self)
        for p in paths:
            self._add_template(Path(p))

    def _on_template_delay(self, index: int, seconds: float):
        """A row's 'before click' field changed. The detector reads the same
        dict, so this takes effect immediately, even while running."""
        if 0 <= index < len(self._templates):
            self._templates[index]["pre_delay_ms"] = int(round(seconds * 1000))

    def _remove_template(self, index: int):
        if 0 <= index < len(self._templates):
            removed = self._templates.pop(index)
            log.info(f"Template removed: {removed['path']}")
            self._on_templates_changed()

    def _clear_templates(self):
        self._templates.clear()
        self._on_templates_changed()
        log.info("Cleared all templates.")

    # ── Capture region ─────────────────────────────────────────────────

    def _select_region(self):
        if self._running:
            return  # region is applied on START; avoid changing it mid-run
        self._hide_for_screen_pick()
        self.after(200, lambda: RegionSelector(
            self, on_select=self._on_region_selected,
            on_cancel=self._on_snip_cancel))

    def _on_region_selected(self, x, y, w, h):
        self.after(0, self._restore_after_screen_pick)
        self._region = (x, y, w, h)
        self._settings_frame.set_region_label(f"{w} × {h} at ({x}, {y})")
        log.info(f"Capture region set: {self._region}")

    def _clear_region(self):
        self._region = None
        self._settings_frame.set_region_label("Whole screen")

    # ── Snip template ──────────────────────────────────────────────────

    def _snip_template(self):
        # Snipping while running: pause clicking so the worker does not move
        # the mouse while the user drags; resume afterwards (only if we paused).
        if self._running and not self._paused:
            self._pause_toggle()
            self._resume_after_pick = True
        self._hide_for_screen_pick()
        self.after(200, self._open_snip_selector)

    def _open_snip_selector(self):
        RegionSelector(self, on_select=self._on_snip_selected,
                       on_cancel=self._on_snip_cancel)

    def _on_snip_selected(self, x, y, w, h):
        self.after(0, self._restore_after_screen_pick)
        try:
            frame = self._capture.capture_region(x, y, w, h)
            data_dir = get_config_dir().parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            path = data_dir / f"snip_{time.time_ns() // 1_000_000}.png"  # ms: two snips in a second must not overwrite

            # imencode so non-ASCII paths work
            ok, buf = cv2.imencode(".png", frame)
            if not ok:
                raise RuntimeError("PNG encode failed")
            buf.tofile(str(path))

            self._add_template(path.absolute())
            if self._settings_frame.get_mode() != "Template Matching":
                self._settings_frame.set_mode("Template Matching")
                self._on_mode_change("Template Matching")  # also retargets a running scan
            self._refresh_start_state()
        except Exception as e:
            log.error(f"Failed to snip template: {e}")
            self._show_error("Snip failed", f"Could not save the snipped image:\n{e}")

    def _on_snip_cancel(self):
        self.after(0, self._restore_after_screen_pick)

    # ── Status ─────────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        self._status_dot.configure(text_color=color)
        self._status_text.configure(text=text, text_color=color)

    # ── Callbacks from SettingsFrame ───────────────────────────────────

    def _on_mode_change(self, mode: str):
        log.debug(f"Mode: {mode}")
        if self._running:
            # Keep the running scan in step with what the panel shows.
            if mode == "Template Matching" and not self._templates:
                self._stop()
                self._set_status("Stopped: no images to look for", T.WARN)
                return
            if not self._build_detector():
                self._stop()
                return
        self._refresh_start_state()

    def _on_target_mode_change(self, order: str):
        if self._running and self._settings_frame.get_mode() == "Template Matching":
            detector = self._make_template_detector()
            if detector.is_ready():
                self._worker.set_detector(detector)

    def _on_confidence_change(self, value: float):
        if self._worker._detector:
            self._worker._detector.threshold = value

    def _on_color_change(self, rng: dict):
        self._config["color_detection"] = dict(rng)
        det = self._worker._detector
        if isinstance(det, ColorDetector):  # apply live while running
            det.set_color_range(rng["hue_min"], rng["hue_max"], rng["sat_min"],
                                rng["sat_max"], rng["val_min"], rng["val_max"])

    def _on_delay_change(self, value: float):
        self._click_ctrl.cooldown_ms = int(value * 1000)

    def _on_interval_change(self, ms: int):
        self._worker.set_interval_ms(ms)

    def _on_click_mode_change(self, mode: str):
        self._click_ctrl.click_mode = mode
        log.info(f"Click mode: {mode}")

    # ── Config / lifecycle ─────────────────────────────────────────────

    def _restore_state(self):
        """Re-apply settings, region and templates saved by the last session."""
        sf = self._settings_frame
        sf.set_confidence(self._config.get("confidence", 0.85))
        sf.set_delay(self._config.get("click_delay", 0.30))
        sf.set_color_range(self._config.get("color_detection", {}))
        sf.set_overlay_enabled(self._config.get("overlay", True))

        region = self._config.get("region")
        if isinstance(region, (list, tuple)) and len(region) == 4:
            self._region = tuple(int(v) for v in region)
            x, y, w, h = self._region
            sf.set_region_label(f"{w} × {h} at ({x}, {y})")

        for t in self._config.get("templates", []):
            if not t.get("path"):
                continue
            tmpl = normalize_template(t)
            if tmpl["path"].is_file():
                self._templates.append(tmpl)
            else:
                log.warning(f"Saved template missing, skipped: {tmpl['path']}")
        if self._templates:
            sf.set_template_list(self._templates)

    def _save_config_state(self):
        self._config["confidence"]  = self._settings_frame.get_confidence()
        self._config["click_delay"] = self._settings_frame.get_delay()
        self._config["overlay"]     = self._settings_frame.get_overlay_enabled()
        self._config["region"]      = list(self._region) if self._region else None
        self._config["templates"]   = [
            {"path": str(t["path"]), "pre_delay_ms": t["pre_delay_ms"]} for t in self._templates
        ]
        save_config(self._config)

    def _on_close(self):
        self._settings_frame.commit_pending()
        self._stop()
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self._save_config_state()
        self.destroy()
