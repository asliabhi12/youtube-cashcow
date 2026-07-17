"""Hardware-aware encoding, benchmarking, metrics, and worker utilities."""

from .benchmark import Benchmark
from .detector import HardwareDetector
from .encoder import EncoderSelector, PerformanceEncoder
from .models import BenchmarkResult, EncoderDecision, HardwareBackend, HardwareCapabilities, PerformanceMetrics
from .presets import PRESETS, Preset
from .worker_pool import WorkerPool

__all__ = ["Benchmark", "BenchmarkResult", "EncoderDecision", "EncoderSelector", "HardwareBackend", "HardwareCapabilities", "HardwareDetector", "PerformanceEncoder", "PerformanceMetrics", "PRESETS", "Preset", "WorkerPool"]
