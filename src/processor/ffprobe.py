"""FFprobe wrapper returning a stable, strongly typed media description."""

import json
import logging

from .exceptions import InvalidMediaError, ProcessingFailedError
from .models import VideoInfo
from .runner import FFmpegRunner
from .utils import PathLike, fps_value, input_path


class FFprobe:
    """Inspect local media using FFprobe's JSON output."""

    def __init__(self, executable: str, logger: logging.Logger, timeout: int = 60) -> None:
        self.runner = FFmpegRunner(executable, timeout, logger)

    def inspect(self, file_path: PathLike) -> VideoInfo:
        """Return video and audio stream details for a local media file."""
        path = input_path(file_path)
        try:
            stdout, _, _ = self.runner.run(["-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
        except ProcessingFailedError as exc:
            raise InvalidMediaError(f"Unable to inspect media '{path}'") from exc
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise InvalidMediaError(f"FFprobe returned invalid media metadata for: {path}") from exc
        streams = payload.get("streams", [])
        video = next((item for item in streams if item.get("codec_type") == "video"), {})
        audio = next((item for item in streams if item.get("codec_type") == "audio"), {})
        if not video and not audio:
            raise InvalidMediaError(f"No media streams found in: {path}")
        container = payload.get("format", {})
        return VideoInfo(
            path=path, width=video.get("width"), height=video.get("height"),
            fps=fps_value(video.get("avg_frame_rate")), duration=_number(container.get("duration")),
            bitrate=_integer(container.get("bit_rate")), codec=video.get("codec_name"),
            audio_codec=audio.get("codec_name"), has_audio=bool(audio),
        )


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _integer(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
