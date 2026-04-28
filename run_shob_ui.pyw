"""
Windows launcher for Shob UI.

Double-clicking this file starts the desktop app without requiring a terminal.
"""

import os
import sys
import tkinter.messagebox as messagebox
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
os.chdir(BASE_DIR)

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


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
