"""High-level, local-media-only façade for independent FFmpeg primitives."""

from threading import Event
from typing import Callable

from src.config import Settings
from src.logger import get_logger

from . import audio, compositor, concat, crop, overlay, resize, rotate, subtitles, thumbnail, trim, watermark
from .encode import PRESETS, encoding_args
from .ffprobe import FFprobe
from .models import OverlayConfig, ProcessingResult, VideoInfo
from .runner import FFmpegRunner

ProgressCallback = Callable[[float], None]


class Processor:
    """Orchestrate reusable FFmpeg operations on local media only."""

    def __init__(self, settings: Settings) -> None:
        config = settings.ffmpeg
        executable = config.executable or config.path
        self.settings = settings
        self.logger = get_logger("youtube_cashcow.processor")
        self.runner = FFmpegRunner(executable, config.timeout, self.logger, config.hwaccel)
        self.probe = FFprobe(config.ffprobe, self.logger)
        self._performance_encoder = None

    def _encode(self, profile: str | None = None) -> list[str]:
        # Kept private so all existing Processor APIs remain unchanged.  The
        # performance layer only supplies encoding options; this façade still
        # delegates actual execution to FFmpegRunner through each operation.
        if self.settings.performance.hardware.lower() != "off":
            if self._performance_encoder is None:
                from src.performance.encoder import PerformanceEncoder
                self._performance_encoder = PerformanceEncoder.from_processor(self)
            return self._performance_encoder.default_args(profile)
        codec, preset, crf = PRESETS.get(profile or "", (self.settings.ffmpeg.codec, self.settings.ffmpeg.preset, str(self.settings.ffmpeg.crf)))
        args = encoding_args(codec, preset, int(crf), self.settings.ffmpeg.audio_codec)
        threads = self.settings.ffmpeg.threads
        if threads != "auto": args += ["-threads", str(threads)]
        return args

    def inspect(self, input_file: str) -> VideoInfo: return self.probe.inspect(input_file)
    def trim(self, input_file: str, output_file: str, start: float, end: float, *, stream_copy: bool = False, progress: ProgressCallback | None = None, cancel_event: Event | None = None) -> ProcessingResult: return trim.trim(self.runner, input_file, output_file, start, end, stream_copy=stream_copy, encode=self._encode(), progress=progress, cancel_event=cancel_event)
    def crop(self, input_file: str, output_file: str, width: int, height: int, x: int = 0, y: int = 0, **kwargs) -> ProcessingResult: return crop.crop(self.runner, input_file, output_file, width, height, x, y, encode=self._encode(), **kwargs)
    def resize(self, input_file: str, output_file: str, width: int | None = None, height: int | None = None, **kwargs) -> ProcessingResult: return resize.resize(self.runner, input_file, output_file, width, height, encode=self._encode(), **kwargs)
    def rotate(self, input_file: str, output_file: str, degrees: float, **kwargs) -> ProcessingResult: return rotate.rotate(self.runner, input_file, output_file, degrees, encode=self._encode(), **kwargs)
    def overlay(self, input_file: str, image_file: str, output_file: str, x: str | int = 0, y: str | int = 0, **kwargs) -> ProcessingResult: return overlay.overlay(self.runner, input_file, image_file, output_file, x, y, encode=self._encode(), **kwargs)
    def composite(self, input_file: str, output_file: str, config: OverlayConfig | dict, *, progress: ProgressCallback | None = None, cancel_event: Event | None = None) -> ProcessingResult:
        overlay_config = config if isinstance(config, OverlayConfig) else OverlayConfig(**config)
        return compositor.composite(self.runner, input_file, overlay_config, output_file, encode=self._encode(), progress=progress, cancel_event=cancel_event)
    def watermark(self, input_file: str, output_file: str, *, image_file: str | None = None, text: str | None = None, **kwargs) -> ProcessingResult:
        if bool(image_file) == bool(text): raise ValueError("Provide exactly one of image_file or text")
        if image_file: return watermark.image_watermark(self.runner, input_file, image_file, output_file, encode=self._encode(), **kwargs)
        return watermark.text_watermark(self.runner, input_file, output_file, text or "", encode=self._encode(), **kwargs)
    def burn_subtitles(self, input_file: str, subtitle_file: str, output_file: str, **kwargs) -> ProcessingResult: return subtitles.burn_subtitles(self.runner, input_file, subtitle_file, output_file, encode=self._encode(), **kwargs)
    def thumbnail(self, input_file: str, output_file: str, timestamp: float = 0, **kwargs) -> ProcessingResult: return thumbnail.thumbnail(self.runner, input_file, output_file, timestamp, **kwargs)
    def concat(self, input_files: list[str], output_file: str, *, reencode: bool = False, **kwargs) -> ProcessingResult: return concat.concat(self.runner, self.probe, input_files, output_file, reencode=reencode, encode=self._encode(), **kwargs)
    def extract_audio(self, input_file: str, output_file: str, **kwargs) -> ProcessingResult: return audio.extract_audio(self.runner, input_file, output_file, codec=self.settings.ffmpeg.audio_codec, **kwargs)
    def replace_audio(self, input_file: str, audio_file: str, output_file: str, **kwargs) -> ProcessingResult: return audio.replace_audio(self.runner, input_file, audio_file, output_file, encode=self._encode(), **kwargs)
    def mute(self, input_file: str, output_file: str, **kwargs) -> ProcessingResult: return audio.audio_filter(self.runner, input_file, output_file, "volume=0", encode=self._encode(), **kwargs)
    def volume(self, input_file: str, output_file: str, factor: float, **kwargs) -> ProcessingResult: return audio.audio_filter(self.runner, input_file, output_file, f"volume={factor}", encode=self._encode(), **kwargs)
    def normalize(self, input_file: str, output_file: str, **kwargs) -> ProcessingResult: return audio.audio_filter(self.runner, input_file, output_file, "loudnorm", encode=self._encode(), **kwargs)
