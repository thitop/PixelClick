"""
gui/theme.py — Design tokens for PixelClick.

Rules (keep these when adding UI):
  * One neutral family (cool slate). One accent (the logo blue). Nothing else
    is coloured except semantic status (ok / warn / err) used on text and dots.
  * Two corner radii: R_CTRL for anything you click or type in, R_PANEL for
    surfaces that contain things.
  * No emoji in the interface. Icons come from assets/icons only.
"""

import customtkinter as ctk

# Neutrals
BG       = "#0E1116"   # window
SURFACE  = "#151A21"   # panels
RAISED   = "#1C222B"   # inputs, secondary buttons, list rows
HOVER    = "#242B36"
BORDER   = "#2A323E"
TEXT     = "#E6E9EE"
MUTED    = "#9AA4B2"
DIM      = "#667082"

# The only accent
ACCENT       = "#2E86FF"
ACCENT_HOVER = "#1F6FE0"
ON_ACCENT    = "#FFFFFF"

# Semantic status (text / dots only)
OK   = "#3FB950"
WARN = "#D29922"
ERR  = "#F85149"

# Shape
R_CTRL  = 6
R_PANEL = 10

# Spacing (px)
PAD = 16
GAP = 8

FONT_FAMILY = "Segoe UI"


def font(size: int = 12, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(FONT_FAMILY, size, weight="bold" if bold else "normal")


def mono(size: int = 11) -> ctk.CTkFont:
    return ctk.CTkFont("Consolas", size)
