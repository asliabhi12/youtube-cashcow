"""Hardware-aware encoding, benchmarking, metrics, and worker utilities."""

from .benchmark import Benchmark
from .decoder import DecoderDetector
from .detector import HardwareDetector
from .encoder import EncoderSelector, PerformanceEncoder
from .models import BenchmarkProfile, BenchmarkResult, DecoderInfo, EncoderDecision, HardwareBackend, HardwareCapabilities, PerformanceMetrics
from .presets import PRESETS, Preset
from .worker_pool import WorkerPool

__all__ = ["Benchmark", "BenchmarkProfile", "BenchmarkResult", "DecoderDetector", "DecoderInfo", "EncoderDecision", "EncoderSelector", "HardwareBackend", "HardwareCapabilities", "HardwareDetector", "PerformanceEncoder", "PerformanceMetrics", "PRESETS", "Preset", "WorkerPool"]
