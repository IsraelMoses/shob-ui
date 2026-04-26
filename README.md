# Security Camera Player

A Tkinter desktop app that receives JPEG / MP4 POSTs from cameras over HTTPS,
displays them live, then stores them in per-device galleries.

---

## Requirements

```
pip install Pillow flask werkzeug opencv-python
```

For HTTPS certificate generation (optional but recommended):
```
pip install cryptography
```

---

## Quick start

### 1. (Optional) Generate a self-signed TLS cert
```bash
python generate_certs.py
```
This writes `cert.pem` and `key.pem` next to `main.py`.  
If these files are absent the server runs in plain HTTP mode.

### 2. Run the player
```bash
python main.py
```
The server starts on **port 8443** (HTTPS if certs present, HTTP otherwise).

### 3. Configure your devices
Use the right sidebar in the UI:

- Click `Add Device` to enter a name, IP address, and UUID.
- Click `Remove` on a device card to delete it from the registry.

Devices are stored in a local SQLite database at `devices.db`. On first run,
the app will import entries from `devices.json` if that file already exists.

---

## Camera endpoint

```
POST https://<player-host>:8443/upload
```

Send the file as **multipart/form-data** with field name `file`, **or** as a
raw body with `Content-Type: image/jpeg` or `Content-Type: video/mp4`.

The sender's IP is matched against the SQLite device registry to identify the
camera.

---

## Testing locally

```bash
# send a dummy JPEG from localhost
python test_send.py photo

# send a real file
python test_send.py photo  /path/to/snap.jpg
python test_send.py video  /path/to/clip.mp4
```

---

## Gallery

- Media is stored in `gallery/<uuid>/` folders.
- Gallery metadata is stored in `gallery.db`.
- Click any device in the right sidebar to open its gallery.
- Click a thumbnail to view full-size (images) or see the file path (videos).
- Use `Clear Gallery` inside a camera gallery to remove that camera's stored files and metadata.

---

## Player behaviour

| Situation | Display |
|---|---|
| No active messages | "Waiting for messages…" centred |
| 1 active message | Full screen |
| 2 active messages | Split 50 / 50 |
| 3–4 | 2 × 2 grid |
| 5–6 | 3 × 2 grid |
| 7–9 | 3 × 3 grid |
| 10+ | 4-column grid |

Photo display duration is configurable with the spinner in the toolbar.  
Videos loop until their display timer expires.

---

## Folder layout

```
secam_player/
├── main.py
├── devices.db
├── gallery.db
├── devices.json       ← optional one-time migration source
├── generate_certs.py
├── test_send.py
├── cert.pem          ← generated
├── key.pem           ← generated
├── tmp/              ← incoming files (auto-created)
└── gallery/
    ├── cam-0001/
    │   ├── 20250412_143022_snap.jpg
    │   └── 20250412_143022_snap.json
    └── cam-0002/
        └── ...
```

---

## Security and TPM

TLS PEM files (`cert.pem`, `key.pem`) are ignored by Git. For Windows TPM-backed certificate setup and safer key handling, see:

```
docs/security-tpm.md
```

Useful scripts:

```powershell
.\scripts\check_tpm.ps1
.\scripts\create_tpm_certificate.ps1
.\scripts\run_with_external_pem.ps1
.\scripts\run_internal_http.ps1
.\scripts\start_tpm_https_proxy.ps1
```
