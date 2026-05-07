"""
Main Tk application shell that composes the UI feature modules.
"""

from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.backend import (
    add_device_if_missing,
    add_device,
    load_devices,
    remove_device,
)
from core.gallery_store import extract_video_thumbnail, gallery_items_for, save_to_gallery
from core.gallery_store import export_images_for, image_items_for

from .ui_devices import DeviceDialog
from .ui_gallery import GalleryWindow
from .ui_media import MediaSlot
from .ui_theme import C, apply_ttk_style, load_logo, load_logo2


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
        radius: int = 10,
        font=("Helvetica", 9, "bold"),
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

        # Soft outer glow
        self._rounded_rect(
            0,
            0,
            w,
            h,
            radius=max(self._radius + 1, self._radius),
            fill=self.cget("bg"),
            outline=border,
            width=1,
        )

        # Main button body
        self._rounded_rect(
            1,
            1,
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
            icon_size = max(min(h - 14, 16), 14)
            icon_left = 9
            icon_top = (h - icon_size) // 2
            icon_box_fill = self._icon_box_fill_color or fill
            self._rounded_rect(
                icon_left,
                icon_top,
                icon_left + icon_size,
                icon_top + icon_size,
                radius=4,
                fill=icon_box_fill,
                outline=border,
                width=1,
            )
            self.create_text(
                icon_left + (icon_size // 2),
                h // 2,
                text=self._icon_text,
                fill=self._icon_color,
                font=self._icon_font,
            )
            text_x = icon_left + icon_size + 8
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
        return self.create_polygon(points, smooth=True, splinesteps=24, **kwargs)


class SecCamApp(tk.Tk):
    SIDEBAR_W = 320

    def __init__(self):
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
        self._devices_title_var = tk.StringVar(value="DEVICES (0)")
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
        hdr = tk.Frame(parent, bg=C["bg_sidebar"])
        hdr.pack(fill=tk.X, padx=12, pady=(14, 8))
        tk.Label(
            hdr,
            textvariable=self._devices_title_var,
            font=("Helvetica", 10, "bold"),
            bg=C["bg_sidebar"],
            fg=C["tx_green"],
        ).pack(side=tk.LEFT)
        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)

        scroll_f = tk.Frame(parent, bg=C["bg_sidebar"])
        scroll_f.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(scroll_f, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._dev_canvas = tk.Canvas(
            scroll_f,
            bg=C["bg_sidebar"],
            highlightthickness=0,
            yscrollcommand=vsb.set,
        )
        self._dev_canvas.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self._dev_canvas.yview)
        self._dev_list = tk.Frame(self._dev_canvas, bg=C["bg_sidebar"])
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

        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)
        actions = tk.Frame(parent, bg=C["bg_sidebar"])
        actions.pack(fill=tk.X, padx=12, pady=10)

        add_btn = tk.Button(
            actions,
            text="➕  Add Device",
            command=self._show_add_device_dialog,
            bg=C["tx_green"],
            fg=C["tx_white"],
            activebackground="#0f6f3f",
            activeforeground=C["tx_white"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        # Add Device button hidden by request.

        refresh_btn = tk.Button(
            actions,
            text="🔄  Refresh",
            command=self._manual_refresh_devices,
            bg=C["bg_card"],
            fg=C["tx_green"],
            activebackground=C["bg_card_hv"],
            activeforeground=C["tx_green"],
            relief=tk.FLAT,
            highlightbackground=C["tx_green"],
            highlightthickness=1,
            bd=0,
            padx=10,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        refresh_btn.pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )

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
        self._devices_title_var.set(f"DEVICES ({len(devices)})")

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

    def _build_device_card(self, dev):
        items = gallery_items_for(dev["uuid"])
        items_count = len(items)
        card_canvas = tk.Canvas(
            self._dev_list,
            bg=C["bg_sidebar"],
            bd=0,
            highlightthickness=0,
            height=132,
            cursor="hand2",
        )
        card_canvas.pack(fill=tk.X, padx=10, pady=6)

        card = tk.Frame(card_canvas, bg=C["bg_card"])
        card_window = card_canvas.create_window(12, 10, window=card, anchor="nw")

        top = tk.Frame(card, bg=C["bg_card"], padx=10, pady=9)
        top.pack(fill=tk.X)
        top.grid_columnconfigure(0, weight=1)

        info = tk.Frame(top, bg=C["bg_card"])
        info.grid(row=0, column=0, sticky="nsew")
        actions = tk.Frame(top, bg=C["bg_card"])
        actions.grid(row=0, column=1, sticky="ne", padx=(10, 0))

        name_lbl = tk.Label(
            info,
            text=dev["name"],
            font=("Helvetica", 12, "bold"),
            bg=C["bg_card"],
            fg=C["tx_primary"],
            anchor="w",
        )
        name_lbl.pack(fill=tk.X)

        ip_lbl = tk.Label(
            info,
            text=dev["ip"],
            font=("Helvetica", 10),
            bg=C["bg_card"],
            fg=C["tx_secondary"],
            anchor="w",
        )
        ip_lbl.pack(fill=tk.X, pady=(2, 0))

        items_lbl = tk.Label(
            info,
            text=f"{items_count} items in gallery",
            font=("Helvetica", 10, "bold"),
            bg=C["bg_card"],
            fg=C["tx_green_lt"],
            anchor="w",
        )
        items_lbl.pack(fill=tk.X, pady=(6, 0))

        export_btn = RoundedActionButton(
            actions,
            text="Export Photos",
            command=lambda d=dev: self._export_device_images(d),
            fill_color="#0a5c41",
            hover_fill_color="#11865d",
            press_fill_color="#084a35",
            border_color="#24ffb2",
            border_hover_color="#63ffd0",
            text_color=C["tx_white"],
            icon_text="\u2B07",
            icon_color="#d8ffee",
            icon_box_fill_color="#0b4f39",
            width=120,
            height=33,
            radius=8,
        )
        export_btn.pack(side=tk.TOP, fill=tk.X)

        delete_btn = RoundedActionButton(
            actions,
            text="Delete",
            command=lambda d=dev: self._remove_device(d),
            fill_color="#7b1125",
            hover_fill_color="#a01933",
            press_fill_color="#640d1e",
            border_color="#ff3158",
            border_hover_color="#ff6788",
            text_color=C["tx_white"],
            icon_text="\u2716",
            icon_color="#ffd9e0",
            icon_box_fill_color="#651020",
            width=120,
            height=33,
            radius=8,
        )
        delete_btn.pack(side=tk.TOP, fill=tk.X, pady=(7, 0))

        card.update_idletasks()
        card_canvas.configure(height=card.winfo_reqheight() + 20)

        hover_widgets = [
            card,
            top,
            info,
            actions,
            name_lbl,
            ip_lbl,
            items_lbl,
        ]
        hover = {"on": False}
        flashing = dev["uuid"] in self._flash_device_uuids
        base_bg = "#2a1b1b" if flashing else "#0b1f36"
        hover_bg = "#3a2323" if flashing else "#112b4a"

        for widget in hover_widgets:
            widget.configure(bg=base_bg)
        export_btn.set_container_bg(base_bg)
        delete_btn.set_container_bg(base_bg)

        def _draw_card_background():
            width = max(card_canvas.winfo_width(), 80)
            height = max(card_canvas.winfo_height(), 80)
            if flashing:
                fill = hover_bg if hover["on"] else base_bg
                outline = "#be2323" if hover["on"] else "#d62828"
            else:
                fill = hover_bg if hover["on"] else base_bg
                outline = "#2a668f" if hover["on"] else "#1a4f79"
            card_canvas.delete("card_bg")
            card_canvas.delete("card_accent")
            self._rounded_rect(
                card_canvas,
                10,
                3,
                width - 4,
                height - 4,
                radius=12,
                fill=fill,
                outline=outline,
                width=1,
                tags="card_bg",
            )
            card_canvas.tag_lower("card_bg")

            # Single slim neon strip on the left, integrated inside the card.
            accent_top = 12
            accent_bottom = max(height - 12, accent_top + 20)
            accent_outer = "#25dcff" if hover["on"] else "#17c8ef"
            accent_core = "#b4fbff" if hover["on"] else "#7cf3ff"

            self._rounded_rect(
                card_canvas,
                13,
                accent_top,
                19,
                accent_bottom,
                radius=4,
                fill="#041425",
                outline=accent_outer,
                width=1,
                tags="card_accent",
            )
            self._rounded_rect(
                card_canvas,
                15,
                accent_top + 4,
                17,
                accent_bottom - 4,
                radius=2,
                fill=accent_core,
                outline=accent_core,
                width=1,
                tags="card_accent",
            )

            card_canvas.coords(card_window, 22, 10)
            card_canvas.itemconfigure(card_window, width=max(width - 28, 120))
            card_canvas.tag_raise(card_window)

        def _enter(_event):
            hover["on"] = True
            _draw_card_background()
            for widget in hover_widgets:
                widget.configure(bg=hover_bg)
            export_btn.set_container_bg(hover_bg)
            delete_btn.set_container_bg(hover_bg)

        def _leave(_event):
            hover["on"] = False
            _draw_card_background()
            for widget in hover_widgets:
                widget.configure(bg=base_bg)
            export_btn.set_container_bg(base_bg)
            delete_btn.set_container_bg(base_bg)

        card_canvas.bind("<Configure>", lambda _e: _draw_card_background())
        _draw_card_background()

        clickable = [
            card_canvas,
            card,
            top,
            info,
            name_lbl,
            ip_lbl,
            items_lbl,
        ]
        for widget in clickable:
            widget.bind("<Button-1>", lambda _e, d=dev: self._open_gallery(d))
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)

        for btn in (export_btn, delete_btn):
            btn.bind("<Enter>", _enter)
            btn.bind("<Leave>", _leave)

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
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

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
            elif save_status == "exists_uuid":
                self.set_server_status("Admin device already exists", C["status_warn"])
                self._show_top_notice(
                    title="Device already exists",
                    detail=f"{name}  |  {ip}",
                    tone="warn",
                    duration_ms=7000,
                )
            else:
                self.set_server_status("Admin device IP already exists", C["status_warn"])
                self._show_top_notice(
                    title="Device IP already exists",
                    detail=f"{name}  |  {ip}",
                    tone="warn",
                    duration_ms=7000,
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
        self._hide_top_notice(immediate=True)
        self.destroy()

    def _center_child_window(self, win):
        win.update_idletasks()
        self.update_idletasks()

        width = win.winfo_reqwidth()
        height = win.winfo_reqheight()
        root_x = self.winfo_rootx()
        root_y = self.winfo_rooty()
        root_w = self.winfo_width()
        root_h = self.winfo_height()

        x = root_x + max((root_w - width) // 2, 0)
        y = root_y + max((root_h - height) // 2, 0)
        win.geometry(f"+{x}+{y}")

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
        self._refresh_device_list()
        self.set_server_status(f"Device deleted: {device['name']}", C["status_ok"])

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
