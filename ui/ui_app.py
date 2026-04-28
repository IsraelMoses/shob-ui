"""
Main Tk application shell that composes the UI feature modules.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from core.backend import (
    add_device_if_missing,
    add_device,
    load_devices,
    remove_device,
)
from core.gallery_store import extract_video_thumbnail, gallery_count_for, save_to_gallery

from .ui_devices import DeviceDialog
from .ui_gallery import GalleryWindow
from .ui_media import MediaSlot
from .ui_theme import C, apply_ttk_style, load_logo


class SecCamApp(tk.Tk):
    SIDEBAR_W = 230

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
        self._build_ui()

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
            fg="#3d3d3d",
        )
        self._waiting_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _build_toolbar(self):
        toolbar = tk.Frame(self, bg=C["bg_toolbar"], height=56)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)

        logo_photo = load_logo(height_px=44)
        if logo_photo:
            self._logo_photo = logo_photo
            lbl = tk.Label(toolbar, image=logo_photo, bg=C["bg_toolbar"])
            lbl.image = logo_photo
            lbl.pack(side=tk.LEFT, padx=(14, 0), pady=6)
        else:
            badge = tk.Frame(toolbar, bg=C["tx_green"], padx=8, pady=4)
            badge.pack(side=tk.LEFT, padx=(14, 0), pady=10)
            tk.Label(
                badge,
                text="SC",
                font=("Helvetica", 12, "bold"),
                bg=C["tx_green"],
                fg="white",
            ).pack()

        tk.Frame(toolbar, bg=C["border"], width=1).pack(
            side=tk.LEFT,
            fill=tk.Y,
            padx=10,
            pady=10,
        )
        tk.Label(
            toolbar,
            text="SecCam Player",
            font=("Helvetica", 13, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_green"],
        ).pack(side=tk.LEFT)

        tk.Label(
            toolbar,
            text="Photo display (s):",
            font=("Helvetica", 9),
            bg=C["bg_toolbar"],
            fg=C["tx_secondary"],
        ).pack(side=tk.RIGHT, padx=(0, 4))
        ttk.Spinbox(
            toolbar,
            from_=1,
            to=300,
            textvariable=self._display_secs,
            width=5,
            font=("Helvetica", 9),
        ).pack(side=tk.RIGHT, padx=(0, 14), pady=14)

        tk.Frame(toolbar, bg=C["border"], width=1).pack(
            side=tk.RIGHT,
            fill=tk.Y,
            padx=8,
            pady=10,
        )
        self._srv_lbl = tk.Label(
            toolbar,
            text="Starting...",
            font=("Helvetica", 9),
            bg=C["bg_toolbar"],
            fg=C["status_warn"],
        )
        self._srv_lbl.pack(side=tk.RIGHT, padx=12)

    def _build_sidebar(self, parent):
        hdr = tk.Frame(parent, bg=C["bg_sidebar"])
        hdr.pack(fill=tk.X, padx=12, pady=(14, 4))
        tk.Label(
            hdr,
            text="DEVICES",
            font=("Helvetica", 9, "bold"),
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
        self._dev_canvas.create_window((0, 0), window=self._dev_list, anchor="nw")
        self._dev_list.bind(
            "<Configure>",
            lambda e: self._dev_canvas.configure(scrollregion=self._dev_canvas.bbox("all")),
        )

        tk.Frame(parent, bg=C["border"], height=1).pack(fill=tk.X)
        actions = tk.Frame(parent, bg=C["bg_sidebar"])
        actions.pack(fill=tk.X, padx=12, pady=10)
        ttk.Button(actions, text="Add Device", command=self._show_add_device_dialog).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
        )
        ttk.Button(actions, text="Refresh", command=self._refresh_device_list).pack(
            side=tk.LEFT,
            fill=tk.X,
            expand=True,
            padx=(8, 0),
        )

        self._refresh_device_list()

    def _refresh_device_list(self):
        for widget in self._dev_list.winfo_children():
            widget.destroy()

        for dev in load_devices():
            self._build_device_card(dev)

    def _build_device_card(self, dev):
        card = tk.Frame(
            self._dev_list,
            bg=C["bg_card"],
            cursor="hand2",
            highlightbackground=C["border"],
            highlightthickness=1,
        )
        card.pack(fill=tk.X, padx=10, pady=5)

        accent = tk.Frame(card, bg=C["tx_green"], width=3)
        accent.pack(side=tk.LEFT, fill=tk.Y)

        info = tk.Frame(card, bg=C["bg_card"])
        info.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=7)

        tk.Label(
            info,
            text=dev["name"],
            font=("Helvetica", 10, "bold"),
            bg=C["bg_card"],
            fg=C["tx_primary"],
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            info,
            text=dev["ip"],
            font=("Helvetica", 8),
            bg=C["bg_card"],
            fg=C["tx_secondary"],
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            info,
            text=f"{gallery_count_for(dev['uuid'])} items in gallery",
            font=("Helvetica", 8),
            bg=C["bg_card"],
            fg=C["tx_green_lt"],
            anchor="w",
        ).pack(fill=tk.X)

        ttk.Button(card, text="Remove", command=lambda d=dev: self._remove_device(d)).pack(
            side=tk.RIGHT,
            padx=8,
            pady=8,
        )

        def _enter(e, c=card, iw=info):
            c.configure(bg=C["bg_card_hv"], highlightbackground=C["tx_green_lt"])
            iw.configure(bg=C["bg_card_hv"])
            for child in iw.winfo_children():
                child.configure(bg=C["bg_card_hv"])

        def _leave(e, c=card, iw=info):
            c.configure(bg=C["bg_card"], highlightbackground=C["border"])
            iw.configure(bg=C["bg_card"])
            for child in iw.winfo_children():
                child.configure(bg=C["bg_card"])

        clickable = [card, accent, info, *info.winfo_children()]
        for widget in clickable:
            widget.bind("<Button-1>", lambda e, d=dev: self._open_gallery(d))
            widget.bind("<Enter>", _enter)
            widget.bind("<Leave>", _leave)

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
        name = msg.get("name", "")
        ip = msg.get("ip", "")
        uuid = msg.get("uuid", "")
        sender = msg.get("sender_ip", "unknown")
        received_at = msg.get("received_at")
        if hasattr(received_at, "strftime"):
            received = received_at.strftime("%Y-%m-%d %H:%M:%S")
        else:
            received = str(received_at or "")

        try:
            save_status = add_device_if_missing(uuid=uuid, ip=ip, name=name)
            self._refresh_device_list()
            if save_status == "created":
                self.set_server_status(f"Admin device saved: {name} ({ip})", C["status_ok"])
                saved_message = "Saved to device list"
            elif save_status == "exists_uuid":
                self.set_server_status("Admin device already exists", C["status_warn"])
                saved_message = "Already exists by UUID; old device was not changed"
            else:
                self.set_server_status("Admin device IP already exists", C["status_warn"])
                saved_message = "Already exists by IP; old device was not changed"
        except Exception as exc:
            self.set_server_status("Admin device save failed", C["status_err"])
            saved_message = f"Could not save device: {exc}"

        win = tk.Toplevel(self)
        win.withdraw()
        win.title("Admin Device Update")
        win.configure(bg=C["bg_toolbar"])
        win.transient(self)

        body = tk.Frame(win, bg=C["bg_toolbar"], padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            body,
            text="Management update received",
            font=("Helvetica", 13, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_green"],
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        rows = [
            ("Name", name),
            ("IP", ip),
            ("UUID", uuid),
            ("From", sender),
            ("Time", received),
            ("Status", saved_message),
        ]
        for row, (label, value) in enumerate(rows, start=1):
            tk.Label(
                body,
                text=f"{label}:",
                font=("Helvetica", 9, "bold"),
                bg=C["bg_toolbar"],
                fg=C["tx_primary"],
            ).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
            tk.Label(
                body,
                text=value,
                font=("Helvetica", 9),
                bg=C["bg_toolbar"],
                fg=C["tx_secondary"],
            ).grid(row=row, column=1, sticky="w", pady=3)

        ttk.Button(body, text="Close", command=win.destroy).grid(
            row=len(rows) + 1,
            column=1,
            sticky="e",
            pady=(14, 0),
        )
        self._center_child_window(win)
        win.deiconify()
        win.lift()

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

