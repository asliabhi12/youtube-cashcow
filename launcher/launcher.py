"""Main Tkinter Desktop Application for CashCow Launcher."""

import sys
import webbrowser
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager
from launcher.backend import BackendService
from launcher.frontend import FrontendService
from launcher.cloudflare import CloudflareService
from launcher.health_monitor import HealthMonitor
from launcher.log_viewer import LogViewerWindow


class CashCowLauncherApp(tk.Tk):
    """Modern macOS-native Desktop Launcher & Control Center for CashCow."""

    def __init__(self):
        super().__init__()
        self.config = LauncherConfig()
        self.pm = ProcessManager(self.config)

        # Dedicated Service Controllers
        self.backend_svc = BackendService(self.config, self.pm)
        self.frontend_svc = FrontendService(self.config, self.pm)
        self.cloudflare_svc = CloudflareService(self.config, self.pm)

        self.log_viewer_win: Optional[LogViewerWindow] = None

        self.title("CashCow Control Center")
        self.geometry("520x720")
        self.resizable(False, False)

        # Apply macOS/Modern ttk styling
        self._apply_styles()

        # State tracking
        self.is_busy = False
        self._cancel_event = threading.Event()

        # Build GUI
        self._create_ui()

        # Health Monitor with callback
        self.health_monitor = HealthMonitor(
            self.config, on_status_change=self._on_health_status_change
        )
        self.health_monitor.start()

        # Protocol handlers
        self.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _apply_styles(self) -> None:
        style = ttk.Style(self)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")

        style.configure("Header.TLabel", font=("SF Pro Text", 18, "bold"))
        style.configure("Subtitle.TLabel", font=("SF Pro Text", 11), foreground="#666666")
        style.configure("StatusTitle.TLabel", font=("SF Pro Text", 12, "bold"))
        style.configure("StatusText.TLabel", font=("SF Pro Text", 12))

    def _create_ui(self) -> None:
        main_container = ttk.Frame(self, padding=20)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ----------------------------------------------------
        # Header Banner
        # ----------------------------------------------------
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        ttk.Label(header_frame, text="🐮 CashCow Control Center", style="Header.TLabel").pack(anchor=tk.W)
        ttk.Label(header_frame, text="Local Development Engine & Public Cloudflare Tunnel Studio", style="Subtitle.TLabel").pack(anchor=tk.W, pady=(2, 0))

        # ----------------------------------------------------
        # Service Status Dashboard Card
        # ----------------------------------------------------
        status_card = ttk.LabelFrame(main_container, text=" Service Status ", padding=(15, 12))
        status_card.pack(fill=tk.X, pady=(0, 12))

        # Backend Status
        row_b = ttk.Frame(status_card)
        row_b.pack(fill=tk.X, pady=4)
        ttk.Label(row_b, text="Backend API (port 8000)", style="StatusTitle.TLabel").pack(side=tk.LEFT)
        self.lbl_status_backend = ttk.Label(row_b, text="🔴 Stopped", style="StatusText.TLabel")
        self.lbl_status_backend.pack(side=tk.RIGHT)

        # Frontend Status
        row_f = ttk.Frame(status_card)
        row_f.pack(fill=tk.X, pady=4)
        ttk.Label(row_f, text="Frontend Web App (port 3000)", style="StatusTitle.TLabel").pack(side=tk.LEFT)
        self.lbl_status_frontend = ttk.Label(row_f, text="🔴 Stopped", style="StatusText.TLabel")
        self.lbl_status_frontend.pack(side=tk.RIGHT)

        # Cloudflare Tunnel Status
        row_c = ttk.Frame(status_card)
        row_c.pack(fill=tk.X, pady=4)
        ttk.Label(row_c, text="Cloudflare Tunnel (cashcow)", style="StatusTitle.TLabel").pack(side=tk.LEFT)
        self.lbl_status_cloudflare = ttk.Label(row_c, text="🔴 Cloudflare Tunnel Stopped", style="StatusText.TLabel")
        self.lbl_status_cloudflare.pack(side=tk.RIGHT)

        # Status Footer / Progress message
        self.lbl_status_message = ttk.Label(
            status_card, text="Ready", font=("SF Pro Text", 10, "italic"), foreground="#777777"
        )
        self.lbl_status_message.pack(anchor=tk.W, pady=(8, 0))

        # ----------------------------------------------------
        # Configuration Options (Auto-Start Checkbox)
        # ----------------------------------------------------
        self.var_auto_tunnel = tk.BooleanVar(value=self.config.auto_start_cloudflare)
        cb_tunnel = ttk.Checkbutton(
            main_container,
            text="Start Cloudflare Tunnel automatically with CashCow",
            variable=self.var_auto_tunnel,
            command=self._on_toggle_auto_tunnel,
        )
        cb_tunnel.pack(anchor=tk.W, pady=(0, 15))

        # ----------------------------------------------------
        # Global Action Buttons (Start / Stop / Restart All)
        # ----------------------------------------------------
        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.btn_start = ttk.Button(btn_frame, text="▶  Start CashCow", command=self.on_start)
        self.btn_start.pack(fill=tk.X, pady=3, ipady=4)

        self.btn_stop = ttk.Button(btn_frame, text="■  Stop CashCow", command=self.on_stop)
        self.btn_stop.pack(fill=tk.X, pady=3, ipady=4)

        self.btn_restart = ttk.Button(btn_frame, text="🔄  Restart", command=self.on_restart)
        self.btn_restart.pack(fill=tk.X, pady=3, ipady=4)

        # ----------------------------------------------------
        # Independent Cloudflare Control Buttons
        # ----------------------------------------------------
        cf_btn_frame = ttk.Frame(main_container)
        cf_btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.btn_cf_start = ttk.Button(
            cf_btn_frame, text="☁  Start Cloudflare Tunnel", command=self.on_start_cloudflare
        )
        self.btn_cf_start.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3), ipady=3)

        self.btn_cf_stop = ttk.Button(
            cf_btn_frame, text="☁  Stop Cloudflare Tunnel", command=self.on_stop_cloudflare
        )
        self.btn_cf_stop.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0), ipady=3)

        # ----------------------------------------------------
        # Navigation & Log Buttons (Open Local, Open Public, View Logs)
        # ----------------------------------------------------
        nav_frame = ttk.Frame(main_container)
        nav_frame.pack(fill=tk.X, pady=(0, 12))

        self.btn_open_local = ttk.Button(nav_frame, text="🌐 Open App", command=self.on_open_local_app)
        self.btn_open_local.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 2), ipady=3)

        self.btn_open_public = ttk.Button(nav_frame, text="🌍 Open Public App", command=self.on_open_public_app)
        self.btn_open_public.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2, ipady=3)

        self.btn_logs = ttk.Button(nav_frame, text="📜 View Logs", command=self.on_view_logs)
        self.btn_logs.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(2, 0), ipady=3)

        # ----------------------------------------------------
        # Developer Tools / Settings
        # ----------------------------------------------------
        ext_card = ttk.LabelFrame(main_container, text=" Quick Developer Tools ", padding=(15, 8))
        ext_card.pack(fill=tk.X, pady=(0, 12))

        ext_row1 = ttk.Frame(ext_card)
        ext_row1.pack(fill=tk.X, pady=2)

        btn_docs = ttk.Button(ext_row1, text="📖 OpenAPI Docs", command=self.on_open_docs)
        btn_docs.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 3))

        btn_settings = ttk.Button(ext_row1, text="⚙️ Settings", command=self.on_open_settings)
        btn_settings.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(3, 0))

        # ----------------------------------------------------
        # Exit Button
        # ----------------------------------------------------
        self.btn_exit = ttk.Button(main_container, text="❌  Exit Launcher", command=self.on_exit)
        self.btn_exit.pack(fill=tk.X, side=tk.BOTTOM, ipady=4)

    def _on_toggle_auto_tunnel(self) -> None:
        self.config.auto_start_cloudflare = self.var_auto_tunnel.get()
        self.config.save()

    def _on_health_status_change(
        self, backend_ok: bool, frontend_ok: bool, cloudflare_ok: bool
    ) -> None:
        """Thread-safe UI status indicator update."""
        def update():
            # Backend label
            if backend_ok:
                self.lbl_status_backend.config(text="🟢 Running", foreground="#2e7d32")
            else:
                self.lbl_status_backend.config(text="🔴 Stopped", foreground="#d32f2f")

            # Frontend label
            if frontend_ok:
                self.lbl_status_frontend.config(text="🟢 Running", foreground="#2e7d32")
            else:
                self.lbl_status_frontend.config(text="🔴 Stopped", foreground="#d32f2f")

            # Cloudflare label (checks process or metrics)
            cf_running = self.cloudflare_svc.is_running() or cloudflare_ok
            if cf_running:
                self.lbl_status_cloudflare.config(text="🟢 Cloudflare Tunnel Running", foreground="#2e7d32")
            else:
                self.lbl_status_cloudflare.config(text="🔴 Cloudflare Tunnel Stopped", foreground="#d32f2f")

        self.after(0, update)

    def set_status_message(self, msg: str) -> None:
        self.after(0, lambda: self.lbl_status_message.config(text=msg))

    def set_busy(self, busy: bool) -> None:
        self.is_busy = busy
        def update():
            state = tk.DISABLED if busy else tk.NORMAL
            self.btn_start.config(state=state)
            self.btn_stop.config(state=state)
            self.btn_restart.config(state=state)
            self.btn_cf_start.config(state=state)
            self.btn_cf_stop.config(state=state)
        self.after(0, update)

    # ----------------------------------------------------
    # Action Handlers
    # ----------------------------------------------------
    def on_start(self) -> None:
        """Start Backend, Frontend, and optional Cloudflare Tunnel sequentially."""
        if self.is_busy:
            return

        self._cancel_event.clear()
        self.set_busy(True)

        def worker():
            try:
                # 1. Start Backend
                self.set_status_message("Starting Backend API server...")
                if not self.backend_svc.start():
                    raise RuntimeError("Failed to spawn backend process.")

                self.set_status_message("Waiting for Backend health check (http://localhost:8000/health)...")
                if not self.health_monitor.wait_for_healthy(
                    "backend", timeout=self.config.startup_timeout_sec, cancel_event=self._cancel_event
                ):
                    raise RuntimeError(
                        f"Backend failed to respond to /health within {int(self.config.startup_timeout_sec)} seconds.\nCheck logs for details."
                    )

                # 2. Start Frontend
                self.set_status_message("Starting Frontend web app...")
                if not self.frontend_svc.start():
                    raise RuntimeError("Failed to spawn frontend process.")

                self.set_status_message("Waiting for Frontend (http://localhost:3000)...")
                if not self.health_monitor.wait_for_healthy(
                    "frontend", timeout=self.config.startup_timeout_sec, cancel_event=self._cancel_event
                ):
                    raise RuntimeError(
                        f"Frontend failed to respond on http://localhost:3000 within {int(self.config.startup_timeout_sec)} seconds.\nCheck logs for details."
                    )

                # 3. Start Cloudflare Tunnel if auto-start is checked
                if self.config.auto_start_cloudflare:
                    self.set_status_message("Starting Cloudflare Tunnel...")
                    try:
                        self.cloudflare_svc.start()
                    except Exception as cf_exc:
                        self.pm.log_launcher(f"Warning: Cloudflare Tunnel auto-start failed: {cf_exc}")
                        self.after(
                            0, lambda: messagebox.showwarning("Cloudflare Tunnel Warning", str(cf_exc), parent=self)
                        )

                # 4. Open Browser
                self.set_status_message("CashCow is fully online! Opening browser...")
                if self.config.auto_open_browser:
                    webbrowser.open(self.config.frontend_url)

                self.set_status_message("Running")
            except Exception as exc:
                self.set_status_message(f"Startup error: {exc}")
                self.after(
                    0, lambda: messagebox.showerror("CashCow Startup Failed", str(exc), parent=self)
                )
            finally:
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def on_stop(self) -> None:
        """Stop Backend, Frontend, and Cloudflare Tunnel cleanly."""
        if self.is_busy:
            return

        self._cancel_event.set()
        self.set_busy(True)

        def worker():
            try:
                self.set_status_message("Stopping all services cleanly...")
                self.cloudflare_svc.stop()
                self.frontend_svc.stop()
                self.backend_svc.stop()
                self.set_status_message("Stopped")
            finally:
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def on_restart(self) -> None:
        """Restart all active services."""
        if self.is_busy:
            return

        self._cancel_event.set()
        self.set_busy(True)

        def worker():
            try:
                self.set_status_message("Restarting CashCow services...")
                self.cloudflare_svc.stop()
                self.frontend_svc.stop()
                self.backend_svc.stop()
                self._cancel_event.clear()
                self.set_busy(False)
                self.on_start()
            except Exception as exc:
                self.set_status_message(f"Restart error: {exc}")
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------------------------------
    # Independent Cloudflare Tunnel Actions
    # ----------------------------------------------------
    def on_start_cloudflare(self) -> None:
        if self.is_busy:
            return
        self.set_busy(True)

        def worker():
            try:
                self.set_status_message("Starting Cloudflare Tunnel...")
                self.cloudflare_svc.start()
                self.set_status_message("Cloudflare Tunnel connected.")
            except Exception as exc:
                self.set_status_message(f"Cloudflare error: {exc}")
                self.after(
                    0, lambda: messagebox.showerror("Cloudflare Tunnel Error", str(exc), parent=self)
                )
            finally:
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    def on_stop_cloudflare(self) -> None:
        if self.is_busy:
            return
        self.set_busy(True)

        def worker():
            try:
                self.set_status_message("Stopping Cloudflare Tunnel...")
                self.cloudflare_svc.stop()
                self.set_status_message("Cloudflare Tunnel stopped.")
            finally:
                self.set_busy(False)

        threading.Thread(target=worker, daemon=True).start()

    # ----------------------------------------------------
    # Navigation & Links
    # ----------------------------------------------------
    def on_open_local_app(self) -> None:
        webbrowser.open(self.config.frontend_url)

    def on_open_public_app(self) -> None:
        webbrowser.open(self.config.public_url)

    def on_open_docs(self) -> None:
        webbrowser.open(self.config.backend_docs_url)

    def on_view_logs(self) -> None:
        if self.log_viewer_win is None or not self.log_viewer_win.winfo_exists():
            self.log_viewer_win = LogViewerWindow(self, self.pm)
        else:
            self.log_viewer_win.lift()
            self.log_viewer_win.focus_force()

    def on_open_settings(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("CashCow Settings")
        dlg.geometry("480x360")
        dlg.resizable(False, False)
        dlg.grab_set()

        container = ttk.Frame(dlg, padding=15)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Project Root Directory:").pack(anchor=tk.W, pady=(0, 2))
        entry_root = ttk.Entry(container)
        entry_root.insert(0, str(self.config.project_root))
        entry_root.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(container, text="Frontend Command:").pack(anchor=tk.W, pady=(0, 2))
        entry_cmd = ttk.Entry(container)
        entry_cmd.insert(0, self.config.frontend_cmd)
        entry_cmd.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(container, text="Cloudflare Tunnel Name:").pack(anchor=tk.W, pady=(0, 2))
        entry_tunnel = ttk.Entry(container)
        entry_tunnel.insert(0, self.config.tunnel_name)
        entry_tunnel.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(container, text="Public URL:").pack(anchor=tk.W, pady=(0, 2))
        entry_url = ttk.Entry(container)
        entry_url.insert(0, self.config.public_url)
        entry_url.pack(fill=tk.X, pady=(0, 10))

        var_auto = tk.BooleanVar(value=self.config.auto_open_browser)
        cb_auto = ttk.Checkbutton(container, text="Automatically open browser on startup", variable=var_auto)
        cb_auto.pack(anchor=tk.W, pady=(0, 15))

        def save():
            self.config.project_root = entry_root.get().strip()
            self.config.frontend_cmd = entry_cmd.get().strip()
            self.config.tunnel_name = entry_tunnel.get().strip()
            self.config.public_url = entry_url.get().strip()
            self.config.auto_open_browser = var_auto.get()
            self.config.save()
            messagebox.showinfo("Settings Saved", "Configuration updated.", parent=dlg)
            dlg.destroy()

        ttk.Button(container, text="Save Settings", command=save).pack(side=tk.RIGHT)

    def on_exit(self) -> None:
        self.health_monitor.stop()
        self.cloudflare_svc.stop()
        self.frontend_svc.stop()
        self.backend_svc.stop()
        self.destroy()


def main():
    app = CashCowLauncherApp()
    app.mainloop()


if __name__ == "__main__":
    main()
