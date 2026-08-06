"""Frontend service controller for Next.js web application."""

import os
import subprocess
import sys
import threading
from typing import Optional

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager


class FrontendService:
    """Manages the Next.js Frontend lifecycle independently."""

    def __init__(self, config: LauncherConfig, pm: ProcessManager):
        self.config = config
        self.pm = pm
        self.proc: Optional[subprocess.Popen] = None

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> bool:
        if self.is_running():
            self.pm.log_launcher("Frontend is already running.")
            return True

        cwd = self.config.frontend_cwd
        if not cwd.exists():
            self.pm.log_launcher(f"ERROR: Frontend directory does not exist: {cwd}")
            return False

        npm_bin = self.config.find_npm()
        sub_args = self.config.frontend_cmd.split()
        if sub_args and sub_args[0] in ("npm", "npx"):
            cmd = [npm_bin] + sub_args[1:]
        else:
            cmd = [npm_bin, "start"]

        env = os.environ.copy()
        npm_dir = os.path.dirname(npm_bin)
        if npm_dir:
            env["PATH"] = f"{npm_dir}:{env.get('PATH', '')}"

        self.pm.log_launcher(f"Starting Frontend: {' '.join(cmd)} (cwd: {cwd})")
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
                args=(self.proc, "frontend"),
                daemon=True,
            ).start()

            self.pm.log_launcher(f"Frontend started (PID {self.proc.pid}).")
            return True
        except Exception as exc:
            self.pm.log_launcher(f"ERROR starting Frontend: {exc}")
            return False

    def stop(self) -> None:
        if self.proc is not None:
            self.pm.terminate_process(self.proc, "frontend")
            self.proc = None
