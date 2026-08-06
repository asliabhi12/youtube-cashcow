"""Configuration manager for CashCow Desktop Launcher with Cloudflare Tunnel support."""

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict


class LauncherConfig:
    DEFAULT_PROJECT_ROOT = "/Users/abhishek/Documents/youtube-cashcow"
    CONFIG_FILE_NAME = ".cashcow_launcher.json"

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root or self.DEFAULT_PROJECT_ROOT).resolve()
        self.config_path = Path.home() / self.CONFIG_FILE_NAME
        
        # Backend defaults
        self.backend_relative_cwd = "cashcow/backend"
        self.backend_cmd = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
        self.backend_health_url = "http://localhost:8000/health"
        self.backend_docs_url = "http://localhost:8000/docs"
        
        # Frontend defaults
        self.frontend_relative_cwd = "cashcow/frontend"
        self.frontend_cmd = "npm start"
        self.frontend_dev_cmd = "npm run dev"
        self.frontend_url = "http://localhost:3000"

        # Cloudflare Tunnel defaults
        self.tunnel_name = "cashcow"
        self.public_url = "https://api.cashcow.dpdns.org"
        self.auto_start_cloudflare = True
        
        # General defaults
        self.auto_open_browser = True
        self.poll_interval_sec = 2.0
        self.startup_timeout_sec = 45.0

        self.load()

    @property
    def venv_path(self) -> Path:
        return self.project_root / ".venv"

    @property
    def venv_python(self) -> Path:
        bin_python = self.venv_path / "bin" / "python"
        if bin_python.exists():
            return bin_python
        bin_python3 = self.venv_path / "bin" / "python3"
        if bin_python3.exists():
            return bin_python3
        return Path(shutil.which("python3") or "python3")

    @property
    def backend_cwd(self) -> Path:
        return self.project_root / self.backend_relative_cwd

    @property
    def frontend_cwd(self) -> Path:
        return self.project_root / self.frontend_relative_cwd

    def find_npm(self) -> str:
        npm_bin = shutil.which("npm")
        if npm_bin:
            return npm_bin
        for fallback in ["/opt/homebrew/bin/npm", "/usr/local/bin/npm", "~/.nvm/versions/node/current/bin/npm"]:
            expanded = os.path.expanduser(fallback)
            if os.path.exists(expanded):
                return expanded
        return "npm"

    def find_cloudflared(self) -> str | None:
        cf_bin = shutil.which("cloudflared")
        if cf_bin:
            return cf_bin
        for fallback in ["/opt/homebrew/bin/cloudflared", "/usr/local/bin/cloudflared"]:
            expanded = os.path.expanduser(fallback)
            if os.path.exists(expanded):
                return expanded
        return None

    def load(self) -> None:
        """Load user settings from JSON if present."""
        if not self.config_path.exists():
            return
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)
            if "project_root" in data:
                self.project_root = Path(data["project_root"]).resolve()
            if "frontend_cmd" in data:
                self.frontend_cmd = data["frontend_cmd"]
            if "tunnel_name" in data:
                self.tunnel_name = data["tunnel_name"]
            if "public_url" in data:
                self.public_url = data["public_url"]
            if "auto_start_cloudflare" in data:
                self.auto_start_cloudflare = bool(data["auto_start_cloudflare"])
            if "auto_open_browser" in data:
                self.auto_open_browser = bool(data["auto_open_browser"])
        except Exception:
            pass

    def save(self) -> None:
        """Save user settings to JSON."""
        data = {
            "project_root": str(self.project_root),
            "backend_relative_cwd": self.backend_relative_cwd,
            "frontend_relative_cwd": self.frontend_relative_cwd,
            "frontend_cmd": self.frontend_cmd,
            "tunnel_name": self.tunnel_name,
            "public_url": self.public_url,
            "auto_start_cloudflare": self.auto_start_cloudflare,
            "auto_open_browser": self.auto_open_browser,
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass
