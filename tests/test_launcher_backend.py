"""Regression tests for CashCow Desktop Launcher Backend lifecycle and identity validation."""

import json
from unittest.mock import MagicMock, patch
import pytest

from launcher.config import LauncherConfig
from launcher.process_manager import ProcessManager
from launcher.backend import BackendService, check_cashcow_identity, is_port_in_use
from launcher.health_monitor import HealthMonitor


@pytest.fixture
def mock_config(tmp_path):
    config = LauncherConfig(project_root=str(tmp_path))
    (tmp_path / "cashcow" / "backend").mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def mock_pm(mock_config):
    return ProcessManager(mock_config)


def test_1_port_8000_is_free_backend_starts(mock_config, mock_pm):
    """TEST 1: Port 8000 is free. CashCow backend starts normally."""
    svc = BackendService(mock_config, mock_pm)

    with patch("launcher.backend.is_port_in_use", return_value=False), \
         patch("subprocess.Popen") as mock_popen:

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        started = svc.start()
        assert started is True
        assert svc.proc is not None
        assert svc.proc.pid == 12345

        # Verify command does NOT include --reload
        cmd_args = mock_popen.call_args[0][0]
        assert "--reload" not in cmd_args
        assert cmd_args[-2:] == ["--port", "8000"]


def test_2_cashcow_already_running_reused(mock_config, mock_pm):
    """TEST 2: CashCow is already running on 8000. Launcher detects it and does NOT spawn second process."""
    svc = BackendService(mock_config, mock_pm)

    with patch("launcher.backend.is_port_in_use", return_value=True), \
         patch("launcher.backend.check_cashcow_identity", return_value=True), \
         patch("subprocess.Popen") as mock_popen:

        started = svc.start()
        assert started is True
        # Must NOT call Popen to start a duplicate backend
        mock_popen.assert_not_called()


def test_3_other_application_occupies_8000_refuses_to_start(mock_config, mock_pm):
    """TEST 3: Another application occupies 8000. Launcher refuses to start CashCow and reports conflict."""
    svc = BackendService(mock_config, mock_pm)

    with patch("launcher.backend.is_port_in_use", return_value=True), \
         patch("launcher.backend.check_cashcow_identity", return_value=False), \
         patch("launcher.backend.get_port_occupant_info", return_value={"pid": 9999, "command": "rogue_app", "cwd": "/tmp"}), \
         patch("subprocess.Popen") as mock_popen:

        started = svc.start()
        assert started is False
        mock_popen.assert_not_called()
        # Check launcher logs for error details
        logs = "".join(mock_pm.launcher_logs)
        assert "ERROR: Port 8000 is occupied by a non-CashCow application" in logs
        assert "PID 9999" in logs


def test_4_health_200_but_openapi_not_cashcow_unhealthy(mock_config):
    """TEST 4: /health returns 200 but /openapi.json identifies another app. Backend is considered unhealthy."""
    monitor = HealthMonitor(mock_config)

    def mock_urlopen(req, timeout=1.5):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        mock_resp = MagicMock()
        mock_resp.status = 200
        if "/health" in url:
            mock_resp.read.return_value = json.dumps({"status": "ok"}).encode("utf-8")
        elif "/openapi.json" in url:
            mock_resp.read.return_value = json.dumps({
                "info": {"title": "Secure Document Recovery API", "version": "2.0.0"}
            }).encode("utf-8")
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        healthy = monitor.check_backend()
        assert healthy is False, "Backend must be unhealthy when openapi.json title is not 'CashCow'"


def test_5_cashcow_starts_and_stops_cleanly(mock_config, mock_pm):
    """TEST 5: CashCow starts and then stops. The managed backend process exits cleanly."""
    svc = BackendService(mock_config, mock_pm)

    with patch("launcher.backend.is_port_in_use", return_value=False), \
         patch("subprocess.Popen") as mock_popen:

        mock_proc = MagicMock()
        mock_proc.pid = 54321
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        svc.start()
        assert svc.is_running() is True

        # Stop process
        with patch.object(mock_pm, "terminate_process") as mock_term:
            svc.stop()
            mock_term.assert_called_once_with(mock_proc, "backend")
            assert svc.proc is None


def test_6_start_stop_start_cycle(mock_config, mock_pm):
    """TEST 6: Start -> stop -> start cycle succeeds cleanly without address conflict."""
    svc = BackendService(mock_config, mock_pm)

    with patch("launcher.backend.is_port_in_use", return_value=False), \
         patch("subprocess.Popen") as mock_popen:

        mock_proc1 = MagicMock()
        mock_proc1.pid = 1001
        mock_proc1.poll.return_value = None

        mock_proc2 = MagicMock()
        mock_proc2.pid = 1002
        mock_proc2.poll.return_value = None

        mock_popen.side_effect = [mock_proc1, mock_proc2]

        # 1. First start
        assert svc.start() is True
        assert svc.proc.pid == 1001

        # 2. Stop
        mock_proc1.poll.return_value = 0
        svc.stop()
        assert svc.proc is None

        # 3. Second start
        assert svc.start() is True
        assert svc.proc.pid == 1002
