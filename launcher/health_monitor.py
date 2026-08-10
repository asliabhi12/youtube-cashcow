"""Background health monitoring thread for Backend, Frontend, and Cloudflare Tunnel."""

import json
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Callable, Optional

from launcher.config import LauncherConfig


class HealthMonitor:
    """Monitors HTTP endpoints for Backend & Frontend, plus Cloudflare Tunnel state."""

    def __init__(
        self,
        config: LauncherConfig,
        on_status_change: Optional[Callable[[bool, bool, bool], None]] = None,
    ):
        self.config = config
        self.on_status_change = on_status_change

        self.backend_healthy = False
        self.frontend_healthy = False
        self.cloudflare_healthy = False

        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the background polling thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background polling thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _poll_loop(self) -> None:
        while self._running:
            try:
                b_ok = self.check_backend()
                f_ok = self.check_frontend()
                c_ok = self.check_cloudflare()

                changed = (
                    b_ok != self.backend_healthy
                    or f_ok != self.frontend_healthy
                    or c_ok != self.cloudflare_healthy
                )

                self.backend_healthy = b_ok
                self.frontend_healthy = f_ok
                self.cloudflare_healthy = c_ok

                if self.on_status_change and (changed or True):
                    try:
                        self.on_status_change(b_ok, f_ok, c_ok)
                    except Exception:
                        pass
            except Exception:
                pass

            time.sleep(self.config.poll_interval_sec)

    def check_backend(self) -> bool:
        """Probe GET http://localhost:8000/health AND verify CashCow identity in /openapi.json."""
        try:
            req_health = urllib.request.Request(
                self.config.backend_health_url,
                headers={"User-Agent": "CashCow-Launcher/1.0"},
            )
            with urllib.request.urlopen(req_health, timeout=1.5) as resp:
                if resp.status != 200:
                    return False
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") != "ok":
                    return False
        except Exception:
            return False

        try:
            openapi_url = self.config.backend_health_url.rsplit("/", 1)[0] + "/openapi.json"
            req_openapi = urllib.request.Request(
                openapi_url,
                headers={"User-Agent": "CashCow-Launcher/1.0"},
            )
            with urllib.request.urlopen(req_openapi, timeout=1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    title = data.get("info", {}).get("title")
                    return title == "CashCow"
        except Exception:
            return False

        return False

    def check_frontend(self) -> bool:
        """Probe GET http://localhost:3000."""
        try:
            req = urllib.request.Request(
                self.config.frontend_url,
                headers={"User-Agent": "CashCow-Launcher/1.0"},
            )
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 304, 404, 301, 302)
        except urllib.error.HTTPError as err:
            # Any HTTP status response means Next.js server is listening
            return err.code in (200, 304, 404, 301, 302)
        except Exception:
            return False

    def check_cloudflare(self) -> bool:
        """Detect whether Cloudflare Tunnel (cloudflared) is running."""
        # 1. Probe local metrics endpoint if exposed by cloudflared
        try:
            req = urllib.request.Request("http://127.0.0.1:20000/metrics")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass

        # 2. Check process list for cloudflared
        if sys.platform != "win32":
            try:
                res = subprocess.run(
                    ["pgrep", "-f", "cloudflared"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
                if res.returncode == 0 and res.stdout.strip():
                    return True
            except Exception:
                pass
        else:
            try:
                res = subprocess.run(
                    ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
                    capture_output=True,
                    text=True,
                    timeout=1.0,
                )
                if "cloudflared.exe" in res.stdout.lower():
                    return True
            except Exception:
                pass

        return False

    def wait_for_healthy(
        self,
        component: str,
        timeout: float = 45.0,
        cancel_event: Optional[threading.Event] = None,
    ) -> bool:
        """Block current worker thread until specified component becomes healthy."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if cancel_event and cancel_event.is_set():
                return False

            if component == "backend" and self.check_backend():
                self.backend_healthy = True
                return True
            elif component == "frontend" and self.check_frontend():
                self.frontend_healthy = True
                return True

            time.sleep(0.5)
        return False
