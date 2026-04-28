"""
Gallery window UI for browsing stored media per device.
"""

import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from core.gallery_store import clear_gallery_for, extract_video_thumbnail, gallery_items_for

from .ui_theme import C


class GalleryWindow(tk.Toplevel):
    THUMB_W = 170
    THUMB_H = 115
    COLS = 4

    def __init__(self, parent, device: dict, on_gallery_changed=None):
        super().__init__(parent)
        self.withdraw()
        self.device = device
        self.on_gallery_changed = on_gallery_changed
        self._thumbs = []
        self.title(f"Gallery  {device['name']}")
        self.geometry("830x600")
        self.configure(bg=C["bg_gallery"])
        self._build()
        self._load()
        self._center_on_parent(parent, 830, 600)
        self.deiconify()
        self.lift()

    def _center_on_parent(self, parent, width=None, height=None):
        parent.update_idletasks()
        self.update_idletasks()

        width = width or self.winfo_reqwidth()
        height = height or self.winfo_reqheight()
        x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 0)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build(self):
        hdr = tk.Frame(self, bg=C["bg_toolbar"], pady=10)
        hdr.pack(fill=tk.X)
        tk.Frame(hdr, bg=C["divider"], width=4).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            hdr,
            text=f"  {self.device['name']}",
            font=("Helvetica", 14, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_green"],
        ).pack(side=tk.LEFT, padx=10)
        tk.Label(
            hdr,
            text=f"IP: {self.device['ip']}   |   UUID: {self.device['uuid']}",
            font=("Helvetica", 9),
            bg=C["bg_toolbar"],
            fg=C["tx_secondary"],
        ).pack(side=tk.LEFT, padx=6)
        ttk.Button(hdr, text="Clear Gallery", command=self._clear_gallery).pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )
        ttk.Button(hdr, text="Refresh", command=self._load).pack(side=tk.RIGHT, padx=14)
        tk.Frame(self, bg=C["divider"], height=2).pack(fill=tk.X)

        container = tk.Frame(self, bg=C["bg_gallery"])
        container.pack(fill=tk.BOTH, expand=True)
        vsb = ttk.Scrollbar(container, orient="vertical")
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas = tk.Canvas(
            container,
            bg=C["bg_gallery"],
            highlightthickness=0,
            yscrollcommand=vsb.set,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        vsb.config(command=self._canvas.yview)
        self._grid = tk.Frame(self._canvas, bg=C["bg_gallery"])
        self._canvas.create_window((4, 4), window=self._grid, anchor="nw")
        self._grid.bind(
            "<Configure>",
            lambda e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.bind(
            "<MouseWheel>",
            lambda e: self._canvas.yview_scroll(-1 * (e.delta // 120), "units"),
        )

    def _load(self):
        for widget in self._grid.winfo_children():
            widget.destroy()
        self._thumbs.clear()

        items = gallery_items_for(self.device["uuid"])
        if not items:
            tk.Label(
                self._grid,
                text="No media yet.",
                font=("Helvetica", 13),
                bg=C["bg_gallery"],
                fg=C["tx_secondary"],
            ).grid(row=0, column=0, padx=24, pady=24)
            return

        for idx, (received_str, media_path) in enumerate(items):
            col = idx % self.COLS
            row = (idx // self.COLS) * 2
            self._make_thumb_cell(row, col, media_path, received_str)

    def _make_thumb_cell(self, row, col, media_path, received_str):
        is_video = media_path.suffix.lower() == ".mp4"
        photo = self._load_thumbnail(media_path, is_video)

        cell = tk.Frame(
            self._grid,
            bg=C["bg_thumb"],
            highlightbackground=C["border"],
            highlightthickness=1,
        )
        cell.grid(row=row, column=col, padx=8, pady=8, sticky="n")

        if photo:
            lbl = tk.Label(cell, image=photo, bg=C["bg_thumb"], cursor="hand2")
            lbl.image = photo
            lbl.pack()
            self._thumbs.append(photo)
        else:
            tk.Label(
                cell,
                text="VIDEO" if is_video else "IMAGE",
                font=("Helvetica", 10, "bold"),
                bg=C["bg_thumb"],
                fg="#9ca3af",
                width=14,
                height=5,
            ).pack()

        if is_video:
            tk.Label(
                cell,
                text="VIDEO",
                font=("Helvetica", 7, "bold"),
                bg="#b91c1c",
                fg="white",
            ).pack(fill=tk.X)

        cell.bind("<Enter>", lambda e, c=cell: c.configure(highlightbackground=C["tx_green_lt"]))
        cell.bind("<Leave>", lambda e, c=cell: c.configure(highlightbackground=C["border"]))
        for widget in (cell, *cell.winfo_children()):
            widget.bind("<Button-1>", lambda e, p=media_path, v=is_video: self._open_media(p, v))

        try:
            ts = datetime.fromisoformat(received_str).strftime("%Y-%m-%d  %H:%M:%S")
        except Exception:
            ts = received_str[:19]
        tk.Label(
            self._grid,
            text=ts,
            font=("Helvetica", 8),
            bg=C["bg_gallery"],
            fg=C["tx_green_lt"],
        ).grid(row=row + 1, column=col, pady=(0, 4))

    def _load_thumbnail(self, media_path, is_video):
        try:
            if is_video:
                thumb_p = media_path.with_suffix(".thumb.jpg")
                if not thumb_p.exists():
                    thumb_p = extract_video_thumbnail(media_path) or thumb_p
                img_src = (
                    Image.open(thumb_p)
                    if thumb_p.exists()
                    else Image.new("RGB", (self.THUMB_W, self.THUMB_H), "#d1d5db")
                )
            else:
                img_src = Image.open(media_path)
            img_src.thumbnail((self.THUMB_W, self.THUMB_H))
            return ImageTk.PhotoImage(img_src)
        except Exception:
            return None

    def _open_media(self, path, is_video):
        win = tk.Toplevel(self)
        win.withdraw()
        win.title(path.name)
        win.configure(bg="#111111")
        if is_video:
            tk.Label(
                win,
                text=f"Video: {path.name}\n\nOpen externally to play:\n{path}",
                bg="#111111",
                fg="#e5e7eb",
                font=("Helvetica", 11),
                wraplength=420,
                justify="center",
            ).pack(expand=True, padx=32, pady=32)
            self._center_child_window(win)
            win.deiconify()
            win.lift()
            return

        try:
            img = Image.open(path)
            img.thumbnail((960, 740))
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(win, image=photo, bg="#111111")
            lbl.image = photo
            lbl.pack(expand=True)
        except Exception as exc:
            tk.Label(
                win,
                text=f"Cannot open image:\n{exc}",
                bg="#111111",
                fg="#ef4444",
            ).pack(expand=True)
        self._center_child_window(win)
        win.deiconify()
        win.lift()

    def _center_child_window(self, win):
        win.update_idletasks()
        self.update_idletasks()

        width = win.winfo_reqwidth()
        height = win.winfo_reqheight()
        x = self.winfo_rootx() + max((self.winfo_width() - width) // 2, 0)
        y = self.winfo_rooty() + max((self.winfo_height() - height) // 2, 0)
        win.geometry(f"+{x}+{y}")

    def _clear_gallery(self):
        confirmed = messagebox.askyesno(
            "Clear Gallery",
            f"Delete all stored media for {self.device['name']}?\n\n"
            "This removes the gallery records and local media files for this camera.",
        )
        if not confirmed:
            return

        try:
            clear_gallery_for(self.device["uuid"])
        except Exception as exc:
            messagebox.showerror("Clear Gallery", f"Could not clear gallery:\n{exc}")
            return

        self._load()
        if self.on_gallery_changed:
            self.on_gallery_changed()
