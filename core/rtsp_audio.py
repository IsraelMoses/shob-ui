"""
Optional RTSP audio playback for live camera slots.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from core.rtsp_service import RtspTarget, build_rtsp_url


def _candidate_vlc_paths() -> list[str]:
    candidates = [
        shutil.which("vlc"),
        shutil.which("vlc.exe"),
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ]
    return [item for item in candidates if item and Path(item).exists()]


def _candidate_ffplay_paths() -> list[str]:
    candidates = [
        shutil.which("ffplay"),
        shutil.which("ffplay.exe"),
    ]
    return [item for item in candidates if item and Path(item).exists()]


class RtspAudioSession:
    def __init__(self, target: RtspTarget):
        self.target = target
        self._proc: subprocess.Popen | None = None
        self.backend = ""

    def start(self):
        if self.is_running():
            return

        url = build_rtsp_url(self.target)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        ffplay = next(iter(_candidate_ffplay_paths()), "")
        if ffplay:
            self.backend = "ffplay"
            cmd = [
                ffplay,
                "-nodisp",
                "-vn",
                "-loglevel",
                "error",
                "-fflags",
                "nobuffer",
                "-flags",
                "low_delay",
                url,
            ]
        else:
            vlc = next(iter(_candidate_vlc_paths()), "")
            if not vlc:
                raise RuntimeError("No RTSP audio player found. Install VLC or ffplay.")
            self.backend = "VLC"
            cmd = [
                vlc,
                "--intf",
                "dummy",
                "--no-video",
                "--quiet",
                "--network-caching=250",
                url,
            ]

        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            env=os.environ.copy(),
        )
        if self._proc.poll() is not None:
            code = self._proc.returncode
            self._proc = None
            raise RuntimeError(f"RTSP audio player exited immediately ({self.backend}, code {code}).")

    def stop(self):
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None
