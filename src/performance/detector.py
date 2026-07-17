"""FFmpeg capability detection, executed exclusively through FFmpegRunner."""

import platform
from .hardware import ENCODERS, PRIORITY
from .models import HardwareBackend, HardwareCapabilities
from src.processor.runner import FFmpegRunner


class HardwareDetector:
    """Detect compiled FFmpeg encoders without requiring manual setup."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner

    def detect(self) -> HardwareCapabilities:
        try:
            stdout, stderr, _ = self.runner.run(["-hide_banner", "-encoders"])
            listing = f"{stdout}\n{stderr}"
        except Exception:
            listing = ""
        encoders = [name for names in ENCODERS.values() for name in names if name in listing]
        system, machine = platform.system(), platform.machine()
        preferred = self._preferred_backend(system, machine, encoders)
        return HardwareCapabilities(
            platform=system, machine=machine, backend=preferred,
            encoders=encoders, available=preferred is not HardwareBackend.SOFTWARE,
        )

    @staticmethod
    def _preferred_backend(system: str, machine: str, encoders: list[str]) -> HardwareBackend:
        # VideoToolbox is deliberately first on Apple Silicon, then general
        # portable priority follows the same hardware-first order.
        if system == "Darwin" and machine.lower() in {"arm64", "aarch64"} and any(e in encoders for e in ENCODERS[HardwareBackend.VIDEOTOOLBOX]):
            return HardwareBackend.VIDEOTOOLBOX
        for backend in PRIORITY:
            if any(e in encoders for e in ENCODERS[backend]):
                return backend
        return HardwareBackend.SOFTWARE
