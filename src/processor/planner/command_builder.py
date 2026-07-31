"""Builder for complete FFmpeg command line arguments.

Combines input paths, filter graphs, hardware acceleration settings, codec choices,
and output parameters into a single executable command array.
"""

from pathlib import Path
from typing import Sequence
from src.config import Settings
from .filter_graph import FilterGraphResult
from .operations import EncodeOperation
from .plan import RenderPlan


class FFmpegCommandBuilder:
    """Constructs single-pass FFmpeg execution arguments."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_command(
        self,
        input_file: Path,
        output_file: Path,
        plan: RenderPlan,
        graph: FilterGraphResult,
        encode_args_fn=None,
    ) -> list[str]:
        """Build the full CLI command argument sequence for FFmpeg execution."""
        args: list[str] = ["-y"]

        # Primary input
        args.extend(["-i", str(input_file)])

        # Additional input files (overlays, assets)
        for extra in graph.extra_inputs:
            args.extend(["-i", str(extra)])

        # Filter specification
        if graph.filter_complex:
            args.extend(["-filter_complex", graph.filter_complex])
            if graph.video_map:
                args.extend(["-map", graph.video_map])
            if graph.audio_map:
                args.extend(["-map", graph.audio_map])
        else:
            if graph.video_filters:
                args.extend(["-vf", ",".join(graph.video_filters)])
            if graph.audio_filters:
                args.extend(["-af", ",".join(graph.audio_filters)])

        # Determine encoding parameters
        profile = None
        for op in plan:
            if isinstance(op, EncodeOperation) and op.profile:
                profile = op.profile

        if encode_args_fn:
            encoding_flags = encode_args_fn(profile)
        else:
            encoding_flags = self._default_encoding_flags(profile)

        args.extend(encoding_flags)
        args.append(str(output_file))
        return args

    def _default_encoding_flags(self, profile: str | None = None) -> list[str]:
        ffmpeg_cfg = self.settings.ffmpeg
        codec = ffmpeg_cfg.codec
        preset = ffmpeg_cfg.preset
        crf = str(ffmpeg_cfg.crf)
        audio_codec = ffmpeg_cfg.audio_codec

        flags = [
            "-c:v", codec,
            "-preset", preset,
            "-crf", crf,
            "-c:a", audio_codec,
        ]
        if ffmpeg_cfg.audio_bitrate:
            flags.extend(["-b:a", ffmpeg_cfg.audio_bitrate])
        if ffmpeg_cfg.video_bitrate:
            flags.extend(["-b:v", ffmpeg_cfg.video_bitrate])
        if ffmpeg_cfg.threads != "auto":
            flags.extend(["-threads", str(ffmpeg_cfg.threads)])

        return flags
