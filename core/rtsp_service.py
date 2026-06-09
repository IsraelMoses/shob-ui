"""
Reusable RTSP helpers for camera onboarding and connection checks.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from ipaddress import ip_address
from typing import Any
from urllib.parse import quote


DEFAULT_RTSP_PORT = 8554
DIRECT_RTSP_PORT = 554
DEFAULT_RTSP_PATH = "/cam/realmonitor?channel=1&subtype=0"

CAMERA_DEFAULTS = {
    "Generic RTSP": {"port": DEFAULT_RTSP_PORT, "path": DEFAULT_RTSP_PATH},
    "Dahua": {"port": DEFAULT_RTSP_PORT, "path": DEFAULT_RTSP_PATH},
    "IDIS": {"port": DEFAULT_RTSP_PORT, "path": "/trackID=1"},
    "Hikvision": {"port": DEFAULT_RTSP_PORT, "path": "/Streaming/Channels/101"},
    "Axis": {"port": DEFAULT_RTSP_PORT, "path": "/axis-media/media.amp"},
}


@dataclass(frozen=True)
class RtspTarget:
    host: str
    port: int
    username: str
    password: str
    stream_path: str


def _is_direct_camera_host(host: str) -> bool:
    try:
        parsed = ip_address((host or "").strip())
    except ValueError:
        return False
    return parsed.is_private or parsed.is_loopback or parsed.is_link_local


def camera_defaults(camera_type: str, host: str = "") -> dict[str, Any]:
    defaults = dict(CAMERA_DEFAULTS.get(camera_type, CAMERA_DEFAULTS["Generic RTSP"]))
    if _is_direct_camera_host(host):
        defaults["port"] = DIRECT_RTSP_PORT
    return defaults


def normalize_stream_path(stream_path: str) -> str:
    path = (stream_path or DEFAULT_RTSP_PATH).strip()
    if not path.startswith("/"):
        path = "/" + path
    return path


def build_rtsp_url(target: RtspTarget, mask_password: bool = False) -> str:
    username = quote(target.username, safe="")
    password = "***" if mask_password else quote(target.password, safe="")
    path = normalize_stream_path(target.stream_path)
    return f"rtsp://{username}:{password}@{target.host}:{int(target.port)}{path}"


def make_target(
    host: str,
    port: int,
    username: str,
    password: str,
    stream_path: str,
) -> RtspTarget:
    return RtspTarget(
        host=(host or "").strip(),
        port=int(port or DEFAULT_RTSP_PORT),
        username=(username or "").strip(),
        password=password or "",
        stream_path=normalize_stream_path(stream_path),
    )


def test_rtsp_connection(target: RtspTarget, timeout_seconds: int = 5) -> dict[str, Any]:
    """
    Try the same flow as rtsp_debug.py: TCP probe, open RTSP, read first frame.
    The returned URL is masked so credentials never leak to logs or UI.
    """
    masked_url = build_rtsp_url(target, mask_password=True)
    result: dict[str, Any] = {
        "ok": False,
        "status": "failed",
        "stage": "not_started",
        "error": "",
        "rtsp_url": masked_url,
        "frame_shape": "",
        "fps": None,
    }

    try:
        result["stage"] = "tcp"
        with socket.create_connection((target.host, int(target.port)), timeout=timeout_seconds):
            pass
    except Exception as exc:
        result["error"] = f"TCP connection failed: {exc}"
        return result

    cap = None
    try:
        import cv2

        result["stage"] = "open_stream"
        url = build_rtsp_url(target)
        try:
            cap = cv2.VideoCapture(
                url,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    timeout_seconds * 1000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    timeout_seconds * 1000,
                ],
            )
        except Exception:
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)

        time.sleep(1)
        if not cap.isOpened():
            result["error"] = (
                "RTSP stream did not open. Check username/password, RTSP path, "
                "port forward, and camera WAN RTSP access."
            )
            return result

        result["stage"] = "read_frame"
        started = time.time()
        last = started
        frame = None
        ret = False
        while time.time() - started < timeout_seconds:
            ret, frame = cap.read()
            now = time.time()
            if ret and frame is not None:
                delta = max(now - last, 0.001)
                result["fps"] = round(1 / delta, 2)
                result["frame_shape"] = "x".join(str(v) for v in frame.shape)
                result["ok"] = True
                result["status"] = "connected"
                result["stage"] = "connected"
                return result
            last = now
            time.sleep(0.1)

        result["error"] = "RTSP stream opened, but no video frame was received."
        return result
    except Exception as exc:
        result["error"] = f"RTSP check failed: {exc}"
        return result
    finally:
        if cap is not None:
            cap.release()
