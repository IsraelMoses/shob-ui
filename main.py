"""
main.py
=======
Entry point.  Run:  python main.py

Wires together:
  - core/  (device, gallery, and server code)
  - ui/    (tkinter application)
"""

from ui import SecCamApp, C
from core.server import start_flask_server, start_debug_server, msg_queue


def _poll_queue(app: SecCamApp):
    """Drain the inter-thread message queue and hand messages to the UI."""
    try:
        while True:
            msg = msg_queue.get_nowait()
            app.add_slot(msg)
    except Exception:
        pass
    app.after(200, _poll_queue, app)


def main():
    app = SecCamApp()

    # ── start upload server and wire status callbacks into the UI ─────────────
    def on_ready(proto: str, port: int):
        app.after(0, lambda: app.set_server_status(
            f"●  {proto}://0.0.0.0:{port}",
            C["status_ok"],
        ))

    def on_error(exc: Exception):
        app.after(0, lambda: app.set_server_status(
            f"Server error: {exc}",
            C["status_err"],
        ))

    start_flask_server(on_ready, on_error)

    # ── optional plain-HTTP debug listener ───────────────────────────────────
    start_debug_server(port=8080)

    # ── start polling the message queue ──────────────────────────────────────
    app.after(200, _poll_queue, app)

    app.mainloop()


if __name__ == "__main__":
    main()
