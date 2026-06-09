"""
Live RTSP stream widget for the main player area.
"""

import threading
import time
import tkinter as tk

import cv2
from PIL import Image, ImageTk

from core.onvif_ptz import OnvifZoomController
from core.rtsp_audio import RtspAudioSession
from core.rtsp_service import build_rtsp_url

from .ui_theme import C


class LiveStreamSlot(tk.Frame):
    def __init__(
        self,
        parent,
        device,
        target,
        profile=None,
        on_close=None,
        on_status=None,
        **kw,
    ):
        super().__init__(parent, bg="#050b13", **kw)
        self.device = device
        self.target = target
        self.profile = profile or {}
        self.on_close = on_close
        self.on_status = on_status
        self._running = False
        self._reader_thread = None
        self._cap = None
        self._audio = None
        self._audio_enabled = False
        self._audio_btn = None
        self._zoom_controller = None
        self._zoom_active = False
        self._ptz_lock = threading.Lock()
        self._frame_job = None
        self._health_job = None
        self._photo_ref = None
        self._latest_frame = None
        self._latest_frame_at = 0.0
        self._lock = threading.Lock()
        self._last_reported_status = None
        self._stream_generation = 0
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

        refresh_btn = tk.Button(
            bar,
            text="Refresh",
            command=self._restart_stream,
            bg="#0b342e",
            fg="#38e6bd",
            activebackground="#0e483e",
            activeforeground="#38e6bd",
            relief=tk.FLAT,
            highlightbackground="#1d6658",
            highlightthickness=1,
            bd=0,
            padx=9,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )
        refresh_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=4)

        self._status_lbl = tk.Label(
            bar,
            text="Connecting...",
            font=("Helvetica", 8, "bold"),
            bg=C["slot_bar"],
            fg=C["status_warn"],
        )
        self._status_lbl.pack(side=tk.RIGHT, padx=8)

        if self._is_idis_profile():
            self._build_idis_controls()

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

    def _is_idis_profile(self) -> bool:
        return (self.profile.get("camera_type") or "").strip().lower() == "idis"

    def _build_idis_controls(self):
        controls = tk.Frame(self, bg="#07131e", height=34)
        controls.pack(fill=tk.X, side=tk.TOP)
        controls.pack_propagate(False)

        tk.Label(
            controls,
            text="IDIS",
            font=("Segoe UI", 8, "bold"),
            bg="#07131e",
            fg="#36e6bd",
        ).pack(side=tk.LEFT, padx=(9, 7))

        zoom_in = self._make_control_button(controls, "Zoom +")
        zoom_in.bind("<ButtonPress-1>", lambda _e: self._start_zoom(0.55))
        zoom_in.bind("<ButtonRelease-1>", self._stop_zoom)
        zoom_in.bind("<Leave>", self._stop_zoom)
        zoom_in.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        zoom_out = self._make_control_button(controls, "Zoom -")
        zoom_out.bind("<ButtonPress-1>", lambda _e: self._start_zoom(-0.55))
        zoom_out.bind("<ButtonRelease-1>", self._stop_zoom)
        zoom_out.bind("<Leave>", self._stop_zoom)
        zoom_out.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        stop_zoom = self._make_control_button(controls, "Zoom Stop")
        stop_zoom.configure(command=lambda: self._stop_zoom(force=True))
        stop_zoom.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self._audio_btn = self._make_control_button(controls, "Sound On")
        self._audio_btn.configure(command=self._toggle_audio)
        self._audio_btn.pack(side=tk.RIGHT, padx=9, pady=5)

    def _make_control_button(self, parent, text):
        return tk.Button(
            parent,
            text=text,
            bg="#0b342e",
            fg="#38e6bd",
            activebackground="#0e483e",
            activeforeground="#38e6bd",
            relief=tk.FLAT,
            bd=0,
            padx=9,
            pady=2,
            font=("Segoe UI", 8, "bold"),
            cursor="hand2",
        )

    def _start(self):
        if self._running:
            return
        self._running = True
        self._start_reader()
        self._frame_job = self.after(33, self._draw_latest_frame)
        self._health_job = self.after(1000, self._check_stream_health)

    def _start_reader(self):
        self._stream_generation += 1
        generation = self._stream_generation
        self._reader_thread = threading.Thread(
            target=self._read_loop,
            args=(generation,),
            daemon=True,
        )
        self._reader_thread.start()

    def _read_loop(self, generation: int):
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

            if generation != self._stream_generation or not self._running:
                return
            self._cap = cap
            try:
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            except Exception:
                pass

            if not cap.isOpened():
                self._report_status("failed", "Could not open RTSP stream", generation)
                return

            self._report_status("connected", "", generation)
            while self._running and generation == self._stream_generation:
                ok, frame = cap.read()
                if ok and frame is not None:
                    with self._lock:
                        if generation == self._stream_generation:
                            self._latest_frame = frame
                            self._latest_frame_at = time.time()
                else:
                    time.sleep(0.1)
        except Exception as exc:
            self._report_status("failed", str(exc), generation)
        finally:
            if cap is not None:
                cap.release()
            if generation == self._stream_generation:
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

    def _report_status(self, status: str, error: str = "", generation: int | None = None):
        if generation is not None and generation != self._stream_generation:
            return
        if status == self._last_reported_status and status != "failed":
            return
        self._last_reported_status = status
        try:
            self.after(0, lambda: self._apply_status(status, error, generation))
        except RuntimeError:
            pass

    def _apply_status(self, status: str, error: str = "", generation: int | None = None):
        if not self.winfo_exists():
            return
        if generation is not None and generation != self._stream_generation:
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

    def _get_zoom_controller(self) -> OnvifZoomController:
        if self._zoom_controller is None:
            self._zoom_controller = OnvifZoomController(
                host=self.target.host,
                username=self.target.username,
                password=self.target.password,
                onvif_port=self.profile.get("onvif_port", 80),
            )
        return self._zoom_controller

    def _run_ptz_command(self, action, success_text: str):
        def _worker():
            try:
                with self._ptz_lock:
                    controller = self._get_zoom_controller()
                    action(controller)
                self.after(0, lambda: self._set_status_text(success_text, C["status_ok"]))
            except Exception as exc:
                message = str(exc)
                self._zoom_controller = None
                self._zoom_active = False
                self.after(0, lambda: self._set_status_text(f"Zoom failed: {message}", C["status_err"]))

        threading.Thread(target=_worker, daemon=True).start()

    def _start_zoom(self, velocity: float):
        if not self._is_idis_profile():
            return
        self._zoom_active = True
        label = "Zooming in..." if velocity > 0 else "Zooming out..."
        self._set_status_text(label, C["status_warn"])
        self._run_ptz_command(
            lambda controller: controller.continuous_zoom(velocity),
            "Zoom active",
        )

    def _stop_zoom(self, _event=None, force: bool = False):
        if not self._is_idis_profile():
            return
        if not self._zoom_active and not force:
            return
        self._zoom_active = False
        self._set_status_text("Stopping zoom...", C["status_warn"])
        self._run_ptz_command(lambda controller: controller.stop_zoom(), "Zoom stopped")

    def _toggle_audio(self):
        if not self._is_idis_profile():
            return
        if self._audio_enabled:
            self._stop_audio()
            return
        try:
            self._audio = RtspAudioSession(self.target)
            self._audio.start()
        except Exception as exc:
            self._audio = None
            self._audio_enabled = False
            self._set_status_text(f"Sound failed: {exc}", C["status_err"])
            return
        self._audio_enabled = True
        if self._audio_btn:
            self._audio_btn.configure(text="Sound Off", bg="#123b5c", fg="#93d5ff")
        self._set_status_text(f"Sound on ({self._audio.backend})", C["status_ok"])

    def _stop_audio(self):
        if self._audio is not None:
            self._audio.stop()
        self._audio = None
        self._audio_enabled = False
        if self._audio_btn:
            self._audio_btn.configure(text="Sound On", bg="#0b342e", fg="#38e6bd")
        self._set_status_text("Sound off", C["status_warn"])

    def _restart_stream(self):
        if not self.winfo_exists():
            return

        self._stream_generation += 1
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        with self._lock:
            self._latest_frame = None
            self._latest_frame_at = 0.0
        self._photo_ref = None
        self._last_reported_status = None
        self._running = True
        self._set_status_text("Reconnecting...", C["status_warn"])
        self._video_lbl.configure(
            image="",
            text="Reconnecting live stream...",
            fg="#3c5671",
        )
        self._video_lbl.image = None
        self._start_reader()
        if not self._frame_job:
            self._frame_job = self.after(33, self._draw_latest_frame)
        if not self._health_job:
            self._health_job = self.after(1000, self._check_stream_health)

    def _close(self):
        self._cleanup()
        if self.on_close:
            self.on_close(self.device, self)
        self.destroy()

    def _cleanup(self):
        self._running = False
        self._stream_generation += 1
        self._stop_audio()
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
