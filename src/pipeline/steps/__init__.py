"""Built-in workflow steps."""

from .download import DownloadStep
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
from .export import ExportStep

BUILTIN_STEPS = (DownloadStep, TrimStep, CropStep, ResizeStep, RotateStep, OverlayStep,
                 WatermarkStep, SubtitlesStep, ThumbnailStep, ConcatStep, EncodeStep, ExportStep)
