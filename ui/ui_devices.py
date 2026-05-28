"""
Device management dialogs for the desktop UI.
"""

import tkinter as tk
from tkinter import messagebox, ttk

from core.rtsp_service import camera_defaults

from .ui_theme import C


class DeviceDialog(tk.Toplevel):
    def __init__(self, parent, suggested_uuid: str):
        super().__init__(parent)
        self.withdraw()
        self.result = None
        self._name_var = tk.StringVar()
        self._ip_var = tk.StringVar()
        self._uuid_var = tk.StringVar(value=suggested_uuid)

        self.title("Add Device")
        self.configure(bg=C["bg_toolbar"])
        self.resizable(False, False)
        self.transient(parent)
        self._build()
        self._center_on_parent(parent)
        self.deiconify()
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda e: self._submit())
        self.bind("<Escape>", lambda e: self._cancel())

    def _center_on_parent(self, parent):
        parent.update_idletasks()
        self.update_idletasks()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 0)
        self.geometry(f"+{x}+{y}")

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


class CameraCredentialsDialog(tk.Toplevel):
    def __init__(self, parent, device_name: str, device_ip: str, initial_values=None):
        super().__init__(parent)
        self.withdraw()
        self.result = None
        self._username_var = tk.StringVar()
        self._password_var = tk.StringVar()
        self._camera_type_var = tk.StringVar(value="Generic RTSP")
        defaults = camera_defaults("Generic RTSP")
        self._rtsp_port_var = tk.StringVar(value=str(defaults["port"]))
        self._stream_path_var = tk.StringVar(value=defaults["path"])
        self._device_name = device_name
        self._device_ip = device_ip
        self._initial_values = initial_values or {}

        self.title("Camera Credentials")
        self.configure(bg=C["bg_toolbar"])
        self.resizable(False, False)
        self.transient(parent)
        self._build()
        self._apply_initial_values()
        self._center_on_parent(parent)
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.attributes("-topmost", True)
            self.after(350, lambda: self.attributes("-topmost", False))
        except Exception:
            pass
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self._cancel())

    def _center_on_parent(self, parent):
        parent.update_idletasks()
        self.update_idletasks()

        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        x = parent.winfo_rootx() + max((parent.winfo_width() - width) // 2, 0)
        y = parent.winfo_rooty() + max((parent.winfo_height() - height) // 2, 0)
        self.geometry(f"+{x}+{y}")

    def _build(self):
        body = tk.Frame(self, bg=C["bg_toolbar"], padx=18, pady=16)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)

        tk.Label(
            body,
            text=f"New device added: {self._device_name} ({self._device_ip})",
            font=("Helvetica", 9, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_primary"],
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        self._build_field(body, 1, "Username", self._username_var)
        self._build_field(body, 3, "Password", self._password_var, show="*")

        tk.Label(
            body,
            text="Camera Type",
            font=("Helvetica", 9, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_primary"],
        ).grid(row=5, column=0, sticky="w", pady=(0, 4))
        camera_type_combo = ttk.Combobox(
            body,
            textvariable=self._camera_type_var,
            values=("Generic RTSP", "Dahua", "Hikvision", "Axis"),
            state="readonly",
            width=31,
        )
        camera_type_combo.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        camera_type_combo.bind("<<ComboboxSelected>>", self._apply_camera_defaults)

        self._build_field(body, 7, "RTSP Port", self._rtsp_port_var)
        self._build_field(body, 9, "RTSP Path", self._stream_path_var)

        actions = tk.Frame(body, bg=C["bg_toolbar"])
        actions.grid(row=11, column=0, sticky="e", pady=(14, 0))
        ttk.Button(actions, text="Skip", command=self._cancel).pack(side=tk.RIGHT)
        ttk.Button(actions, text="Save", command=self._submit).pack(
            side=tk.RIGHT,
            padx=(0, 8),
        )

    def _build_field(self, parent, row, label, variable, show=None):
        tk.Label(
            parent,
            text=label,
            font=("Helvetica", 9, "bold"),
            bg=C["bg_toolbar"],
            fg=C["tx_primary"],
        ).grid(row=row, column=0, sticky="w", pady=(0, 4))
        tk.Entry(parent, textvariable=variable, width=34, show=show).grid(
            row=row + 1,
            column=0,
            sticky="ew",
            pady=(0, 10),
        )

    def _apply_camera_defaults(self, _event=None):
        defaults = camera_defaults(self._camera_type_var.get())
        self._rtsp_port_var.set(str(defaults["port"]))
        self._stream_path_var.set(defaults["path"])

    def _apply_initial_values(self):
        if not self._initial_values:
            return
        self._username_var.set(self._initial_values.get("username", ""))
        self._password_var.set(self._initial_values.get("password", ""))
        self._camera_type_var.set(
            self._initial_values.get("camera_type", self._camera_type_var.get())
        )
        self._rtsp_port_var.set(str(self._initial_values.get("rtsp_port", self._rtsp_port_var.get())))
        self._stream_path_var.set(
            self._initial_values.get("stream_path", self._stream_path_var.get())
        )

    def _submit(self):
        username = self._username_var.get().strip()
        password = self._password_var.get()
        camera_type = self._camera_type_var.get().strip()
        rtsp_port = self._rtsp_port_var.get().strip()
        stream_path = self._stream_path_var.get().strip()
        if not username or not password or not camera_type or not rtsp_port or not stream_path:
            messagebox.showerror(
                "Camera Credentials",
                "Username, Password, Camera Type, RTSP Port, and RTSP Path are required.",
                parent=self,
            )
            return
        try:
            port_num = int(rtsp_port)
            if port_num < 1 or port_num > 65535:
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "Camera Credentials",
                "RTSP Port must be a valid number between 1 and 65535.",
                parent=self,
            )
            return
        self.result = {
            "username": username,
            "password": password,
            "camera_type": camera_type,
            "rtsp_port": port_num,
            "stream_path": stream_path,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()
