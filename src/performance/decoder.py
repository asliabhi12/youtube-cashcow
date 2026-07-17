"""Decode-path detection, executed exclusively through FFmpegRunner.

The benchmark needs to report whether the input is decoded in software (e.g.
AV1 via ``libdav1d``) or through a hardware acceleration method, because
software decode of a modern codec can dominate wall-clock time and hide the
encoder throughput a benchmark is meant to isolate.
"""

from .models import DecoderInfo
from src.processor.runner import FFmpegRunner

# Preferred software decoder per input codec. The value is validated against the
# installed FFmpeg's ``-decoders`` listing; if absent, the codec's own native
# decoder name is used as a safe fallback.
_SOFTWARE_DECODERS: dict[str, str] = {
    "av1": "libdav1d",
    "vp9": "libvpx-vp9",
    "vp8": "libvpx",
    "hevc": "hevc",
    "h265": "hevc",
    "h264": "h264",
    "mpeg4": "mpeg4",
    "mpeg2video": "mpeg2video",
}


class DecoderDetector:
    """Determine how a given input codec is decoded by the current FFmpeg."""

    def __init__(self, runner: FFmpegRunner) -> None:
        self.runner = runner
        self._listing: str | None = None

    def detect(self, codec: str | None, hwaccel: str | None = None) -> DecoderInfo:
        """Report the decode path for ``codec`` under the active ``hwaccel``.

        ``hwaccel`` mirrors ``settings.ffmpeg.hwaccel``: when set, the runner
        passes ``-hwaccel`` and decode is performed on the hardware, so the
        report reflects that rather than guessing from the codec alone.
        """
        if hwaccel:
            return DecoderInfo(codec=codec, decoder=hwaccel, hardware=True)
        decoder = self._software_decoder(codec)
        return DecoderInfo(codec=codec, decoder=decoder, hardware=False)

    def _software_decoder(self, codec: str | None) -> str | None:
        if not codec:
            return None
        preferred = _SOFTWARE_DECODERS.get(codec.lower())
        listing = self._decoder_listing()
        if preferred and preferred in listing:
            return preferred
        # Fall back to the codec's native decoder when a specialised library
        # decoder is not compiled in; the native name usually matches the codec.
        native = codec.lower()
        if native in listing:
            return native
        return preferred or native

    def _decoder_listing(self) -> str:
        if self._listing is None:
            try:
                stdout, stderr, _ = self.runner.run(["-hide_banner", "-decoders"])
                self._listing = f"{stdout}\n{stderr}"
            except Exception:
                self._listing = ""
        return self._listing
