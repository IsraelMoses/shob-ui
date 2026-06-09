"""
server.py
=========
Manages the embedded HTTPS/HTTP server.
Cameras POST a JPEG or MP4 to POST /upload
Can expose an optional plain debug server on port 8080 when enabled.

Incoming messages are placed in a shared queue for the UI to consume.
"""

import logging
import queue
import ssl
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from flask import Flask, request, jsonify

from .backend import (
    device_by_ip,
    BASE_DIR,
    CERT_FILE,
    KEY_FILE,
    SERVER_HOST,
    SERVER_PORT,
    TLS_ENABLED,
    TRUSTED_PROXY_IPS,
    ADMIN_EVENT_ALLOWED_IPS,
    ADMIN_EVENT_TOKEN,
)

# Shared queue consumed by the UI
msg_queue: queue.Queue = queue.Queue()

# Flask upload server
flask_app = Flask(__name__)


LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "backend.log"
LOG_DIR.mkdir(exist_ok=True)

_logger = logging.getLogger("shob.backend")
if not _logger.handlers:
    _logger.setLevel(logging.INFO)
    _file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    _file_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    ))
    _logger.addHandler(_file_handler)
    _logger.propagate = False


def _log(message: str, level: str = "info"):
    text = str(message)
    print(text)
    if level == "error":
        _logger.error(text)
    elif level == "warning":
        _logger.warning(text)
    else:
        _logger.info(text)


def _safe_device_lookup(ip: str):
    """
    Returns the device dict if IP is known, otherwise None.
    Handles both 'returns None' and 'raises exception' styles.
    """
    try:
        dev = device_by_ip(ip)
        if not dev:
            return None
        return dev
    except Exception:
        return None


def _format_headers(headers) -> dict:
    return {k: v for k, v in headers.items()}


def _preview_body(body: bytes, max_bytes: int = 1500) -> str:
    if not body:
        return ""
    preview = body[:max_bytes]
    try:
        return preview.decode("utf-8")
    except UnicodeDecodeError:
        return preview.hex(" ")


def _client_ip() -> str:
    remote_addr = request.remote_addr or "unknown"
    if remote_addr in TRUSTED_PROXY_IPS:
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        first_hop = forwarded_for.split(",", 1)[0].strip()
        if first_hop:
            return first_hop
    return remote_addr


def _log_blocked_post(source: str, sender_ip: str, path: str, headers, body: bytes):
    now = datetime.now().isoformat(timespec="seconds")
    _log("\n" + "=" * 28 + " BLOCKED POST " + "=" * 28, level="warning")
    _log(f"Time:        {now}", level="warning")
    _log(f"Source:      {source}", level="warning")
    _log(f"Client IP:   {sender_ip}", level="warning")
    _log(f"Path:        {path}", level="warning")
    _log("Reason:      sender IP is not in device database", level="warning")
    _log("\n--- HEADERS ---", level="warning")
    _log(headers, level="warning")

    if body:
        _log("\n--- BODY (first 500 bytes) ---", level="warning")
        _log(body[:500], level="warning")

    _log("=" * 70, level="warning")

    # Also push this event to the UI queue so the UI can show it
    msg_queue.put({
        "device": None,
        "blocked": True,
        "sender_ip": sender_ip,
        "path": path,
        "headers": _format_headers(headers),
        "body_preview": body[:500],
        "received_at": datetime.now(),
        "source": source,
    })


def _media_ext(filename: str = "", content_type: str = "", body: bytes = b"") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext in (".jpeg", ".jpg", ".mp4"):
        return ".jpg" if ext == ".jpeg" else ext

    ct = (content_type or "").lower()
    if "jpeg" in ct or "jpg" in ct:
        return ".jpg"
    if "mp4" in ct:
        return ".mp4"

    if body.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if len(body) > 12 and body[4:8] == b"ftyp":
        return ".mp4"

    return ""


