"""
backend.py
==========
Manages device registry, configuration, and shared filesystem paths.
"""

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default
    return Path(value).expanduser()


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _default_tls_file(filename: str) -> Path:
    program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    external_file = program_data / "ShobUI" / "certs" / filename
    if external_file.exists():
        return external_file
    return BASE_DIR / filename


def _default_logo_file() -> Path:
    desktop_logo = Path.home() / "Desktop" / "logo.png"
    if desktop_logo.exists():
        return desktop_logo
    return BASE_DIR / "logo.png"


DEVICES_JSON = BASE_DIR / "devices.json"
DEVICES_DB = BASE_DIR / "devices.db"
GALLERY_DIR = BASE_DIR / "gallery"
LOGO_FILE = _env_path("SHOB_LOGO_FILE", _default_logo_file())
GALLERY_DIR.mkdir(exist_ok=True)

SERVER_HOST = os.environ.get("SHOB_SERVER_HOST", "0.0.0.0")
SERVER_PORT = _env_int("SHOB_SERVER_PORT", 8443)
DEBUG_SERVER_ENABLED = _env_bool("SHOB_DEBUG_SERVER", False)
DEBUG_SERVER_PORT = _env_int("SHOB_DEBUG_PORT", 8080)
TLS_ENABLED = _env_bool("SHOB_TLS_ENABLED", True)
TRUSTED_PROXY_IPS = {
    ip.strip()
    for ip in os.environ.get("SHOB_TRUSTED_PROXY_IPS", "127.0.0.1,::1").split(",")
    if ip.strip()
}
ADMIN_EVENT_ALLOWED_IPS = {
    ip.strip()
    for ip in os.environ.get("SHOB_ADMIN_EVENT_ALLOWED_IPS", "127.0.0.1,::1").split(",")
    if ip.strip()
}
ADMIN_EVENT_TOKEN = os.environ.get("SHOB_ADMIN_EVENT_TOKEN", "")

CERT_FILE = _env_path("SHOB_TLS_CERT_FILE", _default_tls_file("cert.pem"))
KEY_FILE = _env_path("SHOB_TLS_KEY_FILE", _default_tls_file("key.pem"))

DEFAULT_DEVICES = [
    {"uuid": "cam-0001", "ip": "127.0.0.1", "name": "Front Door"},
    {"uuid": "cam-0002", "ip": "192.168.1.50", "name": "Back Yard"},
]


