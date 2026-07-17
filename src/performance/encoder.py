"""Encoder strategy and argument generation; execution stays in FFmpegRunner."""

from pathlib import Path
from typing import TYPE_CHECKING

from .detector import HardwareDetector
from .hardware import ENCODERS, backend_for_encoder
from .models import EncoderDecision, HardwareBackend, HardwareCapabilities
from .presets import PRESETS
from src.processor.exceptions import ProcessingFailedError
from src.processor.runner import FFmpegRunner

if TYPE_CHECKING:
    from src.processor.processor import Processor


class EncoderSelector:
    """Choose the fastest usable encoder while retaining software fallback."""

    def choose(
        self,
        resolution: tuple[int, int] | None = None,
        quality: str = "balanced",
        speed: str = "balanced",
        hardware: HardwareCapabilities | None = None,
        codec: str = "h264",
        preferred_encoder: str = "auto",
    ) -> EncoderDecision:
        capabilities = hardware or HardwareCapabilities(platform="unknown", machine="unknown")
        preferred = preferred_encoder.lower()
        if preferred != "auto" and preferred in capabilities.encoders:
            return self._decision(preferred, quality, speed)
        candidates = self._codec_candidates(codec, capabilities.backend)
        encoder = next((item for item in candidates if item in capabilities.encoders), None)
        if encoder is None:
            encoder = self._software_encoder(codec, capabilities.encoders)
        return self._decision(encoder, quality, speed)

    @staticmethod
    def _codec_candidates(codec: str, backend: HardwareBackend) -> tuple[str, ...]:
        prefix = "hevc" if codec in {"h265", "hevc"} else "av1" if codec == "av1" else "h264"
        return tuple(item for item in ENCODERS.get(backend, ()) if item.startswith(prefix))

    @staticmethod
    def _software_encoder(codec: str, available: list[str]) -> str:
        desired = {"h265": "libx265", "hevc": "libx265", "av1": "libsvtav1"}.get(codec, "libx264")
        return desired if not available or desired in available else "libx264"

    @staticmethod
    def _decision(encoder: str, quality: str, speed: str) -> EncoderDecision:
        hardware = backend_for_encoder(encoder) is not HardwareBackend.SOFTWARE
        # VideoToolbox and other hardware encoders use bitrate/quality values
        # rather than x264 CRF. Software retains CRF for compatibility.
        bitrate = {"high": "12M", "balanced": "8M", "low": "4M"}.get(quality, "8M")
        return EncoderDecision(
            encoder=encoder, backend=backend_for_encoder(encoder), hardware=hardware,
            bitrate=bitrate if hardware else None,
            crf={"high": 18, "balanced": 23, "low": 28}.get(quality, 23) if not hardware else None,
            preset="fast" if speed in {"fast", "realtime"} else "medium",
        )


class PerformanceEncoder:
    """Apply selector decisions and invoke the existing processor runner."""

    def __init__(self, runner: FFmpegRunner, settings, detector: HardwareDetector | None = None) -> None:
        self.runner, self.settings = runner, settings
        self.detector = detector or HardwareDetector(runner)
        self.selector = EncoderSelector()
        self._capabilities: HardwareCapabilities | None = None

    @classmethod
    def from_processor(cls, processor: "Processor") -> "PerformanceEncoder":
        return cls(processor.runner, processor.settings)

    @property
    def capabilities(self) -> HardwareCapabilities:
        if self._capabilities is None:
            self._capabilities = self.detector.detect()
        return self._capabilities

    def decision(self, profile: str | None = None, *, force_software: bool = False) -> EncoderDecision:
        preset = PRESETS.get((profile or "").lower())
        codec = preset.codec if preset else self.settings.ffmpeg.codec
        caps = self.capabilities
        if force_software or self.settings.performance.hardware.lower() == "software":
            caps = caps.model_copy(update={"backend": HardwareBackend.SOFTWARE, "encoders": [e for e in caps.encoders if e.startswith("lib")]})
        chosen = self.selector.choose(
            quality="high" if preset and preset.name == "lossless" else "balanced",
            hardware=caps, codec=codec,
            preferred_encoder=self.settings.performance.preferred_encoder,
        )
        if preset:
            chosen = chosen.model_copy(update={"bitrate": preset.bitrate or chosen.bitrate, "gop": preset.gop, "pixel_format": preset.pixel_format, "faststart": preset.faststart})
        return chosen

    def default_args(self, profile: str | None = None) -> list[str]:
        return self.args_for(self.decision(profile), audio_bitrate=self.settings.ffmpeg.bitrate)

    @staticmethod
    def args_for(decision: EncoderDecision, *, audio_codec: str = "aac", audio_bitrate: str = "192k", threads: str | int = "auto") -> list[str]:
        args = ["-c:v", decision.encoder, "-pix_fmt", decision.pixel_format, "-g", str(decision.gop)]
        if decision.hardware:
            if decision.bitrate:
                args += ["-b:v", decision.bitrate]
            # Quality value is a CRF-like knob supported by VideoToolbox.
            if decision.backend is HardwareBackend.VIDEOTOOLBOX:
                args += ["-q:v", "65"]
        else:
            args += ["-preset", decision.preset or "medium", "-crf", str(decision.crf if decision.crf is not None else 23)]
        args += ["-c:a", audio_codec, "-b:a", audio_bitrate]
        if decision.faststart:
            args += ["-movflags", "+faststart"]
        if threads != "auto":
            args += ["-threads", str(threads)]
        return args

    def encode(self, input_file: str | Path, output_file: str | Path, *, profile: str | None = None, force_software: bool = False, duration: float | None = None) -> tuple[EncoderDecision, str, float]:
        output = Path(output_file)
        decision = self.decision(profile, force_software=force_software)
        # ``-t`` limits the output duration so every encoder processes an
        # identical clip; execution still runs through FFmpegRunner unchanged.
        limit = ["-t", str(duration)] if duration and duration > 0 else []
        args = ["-i", str(input_file), *limit, *self.args_for(decision, audio_bitrate=self.settings.ffmpeg.bitrate, threads=self.settings.ffmpeg.threads), "-y", str(output)]
        _, stderr, elapsed = self.runner.run(args)
        if not output.is_file() or output.stat().st_size == 0:
            raise ProcessingFailedError(f"FFmpeg completed but did not create a valid output: {output}")
        return decision, stderr, elapsed