@flask_app.route("/internal/admin/device", methods=["POST"])
def admin_device_event():
    sender_ip = _client_ip()
    _log(f"Admin device event from {sender_ip}")
    if ADMIN_EVENT_ALLOWED_IPS and sender_ip not in ADMIN_EVENT_ALLOWED_IPS:
        _log(f"Admin event blocked by IP policy: {sender_ip}", level="warning")
        return jsonify({
            "error": "blocked",
            "reason": "sender IP is not allowed",
            "sender_ip": sender_ip,
        }), 403

    if ADMIN_EVENT_TOKEN:
        provided = request.headers.get("X-Shob-Admin-Token", "")
        if provided != ADMIN_EVENT_TOKEN:
            _log(f"Admin event unauthorized from {sender_ip}", level="warning")
            return jsonify({"error": "unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action", payload.get("event", "add"))).strip().lower()
    if payload.get("deleted") is True:
        action = "delete"
    name = str(payload.get("name", "")).strip()
    ip = str(payload.get("ip", "")).strip()
    uuid = str(payload.get("uuid", "")).strip()

    if action in {"delete", "remove"}:
        if not uuid and not ip and not name:
            return jsonify({
                "error": "invalid payload",
                "required_any": ["uuid", "ip", "name"],
            }), 400
    else:
        action = "add"
        if not name or not ip or not uuid:
            return jsonify({
                "error": "invalid payload",
                "required": ["name", "ip", "uuid"],
            }), 400

    received_at = datetime.now()
    _log(
        f"Admin event accepted: action={action} name={name or '-'} ip={ip or '-'} uuid={uuid or '-'}"
    )
    msg_queue.put({
        "admin_event": True,
        "action": action,
        "name": name,
        "ip": ip,
        "uuid": uuid,
        "sender_ip": sender_ip,
        "received_at": received_at,
    })

    return jsonify({"status": "ok"}), 200


@flask_app.route("/post-test", methods=["POST"])
@flask_app.route("/event-test", methods=["POST"])
@flask_app.route("/webhook-test", methods=["POST"])
def post_test():
    """
    Diagnostic endpoint for camera event/webhook testing.
    Accepts any POST body and logs it without trying to parse it as media.
    """
    sender_ip = _client_ip()
    device = _safe_device_lookup(sender_ip)
    raw_data = request.get_data(cache=True)
    received_at = datetime.now()
    headers = _format_headers(request.headers)
    path = request.full_path if request.query_string else request.path
    files = [
        {
            "field": field,
            "filename": storage.filename,
            "content_type": storage.content_type,
            "content_length": storage.content_length,
        }
        for field, storage in request.files.items(multi=True)
    ]

    _log("\n" + "=" * 29 + " POST TEST " + "=" * 29)
    _log(f"Time:          {received_at.isoformat(timespec='seconds')}")
    _log(f"Client IP:     {sender_ip}")
    _log(f"Known device:  {'yes' if device else 'no'}")
    if device:
        _log(f"Device:        {device.get('name', '-')} ({device.get('ip', '-')})")
    _log(f"Path:          {path}")
    _log(f"Content-Type:  {request.content_type or '-'}")
    _log(f"Content-Length:{request.content_length or 0}")
    _log("\n--- HEADERS ---")
    _log(headers)
    if files:
        _log("\n--- FILES ---")
        _log(files)
    if raw_data:
        _log("\n--- BODY PREVIEW ---")
        _log(_preview_body(raw_data))
    _log("=" * 69)

    msg_queue.put({
        "post_test": True,
        "device": device,
        "sender_ip": sender_ip,
        "path": path,
        "headers": headers,
        "content_type": request.content_type or "",
        "content_length": request.content_length or len(raw_data),
        "body_preview": _preview_body(raw_data, max_bytes=500),
        "files": files,
        "known_device": bool(device),
        "received_at": received_at,
    })

    return jsonify({
        "status": "ok",
        "kind": "post_test",
        "sender_ip": sender_ip,
        "known_device": bool(device),
        "device": device["name"] if device else None,
        "path": path,
        "content_type": request.content_type,
        "bytes": request.content_length or len(raw_data),
    }), 200


