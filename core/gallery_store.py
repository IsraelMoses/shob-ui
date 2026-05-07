"""
SQLite-backed gallery metadata and local media storage helpers.
"""

import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

import cv2

from .backend import BASE_DIR, GALLERY_DIR


GALLERY_DB = BASE_DIR / "gallery.db"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


def _db_conn():
    conn = sqlite3.connect(GALLERY_DB)
    conn.row_factory = sqlite3.Row
    return conn


def _create_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gallery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_uuid TEXT NOT NULL,
            received TEXT NOT NULL,
            file TEXT NOT NULL,
            UNIQUE(device_uuid, file)
        )
    """)
    conn.commit()


def gallery_dir_for(uuid: str) -> Path:
    path = GALLERY_DIR / uuid
    path.mkdir(exist_ok=True)
    return path


def _migrate_sidecars(conn):
    existing = conn.execute("SELECT COUNT(*) FROM gallery_items").fetchone()[0]
    if existing:
        return

    for device_dir in sorted(GALLERY_DIR.iterdir()):
        if not device_dir.is_dir():
            continue
        for meta_file in sorted(device_dir.glob("*.json")):
            try:
                meta = json.loads(meta_file.read_text())
                media_name = meta["file"]
                media_path = device_dir / media_name
                if not media_path.exists():
                    continue
                conn.execute(
                    """
                    INSERT OR IGNORE INTO gallery_items (device_uuid, received, file)
                    VALUES (?, ?, ?)
                    """,
                    (device_dir.name, meta["received"], media_name),
                )
            except Exception:
                continue
    conn.commit()


def init_gallery_store():
    GALLERY_DIR.mkdir(exist_ok=True)
    with _db_conn() as conn:
        _create_schema(conn)
        _migrate_sidecars(conn)


def save_to_gallery(uuid: str, src_path: Path, received_at: datetime) -> Path:
    init_gallery_store()
    dst_dir = gallery_dir_for(uuid)
    stamp = received_at.strftime("%Y%m%d_%H%M%S")
    dst = dst_dir / f"{stamp}_{src_path.name}"
    shutil.copy2(src_path, dst)

    with _db_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO gallery_items (device_uuid, received, file)
            VALUES (?, ?, ?)
            """,
            (uuid, received_at.isoformat(), dst.name),
        )
        conn.commit()
    return dst


def extract_video_thumbnail(video_path: Path) -> "Path | None":
    thumb_path = video_path.with_suffix(".thumb.jpg")
    cap = cv2.VideoCapture(str(video_path))
    ok, frame = cap.read()
    cap.release()
    if ok:
        cv2.imwrite(str(thumb_path), frame)
        return thumb_path
    return None


def gallery_items_for(uuid: str) -> list:
    init_gallery_store()
    device_dir = gallery_dir_for(uuid)
    with _db_conn() as conn:
        rows = conn.execute(
            """
            SELECT received, file
            FROM gallery_items
            WHERE device_uuid = ?
            ORDER BY received DESC, id DESC
            """,
            (uuid,),
        ).fetchall()

    items = []
    for row in rows:
        media_path = device_dir / row["file"]
        if media_path.exists():
            items.append((row["received"], media_path))
    return items


def gallery_count_for(uuid: str) -> int:
    init_gallery_store()
    with _db_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM gallery_items WHERE device_uuid = ?",
            (uuid,),
        ).fetchone()
    return int(row["count"])


def clear_gallery_for(uuid: str) -> int:
    init_gallery_store()
    items = gallery_items_for(uuid)
    removed = 0

    for _, media_path in items:
        thumb_path = media_path.with_suffix(".thumb.jpg")
        for path in (media_path, thumb_path):
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
        removed += 1

    device_dir = gallery_dir_for(uuid)
    for leftover in device_dir.glob("*.json"):
        try:
            leftover.unlink()
        except Exception:
            pass

    with _db_conn() as conn:
        conn.execute("DELETE FROM gallery_items WHERE device_uuid = ?", (uuid,))
        conn.commit()

    return removed


def image_items_for(uuid: str) -> list:
    items = gallery_items_for(uuid)
    return [
        (received, media_path)
        for received, media_path in items
        if media_path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def _safe_export_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("._") or "device"


def export_images_for(uuid: str, destination_root, device_name: str = "") -> tuple[int, Path]:
    destination_root = Path(destination_root)
    destination_root.mkdir(parents=True, exist_ok=True)

    name_part = _safe_export_segment(device_name or uuid)
    uuid_part = _safe_export_segment(uuid)
    base_dir = destination_root / f"{name_part}_{uuid_part}_photos"

    export_dir = base_dir
    suffix = 2
    while export_dir.exists():
        export_dir = destination_root / f"{base_dir.name}_{suffix}"
        suffix += 1
    export_dir.mkdir(parents=True, exist_ok=False)

    count = 0
    for _, media_path in image_items_for(uuid):
        shutil.copy2(media_path, export_dir / media_path.name)
        count += 1
    return count, export_dir
