"""Backend service controller for Uvicorn FastAPI server."""

import os
import subprocess
import sys
import threading
from typing import Optional

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager


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
            "--reload",
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
