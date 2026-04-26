#!/usr/bin/env python3
"""
test_send.py  –  simulate a camera sending a JPEG or MP4 to the player.

Usage:
    python test_send.py photo  path/to/image.jpg  [host] [port]
    python test_send.py video  path/to/clip.mp4   [host] [port]

Defaults to https://127.0.0.1:8443/upload (self-signed cert, verify=False).
"""
import sys, requests, urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mode = sys.argv[1] if len(sys.argv) > 1 else "photo"
path = sys.argv[2] if len(sys.argv) > 2 else None
host = sys.argv[3] if len(sys.argv) > 3 else "127.0.0.1"
port = int(sys.argv[4]) if len(sys.argv) > 4 else 8443
url  = f"https://{host}:{port}/upload"

if path:
    with open(path, "rb") as f:
        data = f.read()
    fname = path
else:
    # create a tiny dummy JPEG (1x1 pixel)
    import io
    from PIL import Image
    img = Image.new("RGB", (640, 480), color=(50, 100, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    data  = buf.getvalue()
    fname = "test_frame.jpg"

files = {"file": (fname, data, "image/jpeg" if mode=="photo" else "video/mp4")}
resp  = requests.post(url, files=files, verify=False, timeout=10)
print(resp.status_code, resp.text)
