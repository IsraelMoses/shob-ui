"""
Minimal FTP receiver for camera image uploads.

The IDIS camera can upload event images via FTP. This server accepts
uploads from known device IPs and forwards them to the same UI queue used
by the regular HTTP upload path.
"""

from __future__ import annotations

import socket
import threading
import time
from datetime import datetime
from pathlib import Path

from .backend import (
    BASE_DIR,
    FTP_PASSIVE_PORT_END,
    FTP_PASSIVE_PORT_START,
    FTP_PASSWORD,
    FTP_SERVER_HOST,
    FTP_SERVER_PORT,
    FTP_USERNAME,
    device_by_ip,
)
from .server import msg_queue, _log


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".mp4"}
FTP_TEST_FILENAMES = {"upload_test.txt"}


def _safe_device_lookup(ip: str):
    try:
        dev = device_by_ip(ip)
        if not dev:
            return None
        return dev
    except Exception:
        return None


def _media_ext(filename: str, first_bytes: bytes = b"") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in SUPPORTED_EXTENSIONS:
        return ".jpg" if ext == ".jpeg" else ext
    if first_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(first_bytes) > 12 and first_bytes[4:8] == b"ftyp":
        return ".mp4"
    return ""


def _safe_filename(name: str) -> str:
    clean = Path((name or "upload.jpg").replace("\\", "/")).name.strip()
    return clean or "upload.jpg"


