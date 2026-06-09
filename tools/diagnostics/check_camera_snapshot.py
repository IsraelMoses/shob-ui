r"""
HTTP snapshot URL checker for IP cameras.

Usage:
    .\.venv\Scripts\python.exe .\tools\check_camera_snapshot.py --host 192.168.1.130 --username admin

The password is requested with getpass and is never printed or saved.
Successful snapshots are saved under tmp/.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import requests
from requests.auth import HTTPBasicAuth, HTTPDigestAuth


DEFAULT_PATHS = [
    # IDIS documented/common paths.
    "/img.jpg?",
    "/img.jpg",
    "/jpegpull/snapshot",
    # ONVIF/proxy-style and common camera paths.
    "/onvifsnapshot/media_service/snapshot",
    "/snapshot.jpg",
    "/image.jpg",
    "/jpg/image.jpg",
    "/tmpfs/auto.jpg",
    "/cgi-bin/snapshot.cgi",
    "/cgi-bin/snapshot.cgi?channel=1",
    "/ISAPI/Streaming/channels/101/picture",
]


def _mask_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except Exception:
        return url
    if parts.username or parts.password:
        netloc = parts.hostname or ""
        if parts.port:
            netloc += f":{parts.port}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    return url


def _looks_like_jpeg(content: bytes, content_type: str) -> bool:
    if content.startswith(b"\xff\xd8\xff"):
        return True
    return "image/jpeg" in (content_type or "").lower()


def _write_snapshot(content: bytes, host: str, path_label: str) -> Path:
    out_dir = Path("tmp")
    out_dir.mkdir(exist_ok=True)
    safe_path = "".join(ch if ch.isalnum() else "_" for ch in path_label).strip("_")[:50]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = out_dir / f"snapshot_{host.replace('.', '_')}_{safe_path}_{stamp}.jpg"
    out_file.write_bytes(content)
    return out_file


def _try_request(session: requests.Session, url: str, username: str, password: str, timeout: int):
    attempts = [
        ("digest", HTTPDigestAuth(username, password)),
        ("basic", HTTPBasicAuth(username, password)),
        ("no-auth", None),
    ]
    results = []
    for auth_name, auth in attempts:
        try:
            response = session.get(url, auth=auth, timeout=timeout, stream=False)
            content_type = response.headers.get("Content-Type", "")
            results.append((auth_name, response.status_code, content_type, response.content))
            if response.status_code == 200 and _looks_like_jpeg(response.content, content_type):
                return auth_name, response
        except Exception as exc:
            results.append((auth_name, "error", str(exc), b""))
    return None, results


def run(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("Camera password: ")
    if not password.isascii():
        print("[!] Password contains non-ASCII characters.")
        print("[!] If this was not intentional, switch keyboard layout to English and run again.")
    paths = list(args.path or DEFAULT_PATHS)
    base = f"http://{args.host}"
    session = requests.Session()

    print("Snapshot probe")
    print("=" * 72)
    print(f"Host: {args.host}")
    print(f"Username: {args.username}")
    print("Password: <hidden>")
    print()

    found = False
    for path in paths:
        url = base + (path if path.startswith("/") else "/" + path)
        print(f"Trying: {_mask_url(url)}")
        auth_name, result = _try_request(
            session=session,
            url=url,
            username=args.username,
            password=password,
            timeout=args.timeout,
        )
        if auth_name:
            out_file = _write_snapshot(result.content, args.host, path)
            print(f"  OK: JPEG via {auth_name}")
            print(f"  Saved: {out_file}")
            found = True
            if not args.keep_trying:
                break
            continue

        for attempt_auth, status, content_type, content in result:
            size = len(content) if isinstance(content, (bytes, bytearray)) else 0
            print(f"  {attempt_auth}: {status} | {content_type} | {size} bytes")

    print()
    if found:
        print("Snapshot test PASSED.")
        return 0

    print("Snapshot test FAILED. No JPEG snapshot URL worked.")
    return 1


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe HTTP snapshot URLs for a camera.")
    parser.add_argument("--host", default=os.environ.get("CAMERA_HOST", "192.168.1.130"))
    parser.add_argument("--username", default=os.environ.get("CAMERA_USERNAME", "admin"))
    parser.add_argument("--password", default=os.environ.get("CAMERA_PASSWORD", ""))
    parser.add_argument("--timeout", type=int, default=6)
    parser.add_argument("--path", action="append", help="Specific snapshot path to try. Can be repeated.")
    parser.add_argument("--keep-trying", action="store_true", help="Continue after first working snapshot URL.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
