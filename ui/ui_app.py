"""
Main Tk application shell that composes the UI feature modules.
"""

from datetime import datetime, timedelta
import ctypes
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core.backend import (
    BASE_DIR,
    add_device_if_missing,
    add_device,
    load_camera_profile,
    load_devices,
    remove_device,
    save_camera_profile,
    save_camera_connection_status,
)
from core.gallery_store import extract_video_thumbnail, gallery_items_for, save_to_gallery
from core.gallery_store import export_images_for, image_items_for
from core.rtsp_service import make_target, test_rtsp_connection

from .ui_devices import CameraCredentialsDialog, DeviceDialog
from .ui_gallery import GalleryWindow
from .ui_live_stream import LiveStreamSlot
from .ui_media import MediaSlot
from .ui_theme import C, apply_ttk_style, load_logo, load_logo2


DEVICE_UI = {
    "panel": "#07111c",
    "toolbar": "#09121c",
    "card": "#09131d",
    "card_hover": "#0c1c29",
    "card_flash": "#2a1b1b",
    "card_flash_hover": "#3a2323",
    "border": "#1b2a36",
    "border_hover": "#28645d",
    "primary": "#2dd4bf",
    "primary_dim": "#193b3a",
    "foreground": "#e7f0f5",
    "muted": "#7f95a5",
    "online": "#34d399",
    "live_fill": "#0b342e",
    "live_fill_hover": "#0e483e",
    "live_border": "#1d6658",
    "live_border_hover": "#2fae92",
    "live_text": "#38e6bd",
    "export_fill": "#36290d",
    "export_fill_hover": "#4a380f",
    "export_border": "#73541a",
    "export_border_hover": "#a77b1d",
    "export_text": "#f2b72e",
    "delete_fill": "#371821",
    "delete_fill_hover": "#4b1f2b",
    "delete_border": "#743040",
    "delete_border_hover": "#a24355",
    "delete_text": "#f36f7f",
}


def _enable_windows_dpi_awareness():
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _create_smooth_rounded_rect(
    canvas: tk.Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    radius: int = 10,
    **kwargs,
):
    radius = max(0, min(radius, (x2 - x1) // 2, (y2 - y1) // 2))
    points = [
        x1 + radius, y1,
        x1 + radius, y1,
        x2 - radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, splinesteps=18, **kwargs)


class RoundedActionButton(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        command,
        fill_color: str,
        hover_fill_color: str,
        press_fill_color: str,
        border_color: str,
        border_hover_color: str | None = None,
        text_color: str = "#ffffff",
        icon_text: str = "",
        icon_color: str | None = None,
        icon_box_fill_color: str | None = None,
        width: int = 112,
        height: int = 34,
        radius: int = 8,
        font=("Segoe UI", 9, "bold"),
        icon_font=("Segoe UI", 9, "bold"),
    ):
        super().__init__(
            master,
            width=width, 
            height=height,
            bd=0,
            highlightthickness=0,
            bg=master.cget("bg"),
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._fill_color = fill_color
        self._hover_fill_color = hover_fill_color
        self._press_fill_color = press_fill_color
        self._border_color = border_color
        self._border_hover_color = border_hover_color or border_color
        self._text_color = text_color
        self._icon_text = icon_text
        self._icon_color = icon_color or text_color
        self._icon_box_fill_color = icon_box_fill_color
        self._radius = radius
        self._font = font
        self._icon_font = icon_font
        self._state = "normal"

        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

    def set_container_bg(self, bg_color: str):
        self.configure(bg=bg_color)

    def _on_enter(self, _event):
        self._state = "hover"
        self._draw()

    def _on_leave(self, _event):
        self._state = "normal"
        self._draw()

    def _on_press(self, _event):
        self._state = "press"
        self._draw()
        return "break"

    def _on_release(self, event):
        self._state = "hover"
        self._draw()
        if self._command:
            x, y = event.x, event.y
            if 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height():
                self._command()
        return "break"

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), int(self["width"]))
        h = max(self.winfo_height(), int(self["height"]))

        if self._state == "press":
            fill = self._press_fill_color
            border = self._border_hover_color
        elif self._state == "hover":
            fill = self._hover_fill_color
            border = self._border_hover_color
        else:
            fill = self._fill_color
            border = self._border_color

        self._rounded_rect(
            0,
            0,
            w - 1,
            h - 1,
            radius=self._radius,
            fill=fill,
            outline=border,
            width=1,
        )
        text_x = w // 2
        text_anchor = "center"
        if self._icon_text:
            icon_size = max(min(h - 14, 15), 12)
            icon_left = 10
            if self._icon_box_fill_color is not None:
                icon_top = (h - icon_size) // 2
                self._rounded_rect(
                    icon_left,
                    icon_top,
                    icon_left + icon_size,
                    icon_top + icon_size,
                    radius=4,
                    fill=self._icon_box_fill_color,
                    outline=border,
                    width=1,
                )
                icon_x = icon_left + (icon_size // 2)
                text_x = icon_left + icon_size + 8
            else:
                icon_x = icon_left
                text_x = icon_left + icon_size + 6

            self.create_text(
                icon_x,
                h // 2,
                text=self._icon_text,
                fill=self._icon_color,
                font=self._icon_font,
                anchor="w" if self._icon_box_fill_color is None else "center",
            )
            text_anchor = "w"

        self.create_text(
            text_x,
            h // 2,
            text=self._text,
            fill=self._text_color,
            font=self._font,
            anchor=text_anchor,
        )

    def _rounded_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        return _create_smooth_rounded_rect(self, x1, y1, x2, y2, radius, **kwargs)


class ToolbarActionButton(tk.Canvas):
    def __init__(
        self,
        master,
        text: str,
        icon_text: str,
        command,
        width: int = 118,
        height: int = 42,
    ):
        super().__init__(
            master,
            width=width,
            height=height,
            bd=0,
            highlightthickness=0,
            bg=master.cget("bg"),
            cursor="hand2",
        )
        self._text = text
        self._icon_text = icon_text
        self._command = command
        self._hover = False
        self._font = ("Segoe UI", 9, "bold")
        self._icon_font = ("Segoe MDL2 Assets", 11)
        self._draw()
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonRelease-1>", self._on_release)

    def _on_enter(self, _event):
        self._hover = True
        self._draw()

    def _on_leave(self, _event):
        self._hover = False
        self._draw()

    def _on_release(self, event):
        if self._command and 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height():
            self._command()
        return "break"

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), int(self["width"]))
        h = max(self.winfo_height(), int(self["height"]))
        fill = "#0b2428" if self._hover else self.cget("bg")
        outline = "#174947" if self._hover else self.cget("bg")
        _create_smooth_rounded_rect(
            self,
            1,
            4,
            w - 1,
            h - 4,
            radius=9,
            fill=fill,
            outline=outline,
            width=1,
        )
        center_x = w // 2
        self.create_text(
            center_x - 24,
            h // 2,
            text=self._icon_text,
            fill=DEVICE_UI["primary"],
            font=self._icon_font,
            anchor="center",
        )
        self.create_text(
            center_x - 8,
            h // 2,
            text=self._text,
            fill=DEVICE_UI["primary"],
            font=self._font,
            anchor="w",
        )