class _FtpSession:
    def __init__(self, control: socket.socket, address):
        self.control = control
        self.client_ip = address[0]
        self.logged_in = False
        self.username = ""
        self.passive_socket = None
        self.active_target = None
        self.cwd = "/"
        self.control.settimeout(300)

    def run(self):
        try:
            self._send("220 Shob UI FTP receiver ready")
            while True:
                line = self._readline()
                if not line:
                    break
                command, arg = self._split_command(line)
                if command in {"USER", "PASS", "QUIT", "NOOP", "SYST", "FEAT", "OPTS"}:
                    if command == "USER":
                        self._cmd_user(arg)
                    elif command == "PASS":
                        self._cmd_pass(arg)
                    elif command == "QUIT":
                        self._send("221 Goodbye")
                        break
                    elif command == "NOOP":
                        self._send("200 OK")
                    elif command == "SYST":
                        self._send("215 UNIX Type: L8")
                    elif command == "FEAT":
                        self._send("211-Features\r\n PASV\r\n EPSV\r\n UTF8\r\n211 End")
                    else:
                        self._send("200 OK")
                    continue

                if not self.logged_in:
                    self._send("530 Login required")
                    continue

                if command in {"TYPE", "MODE", "STRU"}:
                    self._send("200 OK")
                elif command == "PWD":
                    self._send(f'257 "{self.cwd}" is current directory')
                elif command == "CWD":
                    self.cwd = "/" + arg.strip("/\\")
                    self._send("250 Directory changed")
                elif command == "MKD":
                    self._send(f'257 "{arg}" directory created')
                elif command == "PASV":
                    self._cmd_pasv()
                elif command == "EPSV":
                    self._cmd_epsv()
                elif command == "PORT":
                    self._cmd_port(arg)
                elif command == "STOR":
                    self._cmd_stor(arg)
                elif command == "LIST":
                    self._send_listing()
                else:
                    self._send("502 Command not implemented")
        except Exception as exc:
            _log(f"FTP session error from {self.client_ip}: {exc}", level="warning")
        finally:
            self._close_passive()
            try:
                self.control.close()
            except Exception:
                pass

    def _readline(self) -> str:
        data = bytearray()
        while not data.endswith(b"\n"):
            chunk = self.control.recv(1)
            if not chunk:
                return ""
            data.extend(chunk)
            if len(data) > 4096:
                break
        return data.decode("utf-8", errors="replace").strip()

    def _send(self, message: str):
        self.control.sendall((message + "\r\n").encode("utf-8"))

    def _split_command(self, line: str) -> tuple[str, str]:
        if " " in line:
            command, arg = line.split(" ", 1)
        else:
            command, arg = line, ""
        return command.strip().upper(), arg.strip()

    def _cmd_user(self, arg: str):
        self.username = arg
        self._send("331 Password required")

    def _cmd_pass(self, arg: str):
        if self.username == FTP_USERNAME and arg == FTP_PASSWORD:
            self.logged_in = True
            self._send("230 Login successful")
        else:
            _log(f"FTP login failed from {self.client_ip} user={self.username}", level="warning")
            self._send("530 Login incorrect")

    def _cmd_pasv(self):
        self._close_passive()
        psock = self._open_passive_socket()
        host = self.control.getsockname()[0]
        if host in {"0.0.0.0", "::"}:
            host = self.control.getsockname()[0]
        if host == "0.0.0.0":
            host = self._local_ip_for_client()
        port = psock.getsockname()[1]
        parts = host.split(".") + [str(port // 256), str(port % 256)]
        self._send("227 Entering Passive Mode (" + ",".join(parts) + ")")

    def _cmd_epsv(self):
        self._close_passive()
        psock = self._open_passive_socket()
        port = psock.getsockname()[1]
        self._send(f"229 Entering Extended Passive Mode (|||{port}|)")

    def _open_passive_socket(self) -> socket.socket:
        last_error = None
        for port in range(FTP_PASSIVE_PORT_START, FTP_PASSIVE_PORT_END + 1):
            try:
                psock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                psock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                psock.bind((FTP_SERVER_HOST, port))
                psock.listen(1)
                psock.settimeout(30)
                self.passive_socket = psock
                return psock
            except OSError as exc:
                last_error = exc
                try:
                    psock.close()
                except Exception:
                    pass
        raise RuntimeError(f"No passive FTP port available: {last_error}")

    def _cmd_port(self, arg: str):
        try:
            parts = [int(p) for p in arg.split(",")]
            host = ".".join(str(p) for p in parts[:4])
            port = parts[4] * 256 + parts[5]
            self.active_target = (host, port)
            self._send("200 PORT command successful")
        except Exception:
            self._send("501 Invalid PORT command")

    def _data_socket(self) -> socket.socket:
        if self.passive_socket is not None:
            self._send("150 Opening data connection")
            conn, _addr = self.passive_socket.accept()
            self._close_passive()
            return conn
        if self.active_target is not None:
            self._send("150 Opening active data connection")
            conn = socket.create_connection(self.active_target, timeout=20)
            self.active_target = None
            return conn
        raise RuntimeError("No FTP data connection was prepared")

    def _cmd_stor(self, arg: str):
        filename = _safe_filename(arg)
        device = _safe_device_lookup(self.client_ip)
        if device is None:
            _log(f"FTP upload blocked from unknown device IP {self.client_ip}", level="warning")
            self._send("550 Unknown device IP")
            return

        tmp = BASE_DIR / "tmp"
        tmp.mkdir(exist_ok=True)
        raw_path = tmp / f"{int(time.time() * 1000)}_{filename}"
        first = b""

        try:
            with self._data_socket() as data:
                with raw_path.open("wb") as f:
                    while True:
                        chunk = data.recv(64 * 1024)
                        if not chunk:
                            break
                        if not first:
                            first = chunk[:32]
                        f.write(chunk)
        except Exception as exc:
            try:
                raw_path.unlink()
            except Exception:
                pass
            _log(f"FTP upload failed from {self.client_ip}: {exc}", level="warning")
            self._send("451 Upload failed")
            return

        ext = _media_ext(filename, first)
        if not ext:
            if filename.lower() in FTP_TEST_FILENAMES:
                _log(f"FTP test upload accepted from {self.client_ip}: {filename}")
                try:
                    raw_path.unlink()
                except Exception:
                    pass
                self._send("226 Transfer complete")
                return

            _log(f"FTP unsupported file from {self.client_ip}: {filename}", level="warning")
            try:
                raw_path.unlink()
            except Exception:
                pass
            self._send("550 Unsupported media type")
            return

        final_path = raw_path.with_suffix(ext)
        if final_path != raw_path:
            raw_path.replace(final_path)

        received_at = datetime.now()
        _log(
            f"FTP upload accepted from {self.client_ip} -> "
            f"device={device['name']} file={final_path.name}"
        )
        msg_queue.put({
            "device": device,
            "path": final_path,
            "ext": ext,
            "received_at": received_at,
            "blocked": False,
            "sender_ip": self.client_ip,
            "source": "ftp",
        })
        self._send("226 Transfer complete")

    def _send_listing(self):
        try:
            with self._data_socket() as data:
                data.sendall(b"")
            self._send("226 Directory send OK")
        except Exception:
            self._send("451 LIST failed")

    def _local_ip_for_client(self) -> str:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.connect((self.client_ip, 1))
            return probe.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            probe.close()

    def _close_passive(self):
        if self.passive_socket is not None:
            try:
                self.passive_socket.close()
            except Exception:
                pass
            self.passive_socket = None


def start_ftp_server(on_ready=None, on_error=None):
    def _run():
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((FTP_SERVER_HOST, FTP_SERVER_PORT))
            srv.listen(20)
            _log(f"FTP receiver listening on {FTP_SERVER_HOST}:{FTP_SERVER_PORT}")
            if on_ready:
                on_ready(FTP_SERVER_HOST, FTP_SERVER_PORT)

            while True:
                conn, addr = srv.accept()
                threading.Thread(
                    target=_FtpSession(conn, addr).run,
                    daemon=True,
                ).start()
        except Exception as exc:
            _log(f"FTP receiver error: {exc}", level="error")
            if on_error:
                on_error(exc)

    threading.Thread(target=_run, daemon=True).start()
