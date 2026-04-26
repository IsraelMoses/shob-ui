"""
Device management dialogs for the desktop UI.
"""

import tkinter as tk
from tkinter import ttk

from .ui_theme import C


class DeviceDialog(tk.Toplevel):
    def __init__(self, parent, suggested_uuid: str):
        super().__init__(parent)
        self.result = None
        self._name_var = tk.StringVar()
        self._ip_var = tk.StringVar()
        self._uuid_var = tk.StringVar(value=suggested_uuid)

        self.title("Add Device")
        self.configure(bg=C["bg_toolbar"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _build(self):
        body = tk.Frame(self, bg=C["bg_toolbar"], padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_field(body, 0, "Name", self._name_var)
        self._build_field(body, 2, "IP Address", self._ip_var)
        self._build_field(body, 4, "UUID", self._uuid_var)

        tk.Label(
            body,
            text="You can keep the suggested UUID or replace it.",
            font=("Helvetica", 8),
            bg=C["bg_toolbar"],
            fg=C["tx_secondary"],
        ).grid(row=6, column=0, sticky="w", pady=(6, 12))

        actions = tk.Frame(body, bg=C["bg_toolbar"])
        actions.grid(row=7, column=0, sticky="e")
        ttk.Button(actions, text="Cancel", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Add Device", command=self._submit).pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )

        body.columnconfigure(0, weight=1)

    def _build_field(self, parent, row, label, variable):
        tk.Label(
            parent,
            text=label,
            font=("Helvetica", 9, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_primary"],
        ).grid(row=row, column=0, sticky="w", pady=(0, 4))
        tk.Entry(parent, textvariable=variable, width=34).grid(
            row=row + 1,
            column=0,
            sticky="ew",
            pady=(0, 10) if row < 4 else 0,
        )

    def _submit(self):
        self.result = {
            "name": self._name_var.get().strip(),
            "ip": self._ip_var.get().strip(),
            "uuid": self._uuid_var.get().strip(),
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
