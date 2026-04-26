"""
backend.py
==========
Manages device registry, configuration, and shared filesystem paths.
"""

import json
import os
import sqlite3
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


DEVICES_JSON = BASE_DIR / "devices.json"
DEVICES_DB = BASE_DIR / "devices.db"
GALLERY_DIR = BASE_DIR / "gallery"
LOGO_FILE = BASE_DIR / "logo.png"
GALLERY_DIR.mkdir(exist_ok=True)

SERVER_HOST = os.environ.get("SHOB_SERVER_HOST", "0.0.0.0")
SERVER_PORT = _env_int("SHOB_SERVER_PORT", 8443)
DEBUG_SERVER_ENABLED = _env_bool("SHOB_DEBUG_SERVER", False)
DEBUG_SERVER_PORT = _env_int("SHOB_DEBUG_PORT", 8080)

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
    conn.commit()


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
            "SELECT uuid, ip, name FROM devices ORDER BY name COLLATE NOCASE, uuid"
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


def remove_device(uuid: str):
    init_device_store()
    with _db_conn() as conn:
        conn.execute("DELETE FROM devices WHERE uuid = ?", (uuid,))
        conn.commit()
