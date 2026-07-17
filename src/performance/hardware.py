"""Stable encoder families and their preferred selection order."""

from .models import HardwareBackend

ENCODERS: dict[HardwareBackend, tuple[str, ...]] = {
    HardwareBackend.VIDEOTOOLBOX: ("h264_videotoolbox", "hevc_videotoolbox"),
    HardwareBackend.NVENC: ("h264_nvenc", "hevc_nvenc", "av1_nvenc"),
    HardwareBackend.QSV: ("h264_qsv", "hevc_qsv"),
    HardwareBackend.SOFTWARE: ("libx264", "libx265", "libsvtav1"),
}

PRIORITY = (HardwareBackend.VIDEOTOOLBOX, HardwareBackend.NVENC, HardwareBackend.QSV, HardwareBackend.SOFTWARE)


def backend_for_encoder(encoder: str) -> HardwareBackend:
    for backend, names in ENCODERS.items():
        if encoder in names:
            return backend
    return HardwareBackend.SOFTWARE
