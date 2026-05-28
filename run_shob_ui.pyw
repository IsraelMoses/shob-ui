"""
Windows launcher for Shob UI.

Double-clicking this file starts the desktop app without requiring a terminal.
"""

import os
import socket
import sys
import tkinter.messagebox as messagebox
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

_instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    _instance_lock.bind(("127.0.0.1", 52991))
    _instance_lock.listen(1)
except OSError:
    messagebox.showinfo("Shob UI", "Shob UI is already running.")
    sys.exit(0)


try:
    from main import main

    main()
except Exception as exc:
    messagebox.showerror(
        "Shob UI",
        "Could not start Shob UI.\n\n"
        f"{type(exc).__name__}: {exc}",
    )
    raise
