"""Central Process Manager base for CashCow desktop launcher."""

import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Callable, Deque, Optional

from launcher.config import LauncherConfig


class ProcessManager:
    """Central log aggregator and process termination helper."""

    MAX_LOG_HISTORY = 5000

    def __init__(self, config: LauncherConfig):
        self.config = config

        self.backend_logs: Deque[str] = deque(maxlen=self.MAX_LOG_HISTORY)
        self.frontend_logs: Deque[str] = deque(maxlen=self.MAX_LOG_HISTORY)
        self.cloudflare_logs: Deque[str] = deque(maxlen=self.MAX_LOG_HISTORY)
        self.launcher_logs: Deque[str] = deque(maxlen=self.MAX_LOG_HISTORY)

        self._log_listeners: list[Callable[[str, str], None]] = []
        self._lock = threading.Lock()

        self.log_launcher("CashCow Process Manager initialized.")

    def add_log_listener(self, listener: Callable[[str, str], None]) -> None:
        """Register a callback for real-time log lines: listener(source, line)."""
        with self._lock:
            if listener not in self._log_listeners:
                self._log_listeners.append(listener)

    def remove_log_listener(self, listener: Callable[[str, str], None]) -> None:
        with self._lock:
            if listener in self._log_listeners:
                self._log_listeners.remove(listener)

    def emit_log(self, source: str, message: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {message.strip()}\n"
        with self._lock:
            if source == "backend":
                self.backend_logs.append(line)
            elif source == "frontend":
                self.frontend_logs.append(line)
            elif source == "cloudflare":
                self.cloudflare_logs.append(line)
            else:
                self.launcher_logs.append(line)

            for listener in list(self._log_listeners):
                try:
                    listener(source, line)
                except Exception:
                    pass

    def log_launcher(self, message: str) -> None:
        self.emit_log("launcher", message)

    def stream_process_output(self, proc: subprocess.Popen, source: str) -> None:
        """Stream process stdout/stderr line-by-line to internal log queue and listeners."""
        try:
            if proc.stdout:
                for line in iter(proc.stdout.readline, ""):
                    if line:
                        self.emit_log(source, line)
                    else:
                        break
        except Exception as exc:
            self.emit_log(source, f"[{source} log stream ended: {exc}]")
        finally:
            self.emit_log(source, f"[{source} process exited with code {proc.poll()}]")

    def terminate_process(self, proc: Optional[subprocess.Popen], name: str) -> None:
        """Terminate a process group cleanly."""
        if proc is None or proc.poll() is not None:
            return

        pid = proc.pid
        self.log_launcher(f"Stopping {name} process (PID {pid})...")
        try:
            if sys.platform != "win32":
                try:
                    pgid = os.getpgid(pid)
                    os.killpg(pgid, signal.SIGTERM)
                except OSError:
                    proc.terminate()
            else:
                proc.terminate()

            # Give up to 5 seconds to exit gracefully
            for _ in range(50):
                if proc.poll() is not None:
                    break
                time.sleep(0.1)

            if proc.poll() is None:
                self.log_launcher(f"Force killing {name} (PID {pid})...")
                if sys.platform != "win32":
                    try:
                        pgid = os.getpgid(pid)
                        os.killpg(pgid, signal.SIGKILL)
                    except OSError:
                        proc.kill()
                else:
                    proc.kill()
                proc.wait(timeout=2)
        except Exception as exc:
            self.log_launcher(f"Error terminating {name}: {exc}")
