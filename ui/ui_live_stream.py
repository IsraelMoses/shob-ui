"""
Live RTSP stream widget for the main player area.
"""

import threading
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from core.rtsp_service import build_rtsp_url

from .ui_theme import C


class LiveStreamSlot(tk.Frame):
    def __init__(self, parent, device, target, on_close=None, on_status=None, **kw):
        super().__init__(parent, bg="#050b13", **kw)
        self.device = device
        self.target = target
        self.on_close = on_close
        self.on_status = on_status
        self._running = False
        self._reader_thread = None
        self._cap = None
        self._frame_job = None
        self._health_job = None
        self._photo_ref = None
        self._latest_frame = None
        self._latest_frame_at = 0.0
        self._lock = threading.Lock()
        self._last_reported_status = None
        self._build()

    def _build(self):
        bar = tk.Frame(self, bg=C["slot_bar"], height=32)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)

        tk.Frame(bar, bg="#24ffb2", width=3).pack(side=tk.LEFT, fill=tk.Y)
        tk.Label(
            bar,
            text=f"  LIVE  {self.device['name']}",
            font=("Helvetica", 9, "bold"),
            bg=C["slot_bar"],
            fg=C["slot_bar_tx"],
        ).pack(side=tk.LEFT)
        tk.Label(
            bar,
            text=self.device["ip"],
            font=("Helvetica", 8),
            bg=C["slot_bar"],
            fg=C["tx_secondary"],
        ).pack(side=tk.LEFT, padx=6)

        close_btn = tk.Button(
            bar,
            text="Stop",
            command=self._close,
            bg="#7b1125",
            fg=C["tx_white"],
            activebackground="#a01933",
            activeforeground=C["tx_white"],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        close_btn.pack(side=tk.RIGHT, padx=8, pady=4)

        self._status_lbl = tk.Label(
            bar,
            text="Connecting...",
            font=("Helvetica", 8, "bold"),
            bg=C["slot_bar"],
            fg=C["status_warn"],
        )
        self._status_lbl.pack(side=tk.RIGHT, padx=8)

        self._content = tk.Frame(self, bg="#050b13")
        self._content.pack(fill=tk.BOTH, expand=True)
        self._video_lbl = tk.Label(
            self._content,
            text="Opening live stream...",
            font=("Helvetica", 16, "bold"),
            bg="#050b13",
            fg="#3c5671",
        )
        self._video_lbl.place(relx=0.5, rely=0.5, anchor="center")

    def _start(self):
        if self._running:
            return
        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()
        self._frame_job = self.after(33, self._draw_latest_frame)
        self._health_job = self.after(1000, self._check_stream_health)

    def _read_loop(self):
        url = build_rtsp_url(self.target)
        cap = None
        try:
            try:
                cap = cv2.VideoCapture(
                    url,
                    cv2.CAP_FFMPEG,
                    [
                        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                        5000,
                        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                        5000,
                    ],
                )
            except Exception:
                cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

            self._cap = cap
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if not cap.isOpened():
                self._report_status("failed", "Could not open RTSP stream")
                return

            self._report_status("connected", "")
            while self._running:
                ok, frame = cap.read()
                if ok and frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                        self._latest_frame_at = time.time()
                else:
                    time.sleep(0.1)
        except Exception as exc:
            self._report_status("failed", str(exc))
        finally:
            if cap is not None:
                cap.release()
            self._cap = None

    def _draw_latest_frame(self):
        if not self._running:
            return

        frame = None
        with self._lock:
            if self._latest_frame is not None:
                frame = self._latest_frame.copy()

        if frame is not None:
            try:
                self._content.update_idletasks()
                box_w = max(self._content.winfo_width(), 240)
                box_h = max(self._content.winfo_height(), 180)
                h, w = frame.shape[:2]
                scale = min(box_w / max(w, 1), box_h / max(h, 1))
                new_w = max(int(w * scale), 1)
                new_h = max(int(h * scale), 1)
                frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                photo = ImageTk.PhotoImage(image=Image.fromarray(frame))
                self._photo_ref = photo
                self._video_lbl.configure(image=photo, text="")
                self._video_lbl.image = photo
                self._video_lbl.place(relx=0.5, rely=0.5, anchor="center")
                if self._last_reported_status == "waiting":
                    self._report_status("connected", "")
            except Exception as exc:
                self._video_lbl.configure(
                    image="",
                    text=f"Live display error:\n{exc}",
                    fg="#ef4444",
                )

        self._frame_job = self.after(33, self._draw_latest_frame)

    def _check_stream_health(self):
        if not self._running:
            return
        if self._latest_frame_at and time.time() - self._latest_frame_at > 6:
            self._set_status_text("Waiting for frames...", C["status_warn"])
            self._report_status("waiting", "No recent frame")
        self._health_job = self.after(1000, self._check_stream_health)

    def _report_status(self, status: str, error: str = ""):
        if status == self._last_reported_status and status != "failed":
            return
        self._last_reported_status = status
        try:
            self.after(0, lambda: self._apply_status(status, error))
        except RuntimeError:
            pass

    def _apply_status(self, status: str, error: str = ""):
        if not self.winfo_exists():
            return
        if status == "connected":
            self._set_status_text("Live", C["status_ok"])
        elif status == "waiting":
            self._set_status_text("Waiting...", C["status_warn"])
        else:
            self._set_status_text("Failed", C["status_err"])
            self._video_lbl.configure(
                image="",
                text=f"Live stream failed\n{error}",
                fg="#ef4444",
            )
        if self.on_status:
            self.on_status(self.device, status, error)

    def _set_status_text(self, text: str, color: str):
        self._status_lbl.configure(text=text, fg=color)

    def _close(self):
        self._cleanup()
        if self.on_close:
            self.on_close(self.device, self)
        self.destroy()

    def _cleanup(self):
        self._running = False
        if self._frame_job:
            try:
                self.after_cancel(self._frame_job)
            except Exception:
                pass
            self._frame_job = None
        if self._health_job:
            try:
                self.after_cancel(self._health_job)
            except Exception:
                pass
            self._health_job = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def destroy(self):
        self._cleanup()
        super().destroy()
