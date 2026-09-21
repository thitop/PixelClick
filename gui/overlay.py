import tkinter as tk
import customtkinter as ctk
import ctypes

class OverlayWindow(ctk.CTkToplevel):
    def __init__(self, master, box_color="#3B82F6", **kwargs):
        super().__init__(master, **kwargs)
        self.title("PixelClick Overlay")
        self._box_color = box_color

        # Get screen size
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")

        # Hide window decorations and make transparent
        self.overrideredirect(True)
        self.attributes("-transparentcolor", "black")
        self.attributes("-topmost", True)
        self.configure(fg_color="black")

        # Make it click-through (WS_EX_LAYERED | WS_EX_TRANSPARENT)
        hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x00080000 | 0x00000020)

        # Canvas for drawing bounding boxes
        self._canvas = tk.Canvas(self, bg="black", highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)

        self._rect = None
        
        # Start hidden
        self.withdraw()
        self._is_showing = False

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
            
        if not found:
            self.clear_target()
        else:
            if not self._rect:
                self._rect = self._canvas.create_rectangle(
                    x, y, x + w, y + h,
                    outline=self._box_color, width=4
                )
            else:
                self._canvas.coords(self._rect, x, y, x + w, y + h)
