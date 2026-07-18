"""Built-in workflow steps."""

from .download import DownloadStep
from .source import SourceStep
from .trim import TrimStep
from .crop import CropStep
from .resize import ResizeStep
from .rotate import RotateStep
from .overlay import OverlayStep
from .watermark import WatermarkStep
from .subtitles import SubtitlesStep
from .thumbnail import ThumbnailStep
from .concat import ConcatStep
from .encode import EncodeStep
from .audio_effect import AudioEffectStep
from .color_effect import ColorEffectStep
from .export import ExportStep

BUILTIN_STEPS = (DownloadStep, SourceStep, TrimStep, CropStep, ResizeStep, RotateStep, OverlayStep,
                 WatermarkStep, SubtitlesStep, ThumbnailStep, ConcatStep, EncodeStep,
                 AudioEffectStep, ColorEffectStep, ExportStep)
