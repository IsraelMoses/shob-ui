"""
main.py
=======
Entry point. Run: python main.py

Wires together:
  - core/  (device, gallery, and server code)
  - ui/    (tkinter application)
"""

from ui import SecCamApp, C
from core.backend import DEBUG_SERVER_ENABLED, DEBUG_SERVER_PORT
from core.server import start_flask_server, start_debug_server, msg_queue


def _poll_queue(app: SecCamApp):
    """Drain the inter-thread message queue and hand messages to the UI."""
    try:
        while True:
            msg = msg_queue.get_nowait()
            if msg.get("blocked"):
                app.show_blocked_upload(msg)
            else:
                app.add_slot(msg)
    except Exception:
        pass
    app.after(200, _poll_queue, app)


def main():
    app = SecCamApp()

    def on_ready(proto: str, host: str, port: int):
        app.after(0, lambda: app.set_server_status(
            f"OK  {proto}://{host}:{port}",
            C["status_ok"],
        ))

    def on_error(exc: Exception):
        app.after(0, lambda: app.set_server_status(
            f"Server error: {exc}",
            C["status_err"],
        ))

    start_flask_server(on_ready, on_error)

    if DEBUG_SERVER_ENABLED:
        start_debug_server(port=DEBUG_SERVER_PORT)

    app.after(200, _poll_queue, app)
    app.mainloop()


if __name__ == "__main__":
    main()
