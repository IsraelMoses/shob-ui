"""
UI theme helpers: shared colors, ttk styling, and toolbar logo loading.
"""

import os
import tkinter as tk
from tkinter import ttk
from pathlib import Path

from PIL import Image, ImageTk

from core.backend import LOGO_FILE


C = {
    "bg_main":     "#030b16",
    "bg_toolbar":  "#061427",
    "bg_sidebar":  "#081a31",
    "bg_card":     "#0d223d",
    "bg_card_hv":  "#143255",
    "bg_player":   "#020813",
    "bg_gallery":  "#061427",
    "bg_thumb":    "#0f2745",
    "tx_primary":  "#d6f4ff",
    "tx_secondary":"#88a9c4",
    "tx_green":    "#0cae56",
    "tx_green_lt": "#2ad074",
    "tx_white":    "#ffffff",
    "border":      "#1c3b5d",
    "divider":     "#00bff1",
    "prog_bg":     "#0f2745",
    "prog_fill":   "#00d6ff",
    "slot_bar":    "#0a1a2c",
    "slot_bar_tx": "#d8ebff",
    "status_ok":   "#22cf73",
    "status_warn": "#f7ad42",
    "status_err":  "#ff4d68",
}


def apply_ttk_style():
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "TButton",
        background=C["bg_card"],
        foreground=C["tx_primary"],
        borderwidth=1,
        relief="flat",
        padding=6,
        font=("Helvetica", 9, "bold"),
    )
    style.map(
        "TButton",
        background=[("active", C["bg_card_hv"])],
        foreground=[("active", C["tx_primary"])],
    )
    style.configure(
        "TScrollbar",
        background=C["bg_sidebar"],
        troughcolor=C["bg_sidebar"],
        arrowcolor=C["tx_primary"],
    )
    style.configure("TSeparator", background=C["border"])
    style.configure(
        "TSpinbox",
        fieldbackground=C["bg_card"],
        background=C["bg_toolbar"],
        foreground=C["tx_primary"],
        borderwidth=1,
    )
    style.map(
        "TSpinbox",
        fieldbackground=[("readonly", C["bg_card"])],
    )


def _first_existing_path(paths):
    for path in paths:
        if path and path.exists():
            return path
    return None


def _load_logo_image(path: Path, height_px: int) -> "ImageTk.PhotoImage | None":
    if not path or not path.exists():
        return None
    original_limit = Image.MAX_IMAGE_PIXELS
    try:
        # Trusted local logo file; allow loading large source images.
        Image.MAX_IMAGE_PIXELS = None
        result = Image.open(path).convert("RGBA")

        if "A" in result.getbands():
            bbox = result.getchannel("A").getbbox()
            if bbox:
                result = result.crop(bbox)

        max_w = max(int(height_px * 4), height_px)
        result.thumbnail((max_w, height_px), Image.LANCZOS)
        return ImageTk.PhotoImage(result)
    except Exception as exc:
        print(f"Logo load error ({path}): {exc}")
        return None
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit


def load_logo(height_px: int = 44) -> "ImageTk.PhotoImage | None":
    return _load_logo_image(LOGO_FILE, height_px)


def load_logo2(height_px: int = 44) -> "ImageTk.PhotoImage | None":
    env_path = os.environ.get("SHOB_LOGO2_FILE", "").strip()
    env_file = Path(env_path).expanduser() if env_path else None
    repo_root = LOGO_FILE.parent
    logo2_file = _first_existing_path((
        env_file,
        repo_root / "logo2.png",
        repo_root / "logo2.jpg",
        repo_root / "logo2.jpeg",
        repo_root / "logo2.webp",
        repo_root / "logo2",
    ))
    if not logo2_file:
        return None
    return _load_logo_image(logo2_file, height_px)


def load_title_banner(
    height_px: int = 84,
    width_px: int | None = None,
    stretch: bool = False,
    cover: bool = False,
    crop_to_content: bool = True,
) -> "ImageTk.PhotoImage | None":
    env_path = os.environ.get("SHOB_TITLE_BANNER_FILE", "").strip()
    env_file = Path(env_path).expanduser() if env_path else None
    downloads_file = Path.home() / "Downloads" / "ChatGPT Image May 7, 2026, 02_12_51 PM.png"
    desktop_file = Path.home() / "Desktop" / "ChatGPT Image May 7, 2026, 01_06_35 PM.png"
    local_file = LOGO_FILE.parent / "header_banner.png"
    banner_file = _first_existing_path((env_file, downloads_file, desktop_file, local_file))
    if not banner_file:
        return None

    original_limit = Image.MAX_IMAGE_PIXELS
    try:
        Image.MAX_IMAGE_PIXELS = None
        result = Image.open(banner_file).convert("RGBA")

        if crop_to_content:
            gray = result.convert("L")
            mask = gray.point(lambda p: 255 if p > 30 else 0)
            bbox = mask.getbbox()
            if bbox:
                x1, y1, x2, y2 = bbox
                bw = max(x2 - x1, 1)
                bh = max(y2 - y1, 1)
                x_pad = max(int(bw * 0.04), 12)
                y_pad_top = max(int(bh * 0.14), 12)
                y_pad_bottom = max(int(bh * 0.24), 18)

                crop_x1 = max(x1 - x_pad, 0)
                crop_y1 = max(y1 - y_pad_top, 0)
                crop_x2 = min(x2 + x_pad, result.width)
                crop_y2 = min(y2 + y_pad_bottom, result.height)
                result = result.crop((crop_x1, crop_y1, crop_x2, crop_y2))

        target_h = max(int(height_px), 24)
        target_w = max(int(width_px), 80) if width_px else None

        if stretch and target_w:
            result = result.resize((target_w, target_h), Image.LANCZOS)
        elif cover and target_w:
            scale = max(target_w / result.width, target_h / result.height)
            resized_w = max(int(result.width * scale), target_w)
            resized_h = max(int(result.height * scale), target_h)
            result = result.resize((resized_w, resized_h), Image.LANCZOS)

            left = max((resized_w - target_w) // 2, 0)
            top = max((resized_h - target_h) // 2, 0)
            result = result.crop((left, top, left + target_w, top + target_h))
        else:
            max_w = target_w if target_w else max(int(target_h * 8), target_h)
            result.thumbnail((max_w, target_h), Image.LANCZOS)

        return ImageTk.PhotoImage(result)
    except Exception as exc:
        print(f"Banner load error: {exc}")
        return None
    finally:
        Image.MAX_IMAGE_PIXELS = original_limit
