import io
from pathlib import Path
from PIL import Image
import customtkinter as ctk
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from utils.config import get_resource_path

def load_svg_icon(path: Path | str, size: tuple[int, int] = (16, 16)) -> ctk.CTkImage:
    """Loads an SVG file, converts it to a PIL Image, and returns a CTkImage."""
    resolved_path = str(get_resource_path(str(path)))
    drawing = svg2rlg(resolved_path)
    if drawing is None:
        return None
    
    # Render to a bytes buffer as PNG (bg defaults to black)
    png_data = renderPM.drawToString(drawing, fmt="PNG", bg=0x000000)
    img = Image.open(io.BytesIO(png_data))
    
    # Convert black background to transparent using image intensity as alpha
    gray = img.convert("L")
    solid = Image.new("RGBA", img.size, (229, 231, 235, 255))
    solid.putalpha(gray)
    img = solid
    
    # Resize nicely
    img = img.resize(size, Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)

def load_colored_svg(path: Path | str, size: tuple[int, int] = (16, 16), bg_hex: str = "#000000") -> ctk.CTkImage:
    """Loads an SVG file with its original colors and renders it onto a solid background color."""
    resolved_path = str(get_resource_path(str(path)))
    drawing = svg2rlg(resolved_path)
    if drawing is None:
        return None
    
    # Convert hex color to int for renderPM (e.g. "#1E293B" -> 0x1E293B)
    bg_int = int(bg_hex.lstrip('#'), 16)
    
    png_data = renderPM.drawToString(drawing, fmt="PNG", bg=bg_int)
    img = Image.open(io.BytesIO(png_data))
    
    # Resize nicely
    img = img.resize(size, Image.LANCZOS)
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)