@flask_app.route("/camera-post", methods=["POST"])
@flask_app.route("/upload", methods=["POST"])
def upload():
    _log("\n==== FLASK UPLOAD RECEIVED ====")
    _log(f"Time: {datetime.now().isoformat(timespec='seconds')}")
    _log(f"Client IP: {request.remote_addr}")
    _log(f"Path: {request.path}")
    _log(f"Content-Type: {request.content_type}")
    _log(request.headers)
    sender_ip = _client_ip()
    device = _safe_device_lookup(sender_ip)

    # Read raw body once if needed for blocked logging or raw-body uploads
    raw_data = request.get_data(cache=True)

    if device is None:
        _log_blocked_post(
            source="flask-upload-server",
            sender_ip=sender_ip,
            path=request.full_path if request.query_string else request.path,
            headers=request.headers,
            body=raw_data,
        )
        return jsonify({
            "error": "blocked",
            "reason": "unknown device IP",
            "sender_ip": sender_ip,
        }), 403

    media_file = request.files.get("file")
    media_ext = ""
    if media_file is not None:
        media_ext = _media_ext(media_file.filename, media_file.content_type)

    if media_file is None:
        for _field, candidate in request.files.items(multi=True):
            candidate_ext = _media_ext(candidate.filename, candidate.content_type)
            if candidate_ext:
                media_file = candidate
                media_ext = candidate_ext
                break

    if media_file is not None:
        ext = media_ext
        if not ext:
            return jsonify({
                "error": "unsupported type",
                "filename": media_file.filename,
                "content_type": media_file.content_type,
            }), 400

        tmp = BASE_DIR / "tmp"
        tmp.mkdir(exist_ok=True)
        tmp_path = tmp / f"{int(time.time() * 1000)}{ext}"
        media_file.save(tmp_path)

    else:
        ct = request.content_type or ""
        ext = _media_ext(content_type=ct, body=raw_data)
        if not ext:
            return jsonify({"error": "no file or unrecognised content-type"}), 400

        tmp = BASE_DIR / "tmp"
        tmp.mkdir(exist_ok=True)
        tmp_path = tmp / f"{int(time.time() * 1000)}{ext}"
        tmp_path.write_bytes(raw_data)

    received_at = datetime.now()
    _log(
        f"Upload accepted from {sender_ip} -> device={device['name']} file={tmp_path.name}"
    )
    msg_queue.put({
        "device": device,
        "path": tmp_path,
        "ext": ext,
        "received_at": received_at,
        "blocked": False,
        "sender_ip": sender_ip,
    })

    return jsonify({"status": "ok", "device": device["name"]}), 200


@flask_app.route("/ping", methods=["GET", "HEAD", "POST"])
def ping():
    sender_ip = _client_ip()
    path = request.full_path if request.query_string else request.path
    user_agent = request.headers.get("User-Agent", "-")
    content_len = request.content_length or 0
    _log(
        "Ping request received: "
        f"method={request.method} ip={sender_ip} path={path} "
        f"user_agent={user_agent} bytes={content_len}"
    )
    return jsonify({
        "status": "ok",
        "pong": True,
        "server_time": datetime.now().isoformat(timespec="seconds"),
    }), 200


def _run_flask(on_ready, on_error):
    """Run the werkzeug server in its own thread."""
    try:
        ctx = None
        if TLS_ENABLED and CERT_FILE.exists() and KEY_FILE.exists():
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(str(CERT_FILE), str(KEY_FILE))
            proto = "https"
        else:
            proto = "http"

        from werkzeug.serving import make_server
        srv = make_server(SERVER_HOST, SERVER_PORT, flask_app, ssl_context=ctx, threaded=True)
        on_ready(proto, SERVER_HOST, SERVER_PORT)
        srv.serve_forever()
    except Exception as exc:
        on_error(exc)


def start_flask_server(on_ready, on_error):
    """Launch the Flask upload server in a daemon thread."""
    t = threading.Thread(
        target=_run_flask,
        args=(on_ready, on_error),
        daemon=True,
    )
    t.start()


# Plain debug HTTP server
class _DebugHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        sender_ip = self.client_address[0]
        device = _safe_device_lookup(sender_ip)

        if device is None:
            _log_blocked_post(
                source="debug-server",
                sender_ip=sender_ip,
                path=self.path,
                headers=self.headers,
                body=body,
            )
            self.send_response(403)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Blocked: unknown device IP")
            return
        else:
            _log("\n==== NEW REQUEST ====")
            _log(f"Time: {datetime.now().isoformat(timespec='seconds')}")
            _log(f"Client IP:   {self.client_address[0]}")
            _log(f"Client Port: {self.client_address[1]}")
            _log(f"Path: {self.path}")
            _log(f"CGI PARAMS: {parse_qs(urlparse(self.path).query)}")
            _log("\n--- HEADERS ---")
            _log(self.headers)
            if body:
                _log("\n--- BODY (first 500 bytes) ---")
                _log(body[:500])
            _log("=" * 60 + " 200 " + "=" * 60)

        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, fmt, *args):
        _log(f"{self.client_address[0]} [{self.log_date_time_string()}] {fmt % args}")


def start_debug_server(port: int = 8080):
    """Launch the plain-HTTP debug server in a daemon thread."""
    def _run():
        srv = HTTPServer(("0.0.0.0", port), _DebugHandler)
        _log(f"Debug server listening on 0.0.0.0:{port}")
        srv.serve_forever()

    threading.Thread(target=_run, daemon=True).start()