class SecCamApp(tk.Tk):
    SIDEBAR_W = 320

    def __init__(self):
        _enable_windows_dpi_awareness()
        super().__init__()
        apply_ttk_style()
        self.title("Security Camera Player")
        self.geometry("1320x800")
        self.minsize(820, 520)
        self.configure(bg=C["bg_main"])
        self._display_secs = tk.IntVar(value=10)
        self._active_slots = []
        self._gallery_windows = {}
        self._logo_photo = None
        self._logo2_photo = None
        self._devices_title_var = tk.StringVar(value="DEVICES")
        self._devices_count_var = tk.StringVar(value="0 connected")
        self._flash_device_uuids = set()
        self._flash_clear_after_ids = {}
        self._banner_window = None
        self._banner_hide_after_id = None
        self._banner_anim_after_id = None
        self._title_banner_photo = None
        self._title_banner_label = None
        self._title_subtitle_label = None
        self._title_box = None
        self._title_banner_size = (0, 0)
        self._auto_refresh_interval_ms = 60_000
        self._auto_refresh_after_id = None
        self._pending_credential_prompts = set()
        self._backend_log_file = BASE_DIR / "logs" / "backend.log"
        self._logs_window = None
        self._logs_text = None
        self._logs_refresh_after_id = None
        self._live_stream_slots = {}
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._schedule_auto_refresh()

    def _build_ui(self):
        self._build_toolbar()
        tk.Frame(self, bg=C["divider"], height=2).pack(fill=tk.X)

        body = tk.Frame(self, bg=C["bg_main"])
        body.pack(fill=tk.BOTH, expand=True)

        sidebar_outer = tk.Frame(body, bg=C["border"], width=self.SIDEBAR_W + 1)
        sidebar_outer.pack(side=tk.RIGHT, fill=tk.Y)
        sidebar_outer.pack_propagate(False)
        sidebar = tk.Frame(sidebar_outer, bg=C["bg_sidebar"], width=self.SIDEBAR_W)
        sidebar.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._build_sidebar(sidebar)

        self._player_frame = tk.Frame(body, bg=C["bg_player"])
        self._player_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._waiting_lbl = tk.Label(
            self._player_frame,
            text="Waiting for messages...",
            font=("Helvetica", 20),
            bg=C["bg_player"],
            fg="#3c5671",
        )
        self._waiting_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _build_toolbar(self):
        toolbar = tk.Frame(self, bg=C["bg_toolbar"], height=168)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)

        brand = tk.Frame(toolbar, bg=C["bg_toolbar"])
        brand.pack(side=tk.LEFT, padx=(12, 10), pady=10)

        logo_photo = load_logo(height_px=86)
        logo2_photo = load_logo2(height_px=86)
        if logo_photo:
            self._logo_photo = logo_photo
            lbl = tk.Label(brand, image=logo_photo, bg=C["bg_toolbar"], bd=0)
            lbl.image = logo_photo
            lbl.pack(side=tk.LEFT)
            if logo2_photo:
                self._logo2_photo = logo2_photo
                lbl2 = tk.Label(brand, image=logo2_photo, bg=C["bg_toolbar"], bd=0)
                lbl2.image = logo2_photo
                lbl2.pack(side=tk.LEFT, padx=(10, 0))
        elif logo2_photo:
            self._logo2_photo = logo2_photo
            lbl2 = tk.Label(brand, image=logo2_photo, bg=C["bg_toolbar"], bd=0)
            lbl2.image = logo2_photo
            lbl2.pack(side=tk.LEFT)
        else:
            tk.Label(
                brand,
                text="SC",
                font=("Helvetica", 12, "bold"),
                bg=C["bg_toolbar"],
                fg=C["tx_green"],
            ).pack(side=tk.LEFT)

        right_info = tk.Frame(toolbar, bg=C["bg_toolbar"])
        right_info.pack(side=tk.RIGHT, padx=(0, 10), pady=20)

        tk.Label(
            right_info,
            text="Photo display (s):",
            font=("Helvetica", 9),
            bg=C["bg_toolbar"],
            fg=C["tx_secondary"],
        ).pack(side=tk.RIGHT, padx=(6, 0))
        ttk.Spinbox(
            right_info,
            from_=1,
            to=300,
            textvariable=self._display_secs,
            width=5,
            font=("Helvetica", 9),
        ).pack(side=tk.RIGHT, padx=(0, 10))

        tk.Frame(right_info, bg=C["border"], width=1, height=64).pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=8,
        )
        self._srv_lbl = tk.Label(
            right_info,
            text="Starting...",
            font=("Helvetica", 9),
            bg=C["bg_toolbar"],
            fg=C["status_warn"],
        )
        self._srv_lbl.pack(side=tk.RIGHT, padx=8)

        title_wrap = tk.Frame(toolbar, bg=C["bg_toolbar"])
        title_wrap.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 0))
        self._title_box = tk.Frame(title_wrap, bg=C["bg_toolbar"])
        self._title_box.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self._title_banner_label = tk.Label(
            self._title_box,
            bg=C["bg_toolbar"],
            bd=0,
            anchor="center",
            justify="center",
        )
        self._title_banner_label.pack(side=tk.TOP, fill=tk.X, expand=True, pady=(8, 0))
        self._title_subtitle_label = tk.Label(
            self._title_box,
            bg=C["bg_toolbar"],
            bd=0,
            anchor="center",
            justify="center",
        )
        self._title_subtitle_label.pack(side=tk.TOP, fill=tk.X, pady=(0, 10))
        self._title_box.bind("<Configure>", self._on_title_banner_resize)
        self.after(10, self._render_title_banner)

    def _on_title_banner_resize(self, _event):
        self._render_title_banner()

    def _render_title_banner(self):
        if not self._title_box or not self._title_banner_label or not self._title_subtitle_label:
            return
        if (
            not self._title_box.winfo_exists()
            or not self._title_banner_label.winfo_exists()
            or not self._title_subtitle_label.winfo_exists()
        ):
            return

        width = max(self._title_box.winfo_width(), 80)
        height = max(self._title_box.winfo_height(), 40)
        current_size = (width, height)
        if current_size == self._title_banner_size:
            return
        self._title_banner_size = current_size

        font_size = max(28, min(60, int(height * 0.45)))
        subtitle_size = max(12, min(22, int(font_size * 0.38)))
        self._title_banner_photo = None
        self._title_banner_label.configure(
            image="",
            text="\u05E9\u05D5\"\u05D1 \u05E8\u05E4\u05D0\u05D9\u05DD",
            font=("Segoe UI", font_size, "bold"),
            fg="#ffffff",
            bg=C["bg_toolbar"],
        )
        self._title_banner_label.image = None
        self._title_subtitle_label.configure(
            text=" - \u05DE\u05D3\u05D5\u05E8 \u05E2\u05D5\u05DE\u05E7 - ",
            font=("Segoe UI", subtitle_size, "normal"),
            fg=C["tx_green"],
            bg=C["bg_toolbar"],
        )

    def _build_sidebar(self, parent):
        parent.configure(bg=DEVICE_UI["panel"])

        hdr = tk.Frame(parent, bg=DEVICE_UI["panel"])
        hdr.pack(fill=tk.X, padx=28, pady=(14, 8))

        monitor_icon = tk.Canvas(
            hdr,
            width=34,
            height=34,
            bg=DEVICE_UI["panel"],
            bd=0,
            highlightthickness=0,
        )
        monitor_icon.pack(side=tk.LEFT, padx=(0, 10))
        _create_smooth_rounded_rect(
            monitor_icon,
            1,
            1,
            33,
            33,
            radius=9,
            fill="#092326",
            outline="#174b49",
            width=1,
        )
        monitor_icon.create_rectangle(10, 9, 24, 20, outline=DEVICE_UI["primary"], width=1)
        monitor_icon.create_line(17, 20, 17, 24, fill=DEVICE_UI["primary"], width=1)
        monitor_icon.create_line(13, 24, 21, 24, fill=DEVICE_UI["primary"], width=1)

        title_stack = tk.Frame(hdr, bg=DEVICE_UI["panel"])
        title_stack.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(
            title_stack,
            textvariable=self._devices_title_var,
            font=("Segoe UI", 10, "bold"),
            bg=DEVICE_UI["panel"],
            fg=DEVICE_UI["primary"],
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            title_stack,
            textvariable=self._devices_count_var,
            font=("Segoe UI", 9),
            bg=DEVICE_UI["panel"],
            fg=DEVICE_UI["muted"],
            anchor="w",
        ).pack(fill=tk.X)

        scroll_f = tk.Frame(parent, bg=DEVICE_UI["panel"])
        scroll_f.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(scroll_f, orient="vertical", style="Vertical.TScrollbar")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dev_canvas = tk.Canvas(
            scroll_f,
            bg=DEVICE_UI["panel"],
            highlightthickness=0,
            yscrollcommand=vsb.set,
        )
        self._dev_canvas.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self._dev_canvas.yview)
        self._dev_list = tk.Frame(self._dev_canvas, bg=DEVICE_UI["panel"])
        self._dev_window_id = self._dev_canvas.create_window(
            (0, 0),
            window=self._dev_list,
            anchor="nw",
        )
        self._dev_list.bind(
            "<Configure>",
            lambda e: self._dev_canvas.configure(scrollregion=self._dev_canvas.bbox("all")),
        )
        self._dev_canvas.bind("<Configure>", self._resize_device_list_canvas)

        tk.Frame(parent, bg=DEVICE_UI["border"], height=1).pack(fill=tk.X)
        actions_outer = tk.Frame(parent, bg=DEVICE_UI["toolbar"])
        actions_outer.pack(fill=tk.X)
        actions = tk.Frame(actions_outer, bg=DEVICE_UI["toolbar"])
        actions.pack(fill=tk.X, padx=18, pady=10)

        refresh_btn = ToolbarActionButton(
            actions,
            text="Refresh",
            icon_text="\ue72c",
            command=self._manual_refresh_devices,
        )
        refresh_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Frame(actions, bg=DEVICE_UI["border"], width=1).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=8,
            pady=8,
        )

        logs_btn = ToolbarActionButton(
            actions,
            text="Logs",
            icon_text="\ue8a5",
            command=self._open_logs_window,
        )
        logs_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._refresh_device_list()

    def _resize_device_list_canvas(self, event):
        self._dev_canvas.itemconfigure(self._dev_window_id, width=event.width)

    def _refresh_device_list(self, preferred_uuid=None):
        devices = load_devices()
        if preferred_uuid:
            for idx, dev in enumerate(devices):
                if dev.get("uuid") == preferred_uuid:
                    devices.insert(0, devices.pop(idx))
                    break
        self._devices_title_var.set("DEVICES")
        self._devices_count_var.set(f"{len(devices)} connected")

        for widget in self._dev_list.winfo_children():
            widget.destroy()

        for dev in devices:
            self._build_device_card(dev)

    def _manual_refresh_devices(self):
        self._refresh_device_list()
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self):
        if self._auto_refresh_after_id:
            try:
                self.after_cancel(self._auto_refresh_after_id)
            except Exception:
                pass
        self._auto_refresh_after_id = self.after(
            self._auto_refresh_interval_ms,
            self._auto_refresh_tick,
        )

    def _auto_refresh_tick(self):
        self._auto_refresh_after_id = None
        if not self.winfo_exists():
            return
        self._refresh_device_list()
        self._schedule_auto_refresh()

    def _open_logs_window(self):
        if self._logs_window and self._logs_window.winfo_exists():
            self._logs_window.lift()
            self._logs_window.focus_force()
            self._refresh_logs_window()
            return

        win = tk.Toplevel(self)
        win.title("Shob Backend Logs")
        win.configure(bg=C["bg_toolbar"])
        win.geometry("980x560")
        win.minsize(700, 380)
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", self._close_logs_window)
        self._logs_window = win

        header = tk.Frame(win, bg=C["bg_toolbar"], padx=12, pady=10)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Backend Logs",
            font=("Segoe UI", 11, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_primary"],
        ).pack(side=tk.LEFT)
        ttk.Button(header, text="Refresh", command=self._refresh_logs_window).pack(side=tk.RIGHT)

        path_label = tk.Label(
            win,
            text=str(self._backend_log_file),
            font=("Segoe UI", 8),
            bg=C["bg_toolbar"],
            fg=C["tx_secondary"],
            anchor="w",
            justify="left",
            padx=12,
        )
        path_label.pack(fill=tk.X)

        self._logs_text = scrolledtext.ScrolledText(
            win,
            bg=C["bg_player"],
            fg="#a7f2c8",
            insertbackground="#a7f2c8",
            relief=tk.FLAT,
            bd=0,
            wrap=tk.NONE,
            font=("Consolas", 9),
        )
        self._logs_text.pack(fill=tk.BOTH, expand=True, padx=12, pady=(8, 12))
        self._logs_text.configure(state=tk.DISABLED)
        self._refresh_logs_window()
        win.update_idletasks()
        self._center_child_window(win)

    def _read_backend_logs_tail(self, max_bytes: int = 220_000) -> str:
        try:
            if not self._backend_log_file.exists():
                return "No log file yet. Waiting for backend activity...\n"

            file_size = self._backend_log_file.stat().st_size
            start = max(file_size - max_bytes, 0)
            with self._backend_log_file.open("rb") as f:
                f.seek(start)
                data = f.read()

            text = data.decode("utf-8", errors="replace")
            if start > 0 and "\n" in text:
                text = text.split("\n", 1)[1]
            return text or "Log file is currently empty.\n"
        except Exception as exc:
            return f"Could not read backend logs: {exc}\n"

    def _refresh_logs_window(self):
        if not self._logs_window or not self._logs_window.winfo_exists() or not self._logs_text:
            self._close_logs_window()
            return

        text = self._read_backend_logs_tail()
        self._logs_text.configure(state=tk.NORMAL)
        self._logs_text.delete("1.0", tk.END)
        self._logs_text.insert("1.0", text)
        self._logs_text.see(tk.END)
        self._logs_text.configure(state=tk.DISABLED)

        if self._logs_refresh_after_id:
            try:
                self.after_cancel(self._logs_refresh_after_id)
            except Exception:
                pass
        self._logs_refresh_after_id = self.after(1500, self._refresh_logs_window)

    def _close_logs_window(self):
        if self._logs_refresh_after_id:
            try:
                self.after_cancel(self._logs_refresh_after_id)
            except Exception:
                pass
            self._logs_refresh_after_id = None

        if self._logs_window and self._logs_window.winfo_exists():
            self._logs_window.destroy()

        self._logs_window = None
        self._logs_text = None

    def _build_device_card(self, dev):
        items = gallery_items_for(dev["uuid"])
        items_count = len(items)
        card_canvas = tk.Canvas(
            self._dev_list,
            bg=DEVICE_UI["panel"],
            bd=0,
            highlightthickness=0,
            height=108,
            cursor="hand2",
        )
        card_canvas.pack(fill=tk.X, padx=12, pady=3)

        card = tk.Frame(card_canvas, bg=DEVICE_UI["card"])
        card_window = card_canvas.create_window(12, 8, window=card, anchor="nw")

        content = tk.Frame(card, bg=DEVICE_UI["card"], padx=9, pady=10)
        content.pack(fill=tk.X)
        content.grid_columnconfigure(0, weight=1, minsize=132)

        info = tk.Frame(content, bg=DEVICE_UI["card"])
        info.grid(row=0, column=0, sticky="nsew")
        actions = tk.Frame(content, bg=DEVICE_UI["card"])
        actions.grid(row=0, column=1, sticky="e", padx=(7, 0))

        name_row = tk.Frame(info, bg=DEVICE_UI["card"])
        name_row.pack(fill=tk.X, pady=(0, 2))
        status_dot = tk.Canvas(
            name_row,
            width=10,
            height=10,
            bg=DEVICE_UI["card"],
            bd=0,
            highlightthickness=0,
        )
        status_dot.pack(side=tk.LEFT, padx=(0, 6), pady=(2, 0))
        status_dot.create_oval(2, 2, 8, 8, fill=DEVICE_UI["online"], outline="")

        name_lbl = tk.Label(
            name_row,
            text=dev["name"],
            font=("Segoe UI", 12, "bold"),
            bg=DEVICE_UI["card"],
            fg=DEVICE_UI["foreground"],
            anchor="w",
        )
        name_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ip_row = tk.Frame(info, bg=DEVICE_UI["card"])
        ip_row.pack(fill=tk.X, pady=(3, 0))
        wifi_icon = tk.Label(
            ip_row,
            text="\ue701",
            font=("Segoe MDL2 Assets", 11),
            bg=DEVICE_UI["card"],
            fg=DEVICE_UI["muted"],
            anchor="center",
            width=2,
        )
        wifi_icon.pack(side=tk.LEFT, padx=(0, 7))

        ip_lbl = tk.Label(
            ip_row,
            text=dev["ip"],
            font=("Consolas", 10),
            bg=DEVICE_UI["card"],
            fg="#b7c9d4",
            anchor="w",
        )
        ip_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        gallery_row = tk.Frame(info, bg=DEVICE_UI["card"])
        gallery_row.pack(fill=tk.X, pady=(3, 0))
        gallery_icon = tk.Label(
            gallery_row,
            text="\ue8b9",
            font=("Segoe MDL2 Assets", 11),
            bg=DEVICE_UI["card"],
            fg=DEVICE_UI["muted"],
            anchor="center",
            width=2,
        )
        gallery_icon.pack(side=tk.LEFT, padx=(0, 7))

        items_lbl = tk.Label(
            gallery_row,
            text=f"{items_count} items in gallery",
            font=("Segoe UI", 10),
            bg=DEVICE_UI["card"],
            fg="#b7c9d4",
            anchor="w",
        )
        items_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)

        live_btn = RoundedActionButton(
            actions,
            text="Live Stream",
            command=lambda d=dev: self._start_live_stream_for_device(d),
            fill_color=DEVICE_UI["live_fill"],
            hover_fill_color=DEVICE_UI["live_fill_hover"],
            press_fill_color="#092b26",
            border_color=DEVICE_UI["live_border"],
            border_hover_color=DEVICE_UI["live_border_hover"],
            text_color=DEVICE_UI["live_text"],
            icon_text="\ue768",
            icon_color=DEVICE_UI["live_text"],
            icon_box_fill_color=None,
            width=104,
            height=24,
            radius=8,
            font=("Segoe UI", 8, "bold"),
            icon_font=("Segoe MDL2 Assets", 9),
        )
        live_btn.pack(side=tk.TOP, fill=tk.X)

        export_btn = RoundedActionButton(
            actions,
            text="Export Photos",
            command=lambda d=dev: self._export_device_images(d),
            fill_color=DEVICE_UI["export_fill"],
            hover_fill_color=DEVICE_UI["export_fill_hover"],
            press_fill_color="#2d2109",
            border_color=DEVICE_UI["export_border"],
            border_hover_color=DEVICE_UI["export_border_hover"],
            text_color=DEVICE_UI["export_text"],
            icon_text="\ue896",
            icon_color=DEVICE_UI["export_text"],
            icon_box_fill_color=None,
            width=104,
            height=24,
            radius=8,
            font=("Segoe UI", 8, "bold"),
            icon_font=("Segoe MDL2 Assets", 9),
        )
        export_btn.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        delete_btn = RoundedActionButton(
            actions,
            text="Delete",
            command=lambda d=dev: self._remove_device(d),
            fill_color=DEVICE_UI["delete_fill"],
            hover_fill_color=DEVICE_UI["delete_fill_hover"],
            press_fill_color="#2d121a",
            border_color=DEVICE_UI["delete_border"],
            border_hover_color=DEVICE_UI["delete_border_hover"],
            text_color=DEVICE_UI["delete_text"],
            icon_text="\ue74d",
            icon_color=DEVICE_UI["delete_text"],
            icon_box_fill_color=None,
            width=104,
            height=24,
            radius=8,
            font=("Segoe UI", 8, "bold"),
            icon_font=("Segoe MDL2 Assets", 9),
        )
        delete_btn.pack(side=tk.TOP, fill=tk.X, pady=(5, 0))

        card.update_idletasks()
        card_canvas.configure(height=card.winfo_reqheight() + 10)

        hover_widgets = [
            card,
            content,
            info,
            actions,
            name_row,
            ip_row,
            gallery_row,
            status_dot,
            wifi_icon,
            gallery_icon,
            name_lbl,
            ip_lbl,
            items_lbl,
        ]
        hover = {"on": False}
        flashing = dev["uuid"] in self._flash_device_uuids
        base_bg = DEVICE_UI["card_flash"] if flashing else DEVICE_UI["card"]
        hover_bg = DEVICE_UI["card_flash_hover"] if flashing else DEVICE_UI["card_hover"]

        for widget in hover_widgets:
            widget.configure(bg=base_bg)
        live_btn.set_container_bg(base_bg)
        export_btn.set_container_bg(base_bg)
        delete_btn.set_container_bg(base_bg)

        def _draw_card_background():
            width = max(card_canvas.winfo_width(), 80)
            height = max(card_canvas.winfo_height(), 80)
            fill = hover_bg if hover["on"] else base_bg
            outline = "#a24355" if flashing else (DEVICE_UI["border_hover"] if hover["on"] else DEVICE_UI["border"])
            card_canvas.delete("card_bg")
            self._rounded_rect(
                card_canvas,
                0,
                2,
                width - 1,
                height - 3,
                radius=10,
                fill=fill,
                outline=outline,
                width=1,
                tags="card_bg",
            )
            if hover["on"] and not flashing:
                self._rounded_rect(
                    card_canvas,
                    1,
                    3,
                    width - 2,
                    height - 4,
                    radius=10,
                    fill="",
                    outline="#123d3a",
                    width=1,
                    tags="card_bg",
                )
            card_canvas.tag_lower("card_bg")
            card_canvas.coords(card_window, 12, 8)
            card_canvas.itemconfigure(card_window, width=max(width - 24, 120))
            card_canvas.tag_raise(card_window)

        def _set_card_bg(bg_color: str):
            for widget in hover_widgets:
                widget.configure(bg=bg_color)
            live_btn.set_container_bg(bg_color)
            export_btn.set_container_bg(bg_color)
            delete_btn.set_container_bg(bg_color)

        def _enter(_event):
            hover["on"] = True
            _draw_card_background()
            _set_card_bg(hover_bg)

        def _leave(_event):
            hover["on"] = False
            _draw_card_background()
            _set_card_bg(base_bg)

        card_canvas.bind("<Configure>", lambda _e: _draw_card_background())
        _draw_card_background()

        clickable = [
            card_canvas,
            card,
            content,
            info,
            name_row,
            ip_row,
            gallery_row,
            status_dot,
            wifi_icon,
            gallery_icon,
            name_lbl,
            ip_lbl,
            items_lbl,
        ]
        for widget in clickable:
            widget.bind("<Button-1>", lambda _e, d=dev: self._open_gallery(d))
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)

        for btn in (live_btn, export_btn, delete_btn):
            btn.bind("<Enter>", _enter, add="+")
            btn.bind("<Leave>", _leave, add="+")

    def _rounded_rect(
        self,
        canvas: tk.Canvas,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        radius: int = 10,
        **kwargs,
    ):
        return _create_smooth_rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs)

    def _build_device_status(self, latest_received):
        if not latest_received:
            return "No activity", "Last seen: never", "#9aa0aa"

        try:
            seen_at = datetime.fromisoformat(str(latest_received))
        except ValueError:
            return "No activity", "Last seen: unknown", "#9aa0aa"

        now = datetime.now(seen_at.tzinfo) if seen_at.tzinfo else datetime.now()
        delta = now - seen_at
        if delta < timedelta(seconds=0):
            delta = timedelta(seconds=0)

        age_text = self._format_age(delta)
        if delta <= timedelta(minutes=2):
            return "Online", f"Last seen: {age_text}", C["status_ok"]
        if delta <= timedelta(minutes=15):
            return "Active", f"Last seen: {age_text}", C["tx_green_lt"]
        return "No activity", f"Last seen: {age_text}", "#9aa0aa"

    def _format_age(self, delta: timedelta) -> str:
        total = int(delta.total_seconds())
        if total <= 5:
            return "just now"
        if total < 60:
            return f"{total}s ago"
        minutes = total // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"

    def _flash_device_card(self, uuid: str, duration_ms: int = 5000):
        if not uuid:
            return
        self._flash_device_uuids.add(uuid)
        self._refresh_device_list()

        prev_after = self._flash_clear_after_ids.get(uuid)
        if prev_after:
            try:
                self.after_cancel(prev_after)
            except Exception:
                pass

        self._flash_clear_after_ids[uuid] = self.after(
            duration_ms,
            lambda u=uuid: self._clear_device_flash(u),
        )

    def _clear_device_flash(self, uuid: str):
        self._flash_clear_after_ids.pop(uuid, None)
        if uuid not in self._flash_device_uuids:
            return
        self._flash_device_uuids.discard(uuid)
        self._refresh_device_list()

    def _show_top_notice(
        self,
        title: str,
        detail: str,
        tone: str = "ok",
        duration_ms: int = 7000,
    ):
        self._hide_top_notice(immediate=True)
        self.update_idletasks()

        palette = {
            "ok": {"fill": "#18a34a", "outline": "#0f7f37", "title": "#ffffff", "detail": "#e8fff0"},
            "alert": {"fill": "#ffecec", "outline": "#c1121f", "title": "#8b1111", "detail": "#5a1111"},
            "warn": {"fill": "#fff1d6", "outline": "#b45309", "title": "#92400e", "detail": "#7c5a2e"},
            "err": {"fill": "#ffe0e0", "outline": "#b91c1c", "title": "#991b1b", "detail": "#7a2e2e"},
        }
        colors = palette.get(tone, palette["ok"])

        notice = tk.Toplevel(self)
        notice.overrideredirect(True)
        notice.attributes("-topmost", True)

        transparent_key = "#ff00ff"
        notice.configure(bg=transparent_key)
        try:
            notice.wm_attributes("-transparentcolor", transparent_key)
        except Exception:
            transparent_key = self.cget("bg")
            notice.configure(bg=transparent_key)

        width = max(min(self.winfo_width() - 36, 600), 360)
        height = 86
        canvas = tk.Canvas(
            notice,
            width=width,
            height=height,
            bg=transparent_key,
            bd=0,
            highlightthickness=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)

        self._rounded_rect(
            canvas,
            2,
            2,
            width - 2,
            height - 2,
            radius=14,
            fill=colors["fill"],
            outline=colors["outline"],
            width=4,
        )
        canvas.create_text(
            18,
            30,
            anchor="w",
            text=title,
            fill=colors["title"],
            font=("Segoe UI", 12, "bold"),
            width=width - 36,
        )
        canvas.create_text(
            18,
            60,
            anchor="w",
            text=detail,
            fill=colors["detail"],
            font=("Segoe UI", 10, "bold"),
            width=width - 36,
        )

        x = self.winfo_rootx() + max((self.winfo_width() - width) // 2, 0)
        target_y = self.winfo_rooty() + 8
        start_y = self.winfo_rooty() - height - 12
        notice.geometry(f"{width}x{height}+{x}+{start_y}")

        self._banner_window = notice
        self._banner_hide_after_id = None
        self._banner_anim_after_id = None

        def start_notice_timers():
            self._banner_hide_after_id = self.after(duration_ms, self._hide_top_notice)

        def slide_in(current_y):
            if not self._banner_window or not self._banner_window.winfo_exists():
                return
            if current_y >= target_y:
                self._banner_window.geometry(f"{width}x{height}+{x}+{target_y}")
                start_notice_timers()
                return
            next_y = min(current_y + 16, target_y)
            self._banner_window.geometry(f"{width}x{height}+{x}+{next_y}")
            self._banner_anim_after_id = self.after(12, lambda: slide_in(next_y))

        slide_in(start_y)

    def _hide_top_notice(self, immediate: bool = False):
        if self._banner_hide_after_id:
            try:
                self.after_cancel(self._banner_hide_after_id)
            except Exception:
                pass
            self._banner_hide_after_id = None

        if self._banner_anim_after_id:
            try:
                self.after_cancel(self._banner_anim_after_id)
            except Exception:
                pass
            self._banner_anim_after_id = None

        banner = self._banner_window
        if not banner or not banner.winfo_exists():
            self._banner_window = None
            return

        if immediate:
            banner.destroy()
            self._banner_window = None
            return

        width = banner.winfo_width()
        height = banner.winfo_height()
        x = banner.winfo_x()
        target_y = self.winfo_rooty() - height - 10

        def slide_out():
            if not banner.winfo_exists():
                self._banner_window = None
                return
            current_y = banner.winfo_y()
            if current_y <= target_y:
                banner.destroy()
                self._banner_window = None
                return
            next_y = max(current_y - 16, target_y)
            banner.geometry(f"{width}x{height}+{x}+{next_y}")
            self._banner_anim_after_id = self.after(12, slide_out)

        slide_out()

    def _export_device_images(self, device):
        images = image_items_for(device["uuid"])
        if not images:
            messagebox.showinfo(
                "Export Photos",
                f"No saved photos for {device['name']} yet.",
            )
            return

        target_dir = filedialog.askdirectory(
            title=f"Export photos for {device['name']}",
            mustexist=True,
        )
        if not target_dir:
            return

        try:
            count, export_dir = export_images_for(
                uuid=device["uuid"],
                destination_root=target_dir,
                device_name=device["name"],
            )
        except Exception as exc:
            messagebox.showerror("Export Photos", f"Could not export photos:\n{exc}")
            return

        self.set_server_status(
            f"Exported {count} photos for {device['name']}",
            C["status_ok"],
        )
        messagebox.showinfo(
            "Export Photos",
            f"Exported {count} photos.\n\nSaved to:\n{export_dir}",
        )

    def _open_gallery(self, device):
        uuid = device["uuid"]
        existing = self._gallery_windows.get(uuid)
        if existing and existing.winfo_exists():
            existing.lift()
            existing._load()
            return
        self._gallery_windows[uuid] = GalleryWindow(
            self,
            device,
            on_gallery_changed=self._refresh_device_list,
        )

    def set_server_status(self, text: str, color: str):
        self._srv_lbl.config(text=text, fg=color)

    def show_blocked_upload(self, msg):
        sender = msg.get("sender_ip", "unknown")
        self.set_server_status(f"Blocked upload from {sender}", C["status_err"])

    def show_post_test_event(self, msg):
        sender = msg.get("sender_ip", "unknown")
        content_type = msg.get("content_type") or "no content-type"
        content_length = msg.get("content_length") or 0
        path = msg.get("path") or "/post-test"
        known = bool(msg.get("known_device"))
        tone = "alert" if known else "warn"
        known_text = "known device" if known else "unknown sender"

        self.set_server_status(
            f"POST received from {sender} ({content_length} bytes)",
            C["status_ok"] if known else C["status_warn"],
        )
        self._show_top_notice(
            title="POST received",
            detail=f"{sender}  |  {path}  |  {content_type}  |  {content_length} bytes  |  {known_text}",
            tone=tone,
            duration_ms=8000,
        )
        if self._logs_window and self._logs_window.winfo_exists():
            self._refresh_logs_window()

    def show_admin_device_event(self, msg):
        action = str(msg.get("action", "add")).strip().lower()
        name = msg.get("name", "")
        ip = msg.get("ip", "")
        uuid = msg.get("uuid", "")
        sender = msg.get("sender_ip", "")

        if action in {"delete", "remove"}:
            devices = load_devices()
            target = None
            if uuid:
                target = next((d for d in devices if d["uuid"] == uuid), None)
            if target is None and ip:
                target = next((d for d in devices if d["ip"] == ip), None)
            if target is None and name:
                target = next((d for d in devices if d["name"] == name), None)

            if target:
                try:
                    remove_device(target["uuid"])
                    gw = self._gallery_windows.pop(target["uuid"], None)
                    if gw and gw.winfo_exists():
                        gw.destroy()
                    self._refresh_device_list()
                    self.set_server_status(
                        f"Admin removed device: {target['name']} ({target['ip']})",
                        C["status_warn"],
                    )
                    self._show_top_notice(
                        title="Device removed from management",
                        detail=f"{target['name']}  |  {target['ip']}",
                        tone="alert",
                        duration_ms=8000,
                    )
                except Exception as exc:
                    self.set_server_status("Admin device remove failed", C["status_err"])
                    self._show_top_notice(
                        title="Device remove failed",
                        detail=f"{name or uuid or ip}  |  {exc}",
                        tone="err",
                        duration_ms=7000,
                    )
            else:
                self.set_server_status("Admin remove ignored (not found)", C["status_warn"])
                self._show_top_notice(
                    title="Device remove ignored",
                    detail=f"{name or uuid or ip}  |  Not found in Shob list",
                    tone="warn",
                    duration_ms=6000,
                )
            return

        try:
            save_status = add_device_if_missing(uuid=uuid, ip=ip, name=name)
            self._refresh_device_list(preferred_uuid=uuid)
            if save_status == "created":
                self.set_server_status(f"Admin device saved: {name} ({ip})", C["status_ok"])
                self._flash_device_card(uuid, duration_ms=5000)
                sender_info = f"Source: {sender}" if sender else "Source: management"
                self._show_top_notice(
                    title="New device added",
                    detail=f"{name}  |  {ip}  |  {sender_info}",
                    tone="alert",
                    duration_ms=8000,
                )
                self._schedule_camera_credentials_prompt(
                    uuid=uuid,
                    name=name,
                    ip=ip,
                )
            elif save_status == "exists_uuid":
                self.set_server_status("Admin device already exists", C["status_warn"])
                self._show_top_notice(
                    title="Device already exists",
                    detail=f"{name}  |  {ip}",
                    tone="warn",
                    duration_ms=7000,
                )
                self._schedule_camera_credentials_prompt(
                    uuid=uuid,
                    name=name,
                    ip=ip,
                    only_if_missing=True,
                )
            else:
                self.set_server_status("Admin device IP already exists", C["status_warn"])
                self._show_top_notice(
                    title="Device IP already exists",
                    detail=f"{name}  |  {ip}",
                    tone="warn",
                    duration_ms=7000,
                )
                existing = next((d for d in load_devices() if d["ip"] == ip), None)
                if existing:
                    self._schedule_camera_credentials_prompt(
                        uuid=existing["uuid"],
                        name=existing["name"],
                        ip=existing["ip"],
                        only_if_missing=True,
                    )
        except Exception as exc:
            self.set_server_status("Admin device save failed", C["status_err"])
            self._show_top_notice(
                title="Device update failed",
                detail=f"{name}  |  {ip}  |  {exc}",
                tone="err",
                duration_ms=7000,
            )

    def _on_close(self):
        if self._auto_refresh_after_id:
            try:
                self.after_cancel(self._auto_refresh_after_id)
            except Exception:
                pass
            self._auto_refresh_after_id = None
        self._close_logs_window()
        self._hide_top_notice(immediate=True)
        for item in list(self._active_slots):
            slot = item.get("slot")
            if hasattr(slot, "destroy"):
                try:
                    slot.destroy()
                except Exception:
                    pass
        self.destroy()

    def _center_child_window(self, win):
        win.update_idletasks()
        self.update_idletasks()

        width = win.winfo_width() or win.winfo_reqwidth()
        height = win.winfo_height() or win.winfo_reqheight()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty()
        root_w = self.winfo_width()
        root_h = self.winfo_height()

        x = root_x + max((root_w - width) // 2, 0)
        y = root_y + max((root_h - height) // 2, 0)
        win.geometry(f"+{x}+{y}")

    def _prompt_camera_credentials(self, device_uuid: str, name: str, ip: str):
        initial_values = None
        while True:
            dlg = CameraCredentialsDialog(
                self,
                device_name=name or device_uuid,
                device_ip=ip or "-",
                initial_values=initial_values,
            )
            self.wait_window(dlg)
            if not dlg.result:
                self.set_server_status(
                    f"Camera credentials pending for {name or device_uuid}",
                    C["status_warn"],
                )
                self._show_top_notice(
                    title="Camera credentials not saved",
                    detail=f"{name or device_uuid}  |  Please complete setup",
                    tone="warn",
                    duration_ms=6000,
                )
                return

            initial_values = dlg.result
            self.set_server_status(
                f"Testing RTSP credentials for {name or device_uuid}",
                C["status_warn"],
            )
            self.update_idletasks()

            try:
                target = make_target(
                    host=ip,
                    port=dlg.result["rtsp_port"],
                    username=dlg.result["username"],
                    password=dlg.result["password"],
                    stream_path=dlg.result["stream_path"],
                )
            except Exception as exc:
                messagebox.showerror(
                    "Camera Credentials",
                    f"Invalid RTSP settings:\n{exc}\n\nPlease enter the details again.",
                    parent=self,
                )
                continue

            rtsp_result = test_rtsp_connection(target)
            if not rtsp_result.get("ok"):
                error = rtsp_result.get("error") or "Could not connect to the camera stream."
                self.set_server_status(
                    f"RTSP credentials rejected for {name or device_uuid}",
                    C["status_err"],
                )
                messagebox.showerror(
                    "Camera Credentials",
                    "Could not open the RTSP stream with these details.\n\n"
                    f"{error}\n\n"
                    "Please check the username, password, RTSP port, and camera type.",
                    parent=self,
                )
                continue

            break

        try:
            save_camera_profile(
                device_uuid=device_uuid,
                username=dlg.result["username"],
                password=dlg.result["password"],
                camera_type=dlg.result["camera_type"],
                rtsp_port=dlg.result["rtsp_port"],
                stream_path=dlg.result["stream_path"],
                onvif_port=dlg.result.get("onvif_port", 80),
            )
        except Exception as exc:
            self.set_server_status("Camera credentials save failed", C["status_err"])
            self._show_top_notice(
                title="Camera credentials save failed",
                detail=f"{name or device_uuid}  |  {exc}",
                tone="err",
                duration_ms=7000,
            )
            return

        try:
            save_camera_connection_status(device_uuid, "connected", "")
        except Exception:
            pass

        self.set_server_status(
            f"Camera credentials saved and verified for {name or device_uuid}",
            C["status_ok"],
        )
        self._handle_rtsp_connection_result(
            device_uuid=device_uuid,
            name=name,
            status="connected",
            error="",
            result=rtsp_result,
        )
        self._start_live_stream_for_device(
            {"uuid": device_uuid, "name": name or device_uuid, "ip": ip},
            profile=dlg.result,
        )

    def _prompt_camera_credentials_if_missing(self, uuid: str, name: str, ip: str):
        profile = load_camera_profile(uuid)
        if (
            profile
            and profile.get("username")
            and profile.get("password")
            and profile.get("camera_type")
            and profile.get("rtsp_port")
            and profile.get("stream_path")
        ):
            return
        self._prompt_camera_credentials(uuid, name, ip)

    def _start_rtsp_connection_check(self, device_uuid: str, name: str, ip: str, profile: dict):
        try:
            target = make_target(
                host=ip,
                port=profile.get("rtsp_port", 8554),
                username=profile.get("username", ""),
                password=profile.get("password", ""),
                stream_path=profile.get("stream_path", ""),
            )
        except Exception as exc:
            save_camera_connection_status(device_uuid, "invalid_profile", str(exc))
            self._show_top_notice(
                title="Camera RTSP profile is invalid",
                detail=f"{name or device_uuid}  |  {exc}",
                tone="err",
                duration_ms=7000,
            )
            return

        def _run_check():
            result = test_rtsp_connection(target)
            status = "connected" if result.get("ok") else "failed"
            error = "" if result.get("ok") else str(result.get("error", "Unknown RTSP error"))
            try:
                save_camera_connection_status(device_uuid, status, error)
            except Exception:
                pass
            self.after(
                0,
                lambda r=result, s=status, e=error: self._handle_rtsp_connection_result(
                    device_uuid=device_uuid,
                    name=name,
                    status=s,
                    error=e,
                    result=r,
                ),
            )

        threading.Thread(target=_run_check, daemon=True).start()

    def _handle_rtsp_connection_result(
        self,
        device_uuid: str,
        name: str,
        status: str,
        error: str,
        result: dict,
    ):
        display_name = name or device_uuid
        if status == "connected":
            self.set_server_status(f"RTSP connected: {display_name}", C["status_ok"])
            detail = result.get("frame_shape") or "First frame received"
            self._show_top_notice(
                title="Camera RTSP connected",
                detail=f"{display_name}  |  {detail}",
                tone="ok",
                duration_ms=6500,
            )
        else:
            self.set_server_status(f"RTSP failed: {display_name}", C["status_err"])
            self._show_top_notice(
                title="Camera RTSP check failed",
                detail=f"{display_name}  |  {error}",
                tone="err",
                duration_ms=9000,
            )
        self._refresh_device_list(preferred_uuid=device_uuid)

    def _schedule_camera_credentials_prompt(
        self,
        uuid: str,
        name: str,
        ip: str,
        only_if_missing: bool = False,
    ):
        if not uuid:
            return
        if uuid in self._pending_credential_prompts:
            return
        self._pending_credential_prompts.add(uuid)

        def _open_prompt():
            try:
                if only_if_missing:
                    self._prompt_camera_credentials_if_missing(uuid, name, ip)
                else:
                    self._prompt_camera_credentials(uuid, name, ip)
            finally:
                self._pending_credential_prompts.discard(uuid)

        self.after(80, _open_prompt)

    def _next_device_uuid(self) -> str:
        existing = {d["uuid"] for d in load_devices()}
        idx = 1
        while True:
            candidate = f"cam-{idx:04d}"
            if candidate not in existing:
                return candidate
            idx += 1

    def _show_add_device_dialog(self):
        dlg = DeviceDialog(self, self._next_device_uuid())
        self.wait_window(dlg)
        if not dlg.result:
            return

        name = dlg.result["name"]
        ip = dlg.result["ip"]
        uuid = dlg.result["uuid"] or self._next_device_uuid()
        if not name or not ip or not uuid:
            messagebox.showerror("Add Device", "Name, IP address, and UUID are required.")
            return

        try:
            add_device(uuid=uuid, ip=ip, name=name)
        except Exception as exc:
            messagebox.showerror("Add Device", f"Could not add device:\n{exc}")
            return
        self._refresh_device_list()

    def _remove_device(self, device):
        confirmed = messagebox.askyesno(
            "Remove Device",
            f"Remove {device['name']} ({device['ip']}) from the device list?\n\n"
            "Existing gallery files will be kept.",
        )
        if not confirmed:
            return

        try:
            remove_device(device["uuid"])
        except Exception as exc:
            messagebox.showerror("Remove Device", f"Could not remove device:\n{exc}")
            return

        gw = self._gallery_windows.pop(device["uuid"], None)
        if gw and gw.winfo_exists():
            gw.destroy()
        live_slot = self._live_stream_slots.pop(device["uuid"], None)
        if live_slot and live_slot.winfo_exists():
            live_slot.destroy()
            self._active_slots = [
                item for item in self._active_slots if item.get("slot") is not live_slot
            ]
        self._refresh_device_list()
        self._rebuild_grid()
        self.set_server_status(f"Device deleted: {device['name']}", C["status_ok"])

    def _start_live_stream_for_device(self, device, profile=None):
        uuid = device.get("uuid")
        if not uuid:
            return

        existing = self._live_stream_slots.get(uuid)
        if existing and existing.winfo_exists():
            self.set_server_status(f"Live stream already open: {device['name']}", C["status_ok"])
            return

        if profile is None:
            profile = load_camera_profile(uuid)
        if (
            not profile
            or not profile.get("username")
            or not profile.get("password")
            or not profile.get("rtsp_port")
            or not profile.get("stream_path")
        ):
            self._prompt_camera_credentials(uuid, device.get("name", uuid), device.get("ip", ""))
            return

        try:
            target = make_target(
                host=device.get("ip", ""),
                port=profile.get("rtsp_port", 8554),
                username=profile.get("username", ""),
                password=profile.get("password", ""),
                stream_path=profile.get("stream_path", ""),
            )
        except Exception as exc:
            messagebox.showerror(
                "Live Stream",
                f"Could not build RTSP stream details:\n{exc}",
            )
            return

        slot = LiveStreamSlot(
            self._player_frame,
            device,
            target,
            profile=profile,
            on_close=self._live_stream_closed,
            on_status=self._live_stream_status_changed,
        )
        self._live_stream_slots[uuid] = slot
        self._active_slots.append({
            "kind": "live",
            "device_uuid": uuid,
            "msg": {"live": True, "device": device},
            "slot": slot,
        })
        self._rebuild_grid()
        self.set_server_status(f"Opening live stream: {device['name']}", C["status_warn"])

    def _live_stream_closed(self, device, slot):
        uuid = device.get("uuid")
        if uuid:
            self._live_stream_slots.pop(uuid, None)
        self._active_slots = [
            item for item in self._active_slots if item.get("slot") is not slot
        ]
        self._rebuild_grid()
        self.set_server_status(f"Live stream stopped: {device.get('name', uuid)}", C["status_warn"])

    def _live_stream_status_changed(self, device, status: str, error: str = ""):
        uuid = device.get("uuid")
        if uuid:
            try:
                save_camera_connection_status(uuid, status, error)
            except Exception:
                pass

        if status == "connected":
            self.set_server_status(f"Live stream active: {device['name']}", C["status_ok"])
        elif status == "failed":
            self.set_server_status(f"Live stream failed: {device['name']}", C["status_err"])
            self._show_top_notice(
                title="Live stream failed",
                detail=f"{device['name']}  |  {error}",
                tone="err",
                duration_ms=8000,
            )

    def _rebuild_grid(self):
        count = len(self._active_slots)
        if count == 0:
            self._waiting_lbl.place(relx=0.5, rely=0.5, anchor="center")
            return

        self._waiting_lbl.place_forget()
        if count <= 2:
            cols, rows = count, 1
        elif count <= 4:
            cols, rows = 2, 2
        elif count <= 6:
            cols, rows = 3, 2
        elif count <= 9:
            cols, rows = 3, 3
        else:
            cols, rows = 4, (count + 3) // 4

        for idx, item in enumerate(self._active_slots):
            row, col = divmod(idx, cols)
            slot = item["slot"]
            slot.place(
                relx=col / cols,
                rely=row / rows,
                relwidth=1 / cols,
                relheight=1 / rows,
            )
            slot.after(60, slot._start)

    def add_slot(self, msg):
        slot = MediaSlot(
            self._player_frame,
            msg,
            display_secs=self._display_secs.get(),
            on_done=self._slot_done,
        )
        self._active_slots.append({"msg": msg, "slot": slot})
        self._rebuild_grid()

    def _slot_done(self, msg):
        try:
            saved = save_to_gallery(msg["device"]["uuid"], msg["path"], msg["received_at"])
            if msg["ext"] == ".mp4":
                extract_video_thumbnail(saved)
        except Exception as exc:
            print(f"Gallery save error: {exc}")

        self._active_slots = [item for item in self._active_slots if item["msg"] is not msg]
        for child in self._player_frame.winfo_children():
            if isinstance(child, MediaSlot) and child.msg is msg:
                child.destroy()
                break

        self._rebuild_grid()
        self._refresh_device_list()

        gw = self._gallery_windows.get(msg["device"]["uuid"])
        if gw and gw.winfo_exists():
            gw._load()
