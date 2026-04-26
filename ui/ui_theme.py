"""
UI theme helpers: shared colors, ttk styling, and toolbar logo loading.
"""

import tkinter as tk
from tkinter import ttk

import numpy as np
from PIL import Image, ImageTk

from core.backend import LOGO_FILE


C = {
    "bg_main":     "#f5f6f8",
    "bg_toolbar":  "#ffffff",
    "bg_sidebar":  "#f0f1f3",
    "bg_card":     "#ffffff",
    "bg_card_hv":  "#eaf4eb",
    "bg_player":   "#181a1b",
    "bg_gallery":  "#f5f6f8",
    "bg_thumb":    "#ffffff",
    "tx_primary":  "#1a1a1a",
    "tx_secondary":"#6b7280",
    "tx_green":    "#1e6e35",
    "tx_green_lt": "#2e9e4f",
    "tx_white":    "#ffffff",
    "border":      "#e2e5ea",
    "divider":     "#2e9e4f",
    "prog_bg":     "#e0e0e0",
    "prog_fill":   "#2e9e4f",
    "slot_bar":    "#1e1e1e",
    "slot_bar_tx": "#e8e8e8",
    "status_ok":   "#1e6e35",
    "status_warn": "#b45309",
    "status_err":  "#b91c1c",
}


def apply_ttk_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "TButton",
        background=C["bg_card"],
        foreground=C["tx_green"],
        borderwidth=1,
        relief="flat",
        padding=6,
        font=("Helvetica", 9, "bold"),
    )
    style.map(
        "TButton",
        background=[("active", C["bg_card_hv"])],
        foreground=[("active", C["tx_green"])],
    )
    style.configure(
        "TScrollbar",
        background=C["bg_sidebar"],
        troughcolor=C["bg_main"],
        arrowcolor=C["tx_secondary"],
    )
    style.configure("TSeparator", background=C["border"])
    style.configure(
        "TSpinbox",
        fieldbackground=C["bg_card"],
        background=C["bg_card"],
        foreground=C["tx_primary"],
        borderwidth=1,
    )


def load_logo(height_px: int = 44) -> "ImageTk.PhotoImage | None":
    if not LOGO_FILE.exists():
        return None
    try:
        img = Image.open(LOGO_FILE).convert("RGB")
        arr = np.array(img, dtype=np.int32)
        brightness = arr[:, :, 0] + arr[:, :, 1] + arr[:, :, 2]

        non_bg = brightness > 3
        ys, xs = np.where(non_bg)
        if not len(xs):
            return None

        pad = 20
        x1 = max(0, xs.min() - pad)
        x2 = min(img.width, xs.max() + pad)
        y1 = max(0, ys.min() - pad)
        y2 = min(img.height, ys.max() + pad)
        cropped = img.crop((x1, y1, x2, y2))

        arr_c = np.array(cropped, dtype=np.int32)
        rc, gc, bc = arr_c[:, :, 0], arr_c[:, :, 1], arr_c[:, :, 2]

        is_red = (rc > 100) & (gc < 50) & (bc < 60)
        inverted = (255 - arr_c).clip(0, 255).astype(np.uint8)
        inverted[is_red] = [210, 35, 35]

        result = Image.fromarray(inverted)
        aspect = result.width / result.height
        new_w = max(1, int(height_px * aspect))
        result = result.resize((new_w, height_px), Image.LANCZOS)
        return ImageTk.PhotoImage(result)
    except Exception as exc:
        print(f"Logo load error: {exc}")
        return None
