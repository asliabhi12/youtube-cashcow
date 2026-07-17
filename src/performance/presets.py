"""Production-oriented encoding presets."""

from .models import EncodingPreset


class Preset:
    YOUTUBE_1080 = EncodingPreset(name="youtube_1080", bitrate="8M", gop=60)
    YOUTUBE_4K = EncodingPreset(name="youtube_4k", bitrate="35M", gop=60)
    SHORTS = EncodingPreset(name="shorts", bitrate="10M", gop=60)
    TIKTOK = EncodingPreset(name="tiktok", bitrate="10M", gop=60)
    INSTAGRAM = EncodingPreset(name="instagram", bitrate="8M", gop=60)
    ARCHIVE = EncodingPreset(name="archive", codec="h265", bitrate="16M", gop=120)
    LOSSLESS = EncodingPreset(name="lossless", codec="h264", bitrate=None, gop=1, hardware_preferred=False)


PRESETS = {value.name: value for value in (Preset.YOUTUBE_1080, Preset.YOUTUBE_4K, Preset.SHORTS, Preset.TIKTOK, Preset.INSTAGRAM, Preset.ARCHIVE, Preset.LOSSLESS)}
