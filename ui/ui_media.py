"""
Live media slot widget for currently displayed uploads.
"""

import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from .ui_theme import C


class MediaSlot(tk.Frame):
    def __init__(self, parent, msg, display_secs, on_done, **kw):
        super().__init__(parent, bg="#111111", **kw)
        self.msg = msg
        self.display_secs = display_secs
        self.on_done = on_done
        self._timer_id = None
        self._video_cap = None
        self._photo_ref = None
        self._frame_job = None
        self._build()
        self._start()

    def _build(self):
        device = self.msg["device"]
        bar = tk.Frame(self, bg=C["slot_bar"], height=30)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)
        tk.Frame(bar, bg=C["divider"], width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            bar,
            text=f"  {device['name']}",
            font=("Helvetica", 9, "bold"),
            bg=C["slot_bar"],
            fg=C["slot_bar_tx"],
        ).pack(side=tk.LEFT)
        tk.Label(
            bar,
            text=device["ip"],
            font=("Helvetica", 8),
            bg=C["slot_bar"],
            fg=C["tx_secondary"],
        ).pack(side=tk.LEFT, padx=6)
        self._time_lbl = tk.Label(
            bar,
            text="",
            font=("Helvetica", 8, "bold"),
            bg=C["slot_bar"],
            fg=C["tx_green_lt"],
        )
        self._time_lbl.pack(side=tk.RIGHT, padx=10)

        self._content = tk.Frame(self, bg="#111111")
        self._content.pack(fill=tk.BOTH, expand=True)

        self._prog_frame = tk.Frame(self, bg=C["prog_bg"], height=3)
        self._prog_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self._prog_bar = tk.Frame(self._prog_frame, bg=C["prog_fill"], height=3)
        self._prog_bar.place(x=0, y=0, relwidth=1.0, height=3)

    def _start(self):
        for widget in self._content.winfo_children():
            widget.destroy()
        if self.msg["ext"] == ".mp4":
            self._play_video(self.msg["path"])
        else:
            self._show_image(self.msg["path"])
        self._start_countdown()

    def _show_image(self, path):
        self._content.update_idletasks()
        width = max(self._content.winfo_width(), 200)
        height = max(self._content.winfo_height(), 150)
        try:
            img = Image.open(path)
            img.thumbnail((width, height))
            photo = ImageTk.PhotoImage(img)
            self._photo_ref = photo
            lbl = tk.Label(self._content, image=photo, bg="#111111")
            lbl.image = photo
            lbl.place(relx=0.5, rely=0.5, anchor="center")
        except Exception as exc:
            tk.Label(
                self._content,
                text=f"Error:\n{exc}",
                bg="#111111",
                fg="#ef4444",
                wraplength=200,
            ).place(relx=0.5, rely=0.5, anchor="center")

    def _play_video(self, path):
        if self._video_cap:
            self._video_cap.release()
        self._video_cap = cv2.VideoCapture(str(path))
        self._video_lbl = tk.Label(self._content, bg="#111111")
        self._video_lbl.place(relx=0.5, rely=0.5, anchor="center")
        self._advance_frame()

    def _advance_frame(self):
        if self._video_cap is None:
            return
        ok, frame = self._video_cap.read()
        if not ok:
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._video_cap.read()
        if ok:
            self._content.update_idletasks()
            width = max(self._content.winfo_width(), 200)
            height = max(self._content.winfo_height(), 150)
            frame = cv2.resize(frame, (width, height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
            self._video_lbl.configure(image=photo)
            self._video_lbl.image = photo
        self._frame_job = self.after(33, self._advance_frame)

    def _start_countdown(self):
        self._end_time = time.time() + self.display_secs
        self._tick()

    def _tick(self):
        remaining = self._end_time - time.time()
        if remaining <= 0:
            self._finish()
            return
        self._time_lbl.config(text=f"{remaining:.0f}s")
        self._prog_bar.place(
            x=0,
            y=0,
            relwidth=remaining / self.display_secs,
            height=3,
        )
        self._timer_id = self.after(200, self._tick)

    def _finish(self):
        self._cleanup()
        self.on_done(self.msg)

    def _cleanup(self):
        if self._timer_id:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        if self._frame_job:
            self.after_cancel(self._frame_job)
            self._frame_job = None
        if self._video_cap:
            self._video_cap.release()
            self._video_cap = None

    def destroy(self):
        self._cleanup()
        super().destroy()
