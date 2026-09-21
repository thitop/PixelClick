import tkinter as tk
import customtkinter as ctk

class MiniHUD(ctk.CTkToplevel):
    def __init__(self, master, on_start, on_stop, on_expand, icons, **kwargs):
        super().__init__(master, **kwargs)
        
        self.title("PixelClick HUD")
        self.geometry("260x90")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.85)
        self.configure(fg_color="#0F172A")
        
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_expand = on_expand
        self._icons = icons
        
        self._build_ui()
        self._setup_drag()
        
        self.withdraw()
        self._is_showing = False

    def _build_ui(self):
        container = ctk.CTkFrame(self, fg_color="#1E293B", corner_radius=10, border_color="#334155", border_width=1)
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        # Drag handle (Logo)
        drag_handle = ctk.CTkLabel(container, text="", image=self._icons.get("logo"), cursor="fleur")
        drag_handle.place(x=12, y=20)
        self._drag_handle = drag_handle
        
        # Status Label
        self._status_label = ctk.CTkLabel(
            container, text="Stopped", anchor="w", width=70,
            font=ctk.CTkFont("Segoe UI", 12, weight="bold"), text_color="#94A3B8"
        )
        self._status_label.place(x=45, y=20)
        
        # Buttons
        self._start_btn = ctk.CTkButton(
            container, text="", image=self._icons.get("play"), width=32, height=32, corner_radius=6,
            fg_color="#166534", hover_color="#15803D", command=self._start_pressed
        )
        self._start_btn.place(x=125, y=15)
        
        self._stop_btn = ctk.CTkButton(
            container, text="", image=self._icons.get("square"), width=32, height=32, corner_radius=6,
            fg_color="#1F2937", hover_color="#B91C1C", command=self._stop_pressed, state="disabled"
        )
        self._stop_btn.place(x=165, y=15)
        
        # Expand Button
        self._expand_btn = ctk.CTkButton(
            container, text="", image=self._icons.get("maximize") or self._icons.get("bar-chart"), width=32, height=32, corner_radius=6,
            fg_color="#374151", hover_color="#4B5563", command=self._expand_pressed
        )
        self._expand_btn.place(x=210, y=15)
        
        # Shortcut Label
        self._shortcut_label = ctk.CTkLabel(
            container, text="Hotkeys: F6 (Start)  •  F7 (Stop)",
            font=ctk.CTkFont("Segoe UI", 10), text_color="#64748B"
        )
        self._shortcut_label.place(x=45, y=55)
        
    def _setup_drag(self):
        # Allow dragging the window by clicking on the container or drag handle
        self._drag_handle.bind("<Button-1>", self._start_drag)
        self._drag_handle.bind("<B1-Motion>", self._do_drag)
        self.bind("<Button-1>", self._start_drag)
        self.bind("<B1-Motion>", self._do_drag)
        
    def _start_drag(self, event):
        self._x = event.x
        self._y = event.y

    def _do_drag(self, event):
        deltax = event.x - self._x
        deltay = event.y - self._y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def _start_pressed(self):
        self._on_start()

    def _stop_pressed(self):
        self._on_stop()
        
    def _expand_pressed(self):
        self._on_expand()

    def update_status(self, is_running: bool, clicks: int):
        if is_running:
            self._status_label.configure(text="Running", text_color="#22C55E")
            self._start_btn.configure(state="disabled", fg_color="#1F2937")
            self._stop_btn.configure(state="normal", fg_color="#7F1D1D")
        else:
            self._status_label.configure(text="Stopped", text_color="#94A3B8")
            self._start_btn.configure(state="normal", fg_color="#166534")
            self._stop_btn.configure(state="disabled", fg_color="#1F2937")

    def show(self):
        self.deiconify()
        self.attributes("-topmost", True)
        self._is_showing = True

    def hide(self):
        self.withdraw()
        self._is_showing = False
