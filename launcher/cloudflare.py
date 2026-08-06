"""Cloudflare Tunnel service controller with auto-restart logic."""

import os
import subprocess
import sys
import threading
import time
from typing import Optional

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager


class CloudflareService:
    """Manages the Cloudflare Tunnel process independently with auto-restart support."""

    MAX_RESTART_ATTEMPTS = 3

    def __init__(self, config: LauncherConfig, pm: ProcessManager):
        self.config = config
        self.pm = pm
        self.proc: Optional[subprocess.Popen] = None

        self._manual_stop = False
        self._restart_attempts = 0
        self._start_timestamp = 0.0
        self._monitor_thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> bool:
        if self.is_running():
            self.pm.emit_log("cloudflare", "Cloudflare Tunnel is already running.")
            return True

        cf_bin = self.config.find_cloudflared()
        if not cf_bin:
            error_msg = "Cloudflared is not installed."
            self.pm.emit_log("cloudflare", f"ERROR: {error_msg}")
            raise RuntimeError(f"{error_msg}\nPlease install it via Homebrew ('brew install cloudflared') or from Cloudflare.")

        cmd = [cf_bin, "tunnel", "run", self.config.tunnel_name]
        self.pm.emit_log("cloudflare", f"Starting Cloudflare Tunnel: {' '.join(cmd)}")

        self._manual_stop = False
        self._start_timestamp = time.time()

        env = os.environ.copy()
        cf_dir = os.path.dirname(cf_bin)
        if cf_dir:
            env["PATH"] = f"{cf_dir}:{env.get('PATH', '')}"

        try:
            kwargs = {}
            if sys.platform != "win32":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            self.proc = subprocess.Popen(
                cmd,
                cwd=str(self.config.project_root),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **kwargs,
            )

            # Stream logs
            threading.Thread(
                target=self.pm.stream_process_output,
                args=(self.proc, "cloudflare"),
                daemon=True,
            ).start()

            # Wait briefly to detect instant crash / auth failure
            time.sleep(1.5)
            if self.proc.poll() is not None:
                ret = self.proc.poll()
                err = f"Cloudflare Tunnel exited immediately with code {ret}."
                self.pm.emit_log("cloudflare", f"ERROR: {err}")
                self.proc = None
                raise RuntimeError(f"{err}\nCheck if tunnel '{self.config.tunnel_name}' is configured or run 'cloudflared login'.")

            self.pm.emit_log("cloudflare", f"Cloudflare Tunnel connected (PID {self.proc.pid}).")

            # Start watcher thread for auto-restart
            if self._monitor_thread is None or not self._monitor_thread.is_alive():
                self._monitor_thread = threading.Thread(target=self._auto_restart_watcher, daemon=True)
                self._monitor_thread.start()

            return True
        except Exception as exc:
            self.pm.emit_log("cloudflare", f"ERROR starting Cloudflare Tunnel: {exc}")
            raise

    def stop(self) -> None:
        self._manual_stop = True
        if self.proc is not None:
            self.pm.emit_log("cloudflare", "Stopping Cloudflare Tunnel...")
            self.pm.terminate_process(self.proc, "cloudflare")
            self.proc = None

    def _auto_restart_watcher(self) -> None:
        """Background thread monitoring for unexpected process exit and auto-restarting."""
        while True:
            time.sleep(2.0)
            if self._manual_stop:
                break

            if self.proc is not None:
                # If process has been running stably for >30s, reset attempt counter
                if self.is_running() and (time.time() - self._start_timestamp > 30.0):
                    if self._restart_attempts > 0:
                        self.pm.emit_log("cloudflare", "Tunnel running stably. Resetting restart attempt counter.")
                        self._restart_attempts = 0

                # Check if process died unexpectedly
                if not self.is_running() and not self._manual_stop:
                    if self._restart_attempts < self.MAX_RESTART_ATTEMPTS:
                        self._restart_attempts += 1
                        self.pm.emit_log(
                            "cloudflare",
                            f"⚠️ Tunnel died unexpectedly! Auto-restart attempt {self._restart_attempts}/{self.MAX_RESTART_ATTEMPTS} in 3 seconds...",
                        )
                        time.sleep(3.0)
                        if not self._manual_stop:
                            try:
                                self.start()
                            except Exception as exc:
                                self.pm.emit_log("cloudflare", f"Auto-restart attempt failed: {exc}")
                    else:
                        self.pm.emit_log(
                            "cloudflare",
                            f"❌ Maximum auto-restart attempts ({self.MAX_RESTART_ATTEMPTS}) reached. Tunnel remains disconnected.",
                        )
                        break
