"""
backend.py
==========
Manages device registry and shared filesystem paths.
"""

import json
import sqlite3
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).resolve().parent.parent
DEVICES_JSON = BASE_DIR / "devices.json"
DEVICES_DB   = BASE_DIR / "devices.db"
GALLERY_DIR  = BASE_DIR / "gallery"
CERT_FILE    = BASE_DIR / "cert.pem"
KEY_FILE     = BASE_DIR / "key.pem"
LOGO_FILE    = BASE_DIR / "logo.png"
GALLERY_DIR.mkdir(exist_ok=True)

SERVER_PORT  = 8443

DEFAULT_DEVICES = [
    {"uuid": "cam-0001", "ip": "127.0.0.1",   "name": "Front Door"},
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
