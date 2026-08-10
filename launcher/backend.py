"""Backend service controller for Uvicorn FastAPI server."""

import json
import os
import socket
import subprocess
import sys
import threading
import urllib.request
from typing import Any, Dict, Optional

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager


def is_port_in_use(port: int = 8000) -> bool:
    """Check if TCP port is currently listening on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def check_cashcow_identity(port: int = 8000) -> bool:
    """Query http://127.0.0.1:{port}/openapi.json and verify title == 'CashCow'."""
    url = f"http://127.0.0.1:{port}/openapi.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CashCow-Launcher/1.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("info", {}).get("title") == "CashCow"
    except Exception:
        return False
    return False


def get_port_occupant_info(port: int = 8000) -> Dict[str, Any]:
    """Retrieve PID, command line, and working directory of the process occupying the port."""
    info: Dict[str, Any] = {}
    if sys.platform != "win32":
        try:
            res = subprocess.run(
                ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                lines = res.stdout.strip().splitlines()
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        pid = int(parts[1])
                        info["pid"] = pid
                        ps_res = subprocess.run(
                            ["ps", "-p", str(pid), "-o", "command="],
                            capture_output=True,
                            text=True,
                            timeout=2.0,
                        )
                        if ps_res.returncode == 0:
                            info["command"] = ps_res.stdout.strip()
                        cwd_res = subprocess.run(
                            ["lsof", "-p", str(pid)],
                            capture_output=True,
                            text=True,
                            timeout=2.0,
                        )
                        if cwd_res.returncode == 0:
                            for line in cwd_res.stdout.splitlines():
                                if " cwd " in line:
                                    info["cwd"] = line.split()[-1]
                                    break
        except Exception:
            pass
    return info


class BackendService:
    """Manages the Uvicorn FastAPI Backend lifecycle independently."""

    def __init__(self, config: LauncherConfig, pm: ProcessManager):
        self.config = config
        self.pm = pm
        self.proc: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> bool:
        if self.is_running():
            self.pm.log_launcher("Backend is already running.")
            return True

        # Check if port 8000 is occupied before spawning Uvicorn
        port = 8000
        if is_port_in_use(port):
            if check_cashcow_identity(port):
                self.pm.log_launcher(f"Port {port} is occupied by an existing healthy CashCow backend. Reusing instance.")
                return True
            else:
                occupant = get_port_occupant_info(port)
                pid_str = f"PID {occupant['pid']}" if occupant.get("pid") else "Unknown PID"
                cmd_str = f", Command: '{occupant['command']}'" if occupant.get("command") else ""
                cwd_str = f", CWD: '{occupant['cwd']}'" if occupant.get("cwd") else ""
                self.pm.log_launcher(
                    f"ERROR: Port {port} is occupied by a non-CashCow application ({pid_str}{cmd_str}{cwd_str}). Refusing to start CashCow backend."
                )
                return False

        cwd = self.config.backend_cwd
        if not cwd.exists():
            self.pm.log_launcher(f"ERROR: Backend directory does not exist: {cwd}")
            return False

        python_exe = str(self.config.venv_python)
        cmd = [
            python_exe,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]

        env = os.environ.copy()
        venv_bin = str(self.config.venv_path / "bin")
        env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
        env["PYTHONPATH"] = f"{cwd}:{self.config.project_root / 'src'}:{env.get('PYTHONPATH', '')}"
        env["PYTHONUNBUFFERED"] = "1"

        self.pm.log_launcher(f"Starting Backend: {' '.join(cmd)} (cwd: {cwd})")
        try:
            kwargs = {}
            if sys.platform != "win32":
                kwargs["start_new_session"] = True
            else:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            self.proc = subprocess.Popen(
                cmd,
                cwd=str(cwd),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **kwargs,
            )

            threading.Thread(
                target=self.pm.stream_process_output,
                args=(self.proc, "backend"),
                daemon=True,
            ).start()

            self.pm.log_launcher(f"Backend started (PID {self.proc.pid}).")
            return True
        except Exception as exc:
            self.pm.log_launcher(f"ERROR starting Backend: {exc}")
            return False

    def stop(self) -> None:
        if self.proc is not None:
            self.pm.terminate_process(self.proc, "backend")
            self.proc = None
            if is_port_in_use(8000):
                if check_cashcow_identity(8000):
                    self.pm.log_launcher("Warning: Port 8000 is still occupied by a CashCow backend after termination.")
                else:
                    self.pm.log_launcher("Warning: Port 8000 remains occupied by an external process after backend termination.")