def _db_conn():
    conn = sqlite3.connect(DEVICES_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            uuid TEXT PRIMARY KEY,
            ip   TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS camera_profiles (
            device_uuid TEXT PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            password TEXT NOT NULL DEFAULT '',
            camera_type TEXT NOT NULL DEFAULT '',
            rtsp_port INTEGER NOT NULL DEFAULT 8554,
            stream_path TEXT NOT NULL DEFAULT '/cam/realmonitor?channel=1&subtype=0',
            last_status TEXT NOT NULL DEFAULT '',
            last_error TEXT NOT NULL DEFAULT '',
            last_checked_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        )
    """)
    _ensure_camera_profile_columns(conn)
    conn.commit()


def _ensure_camera_profile_columns(conn):
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(camera_profiles)").fetchall()
    }
    migrations = {
        "rtsp_port": "ALTER TABLE camera_profiles ADD COLUMN rtsp_port INTEGER NOT NULL DEFAULT 8554",
        "stream_path": (
            "ALTER TABLE camera_profiles ADD COLUMN stream_path TEXT NOT NULL "
            "DEFAULT '/cam/realmonitor?channel=1&subtype=0'"
        ),
        "last_status": "ALTER TABLE camera_profiles ADD COLUMN last_status TEXT NOT NULL DEFAULT ''",
        "last_error": "ALTER TABLE camera_profiles ADD COLUMN last_error TEXT NOT NULL DEFAULT ''",
        "last_checked_at": "ALTER TABLE camera_profiles ADD COLUMN last_checked_at TEXT NOT NULL DEFAULT ''",
    }
    for column, statement in migrations.items():
        if column not in columns:
            conn.execute(statement)


def _import_devices(conn, devices):
    conn.executemany(
        """
        INSERT OR REPLACE INTO devices (uuid, ip, name)
        VALUES (?, ?, ?)
        """,
        [(d["uuid"], d["ip"], d["name"]) for d in devices],
    )
    conn.commit()


def _seed_or_migrate_devices(conn):
    count = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    if count:
        return

    if DEVICES_JSON.exists():
        try:
            devices = json.loads(DEVICES_JSON.read_text())
        except Exception:
            devices = DEFAULT_DEVICES
    else:
        devices = DEFAULT_DEVICES

    _import_devices(conn, devices)


def init_device_store():
    with _db_conn() as conn:
        _create_schema(conn)
        _seed_or_migrate_devices(conn)


def load_devices():
    init_device_store()
    with _db_conn() as conn:
        rows = conn.execute(
            "SELECT uuid, ip, name FROM devices ORDER BY rowid DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def device_by_ip(ip: str) -> "dict | None":
    init_device_store()
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT uuid, ip, name FROM devices WHERE ip = ?",
            (ip,),
        ).fetchone()
    return dict(row) if row else None


def add_device(uuid: str, ip: str, name: str):
    init_device_store()
    with _db_conn() as conn:
        conn.execute(
            "INSERT INTO devices (uuid, ip, name) VALUES (?, ?, ?)",
            (uuid.strip(), ip.strip(), name.strip()),
        )
        conn.commit()


def add_device_if_missing(uuid: str, ip: str, name: str) -> str:
    uuid = uuid.strip()
    ip = ip.strip()
    name = name.strip()
    init_device_store()
    with _db_conn() as conn:
        existing_uuid = conn.execute(
            "SELECT uuid FROM devices WHERE uuid = ?",
            (uuid,),
        ).fetchone()
        existing_ip = conn.execute(
            "SELECT uuid FROM devices WHERE ip = ?",
            (ip,),
        ).fetchone()

        if existing_uuid:
            return "exists_uuid"

        if existing_ip:
            return "exists_ip"

        conn.execute(
            "INSERT INTO devices (uuid, ip, name) VALUES (?, ?, ?)",
            (uuid, ip, name),
        )
        conn.commit()
        return "created"


def remove_device(uuid: str):
    init_device_store()
    with _db_conn() as conn:
        conn.execute("DELETE FROM camera_profiles WHERE device_uuid = ?", (uuid,))
        conn.execute("DELETE FROM devices WHERE uuid = ?", (uuid,))
        conn.commit()


def save_camera_profile(
    device_uuid: str,
    username: str,
    password: str,
    camera_type: str,
    rtsp_port: int = 8554,
    stream_path: str = "/cam/realmonitor?channel=1&subtype=0",
):
    init_device_store()
    now = datetime.now().isoformat(timespec="seconds")
    try:
        rtsp_port = int(rtsp_port)
    except (TypeError, ValueError):
        rtsp_port = 8554
    stream_path = (stream_path or "/cam/realmonitor?channel=1&subtype=0").strip()
    with _db_conn() as conn:
        conn.execute(
            """
            INSERT INTO camera_profiles (
                device_uuid, username, password, camera_type, rtsp_port, stream_path, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_uuid) DO UPDATE SET
                username = excluded.username,
                password = excluded.password,
                camera_type = excluded.camera_type,
                rtsp_port = excluded.rtsp_port,
                stream_path = excluded.stream_path,
                updated_at = excluded.updated_at
            """,
            (
                device_uuid.strip(),
                username.strip(),
                password,
                camera_type.strip(),
                rtsp_port,
                stream_path,
                now,
            ),
        )
        conn.commit()


def load_camera_profile(device_uuid: str) -> "dict | None":
    init_device_store()
    with _db_conn() as conn:
        row = conn.execute(
            """
            SELECT
                device_uuid,
                username,
                password,
                camera_type,
                rtsp_port,
                stream_path,
                last_status,
                last_error,
                last_checked_at,
                updated_at
            FROM camera_profiles
            WHERE device_uuid = ?
            """,
            (device_uuid.strip(),),
        ).fetchone()
    return dict(row) if row else None


def save_camera_connection_status(device_uuid: str, status: str, error: str = ""):
    init_device_store()
    now = datetime.now().isoformat(timespec="seconds")
    with _db_conn() as conn:
        conn.execute(
            """
            UPDATE camera_profiles
            SET last_status = ?, last_error = ?, last_checked_at = ?
            WHERE device_uuid = ?
            """,
            (status.strip(), (error or "").strip(), now, device_uuid.strip()),
        )
        conn.commit()
