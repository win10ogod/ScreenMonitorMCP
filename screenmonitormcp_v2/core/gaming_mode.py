"""Gaming mode optimizations for high-performance real-time screen capture.

This module provides specialized configurations and optimizations for
gaming scenarios requiring high FPS (30-120) with low latency.
"""

import time
import asyncio
import statistics
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class PerformanceMode(Enum):
    """Performance mode presets."""
    QUALITY = "quality"      # 10 FPS, 95% quality, PNG
    BALANCED = "balanced"    # 30 FPS, 75% quality, JPEG
    PERFORMANCE = "performance"  # 60 FPS, 50% quality, JPEG
    EXTREME = "extreme"      # 120 FPS, 30% quality, JPEG


@dataclass
class GameStreamConfig:
    """Configuration for gaming stream."""

    # Performance mode
    mode: PerformanceMode = PerformanceMode.BALANCED

    # Frame rate
    fps: int = 30
    max_fps: int = 120

    # Image quality
    quality: int = 75
    format: str = "jpeg"

    # Caching
    cache_size: int = 60  # Frames to cache
    cache_duration_seconds: int = 2

    # Frame skipping
    enable_frame_skip: bool = True
    max_skip_frames: int = 5
    skip_threshold_ms: float = 50.0  # Skip if behind by this much

    # Region capture
    capture_region_only: bool = False
    window_title: Optional[str] = None

    # Adaptive quality
    adaptive_quality: bool = True
    min_quality: int = 30
    max_quality: int = 95

    # Performance monitoring
    enable_metrics: bool = True
    metrics_window_size: int = 100  # Frames to average

    def __post_init__(self):
        """Apply mode presets if specified."""
        if self.mode == PerformanceMode.QUALITY:
            self.fps = 10
            self.quality = 95
            self.format = "png"
            self.enable_frame_skip = False
            self.adaptive_quality = False

        elif self.mode == PerformanceMode.BALANCED:
            self.fps = 30
            self.quality = 75
            self.format = "jpeg"
            self.enable_frame_skip = True
            self.adaptive_quality = True

        elif self.mode == PerformanceMode.PERFORMANCE:
            self.fps = 60
            self.quality = 50
            self.format = "jpeg"
            self.enable_frame_skip = True
            self.adaptive_quality = True

        elif self.mode == PerformanceMode.EXTREME:
            self.fps = 120
            self.quality = 30
            self.format = "jpeg"
            self.enable_frame_skip = True
            self.adaptive_quality = True
            self.min_quality = 20

        # Calculate cache size based on FPS
        self.cache_size = max(
            self.cache_size,
            self.fps * self.cache_duration_seconds
        )


class FrameMetrics:
    """Performance metrics for gaming streams."""

    def __init__(self, window_size: int = 100):
        self.window_size = window_size

        # Timing data
        self.frame_times: List[float] = []
        self.capture_times: List[float] = []
        self.encode_times: List[float] = []
        self.network_times: List[float] = []

        # Frame statistics
        self.total_frames = 0
        self.dropped_frames = 0
        self.skipped_frames = 0

        # Session timing
        self.session_start = time.time()
        self.last_frame_time = time.time()

    def add_frame(
        self,
        capture_ms: float,
        encode_ms: float,
        network_ms: float,
        dropped: bool = False,
        skipped: bool = False
    ):
        """Record frame metrics."""
        total_ms = capture_ms + encode_ms + network_ms

        # Update timing lists
        self.frame_times.append(total_ms)
        self.capture_times.append(capture_ms)
        self.encode_times.append(encode_ms)
        self.network_times.append(network_ms)

        # Maintain window size
        if len(self.frame_times) > self.window_size:
            self.frame_times.pop(0)
            self.capture_times.pop(0)
            self.encode_times.pop(0)
            self.network_times.pop(0)

        # Update counters
        self.total_frames += 1
        if dropped:
            self.dropped_frames += 1
        if skipped:
            self.skipped_frames += 1

        self.last_frame_time = time.time()

    def get_current_fps(self) -> float:
        """Calculate current FPS based on recent frames."""
        if len(self.frame_times) < 2:
            return 0.0

        # Calculate FPS from frame times
        avg_frame_time_ms = statistics.mean(self.frame_times)
        if avg_frame_time_ms <= 0:
            return 0.0

        return 1000.0 / avg_frame_time_ms

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        if not self.frame_times:
            return {
                "available": False,
                "message": "No frames recorded yet"
            }

        # Calculate percentiles
        try:
            p50 = statistics.median(self.frame_times)
            p95 = statistics.quantiles(self.frame_times, n=20)[18] if len(self.frame_times) >= 20 else p50
            p99 = statistics.quantiles(self.frame_times, n=100)[98] if len(self.frame_times) >= 100 else p95
        except:
            p50 = p95 = p99 = statistics.mean(self.frame_times)

        # Session stats
        session_duration = time.time() - self.session_start
        avg_session_fps = self.total_frames / session_duration if session_duration > 0 else 0

        return {
            "available": True,

            # FPS metrics
            "current_fps": self.get_current_fps(),
            "avg_session_fps": avg_session_fps,

            # Frame time metrics (milliseconds)
            "avg_frame_time_ms": statistics.mean(self.frame_times),
            "min_frame_time_ms": min(self.frame_times),
            "max_frame_time_ms": max(self.frame_times),
            "p50_frame_time_ms": p50,
            "p95_frame_time_ms": p95,
            "p99_frame_time_ms": p99,

            # Component breakdown
            "avg_capture_ms": statistics.mean(self.capture_times),
            "avg_encode_ms": statistics.mean(self.encode_times),
            "avg_network_ms": statistics.mean(self.network_times),

            # Frame statistics
            "total_frames": self.total_frames,
            "dropped_frames": self.dropped_frames,
            "skipped_frames": self.skipped_frames,
            "drop_rate_percent": (self.dropped_frames / self.total_frames * 100) if self.total_frames > 0 else 0,
            "skip_rate_percent": (self.skipped_frames / self.total_frames * 100) if self.total_frames > 0 else 0,

            # Session info
            "session_duration_seconds": session_duration,
            "sample_window_size": len(self.frame_times),
        }


class AdaptiveQualityController:
    """Dynamically adjust image quality based on performance."""

    def __init__(
        self,
        target_fps: int = 60,
        min_quality: int = 30,
        max_quality: int = 95,
        adjustment_interval: int = 10  # Adjust every N frames
    ):
        self.target_fps = target_fps
        self.min_quality = min_quality
        self.max_quality = max_quality
        self.adjustment_interval = adjustment_interval

        self.current_quality = (min_quality + max_quality) // 2
        self.frame_count = 0

    def should_adjust(self) -> bool:
        """Check if it's time to adjust quality."""
        self.frame_count += 1
        return self.frame_count % self.adjustment_interval == 0

    def adjust(self, current_fps: float, cpu_usage: float) -> int:
        """Adjust quality based on current performance.

        Args:
            current_fps: Current frames per second
            cpu_usage: CPU usage percentage (0-100)

        Returns:
            New quality setting
        """
        # FPS significantly below target - reduce quality
        if current_fps < self.target_fps * 0.85:
            self.current_quality = max(
                self.min_quality,
                self.current_quality - 5
            )
            logger.debug(f"FPS low ({current_fps:.1f} < {self.target_fps}), reducing quality to {self.current_quality}")

        # FPS at target and CPU has headroom - increase quality
        elif current_fps >= self.target_fps * 0.95 and cpu_usage < 60:
            self.current_quality = min(
                self.max_quality,
                self.current_quality + 2
            )
            logger.debug(f"FPS good ({current_fps:.1f}), increasing quality to {self.current_quality}")

        # FPS above target but CPU saturated - maintain quality
        elif cpu_usage > 80:
            # Don't increase quality even if FPS is good
            pass

        return self.current_quality


class FrameSkipper:
    """Implements frame skipping to maintain target FPS."""

    def __init__(
        self,
        target_fps: int = 60,
        max_skip: int = 5,
        skip_threshold_ms: float = 50.0
    ):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.max_skip = max_skip
        self.skip_threshold_ms = skip_threshold_ms / 1000.0  # Convert to seconds

        self.last_frame_time = time.time()
        self.consecutive_skips = 0

    def should_skip_frame(self) -> bool:
        """Determine if current frame should be skipped.

        Returns:
            True if frame should be skipped
        """
        current_time = time.time()
        elapsed = current_time - self.last_frame_time

        # Not behind schedule - don't skip
        if elapsed < self.frame_interval + self.skip_threshold_ms:
            self.consecutive_skips = 0
            return False

        # Behind schedule - skip frame to catch up
        if self.consecutive_skips < self.max_skip:
            self.consecutive_skips += 1
            logger.debug(f"Skipping frame (behind by {elapsed*1000:.1f}ms)")
            return True

        # Too many consecutive skips - process this frame
        self.consecutive_skips = 0
        return False

    def mark_frame_processed(self):
        """Mark that a frame was processed."""
        self.last_frame_time = time.time()
        self.consecutive_skips = 0


def calculate_optimal_cache_size(fps: int, buffer_seconds: int = 2) -> int:
    """Calculate optimal cache size for given FPS.

    Args:
        fps: Target frames per second
        buffer_seconds: Desired buffer duration in seconds

    Returns:
        Recommended cache size
    """
    # Minimum: 2 seconds of frames
    min_size = fps * buffer_seconds

    # Maximum: 5 seconds of frames (memory constraint)
    max_size = fps * 5

    # Absolute minimum: 30 frames
    # Absolute maximum: 600 frames (10 seconds @ 60 FPS)
    cache_size = max(30, min(600, min_size))

    return cache_size


def get_game_mode_preset(mode: str) -> GameStreamConfig:
    """Get predefined game mode configuration.

    Args:
        mode: One of "quality", "balanced", "performance", "extreme"

    Returns:
        GameStreamConfig for the specified mode
    """
    mode_enum = PerformanceMode(mode.lower())
    return GameStreamConfig(mode=mode_enum)


# Example usage and testing
if __name__ == "__main__":
    # Test configurations
    print("=== Game Mode Configurations ===\n")

    for mode in PerformanceMode:
        config = GameStreamConfig(mode=mode)
        print(f"{mode.value.upper()} Mode:")
        print(f"  FPS: {config.fps}")
        print(f"  Quality: {config.quality}")
        print(f"  Format: {config.format}")
        print(f"  Cache Size: {config.cache_size} frames")
        print(f"  Frame Skip: {config.enable_frame_skip}")
        print(f"  Adaptive Quality: {config.adaptive_quality}")
        print()

    # Test metrics
    print("=== Testing Metrics ===\n")
    metrics = FrameMetrics(window_size=10)

    for i in range(20):
        metrics.add_frame(
            capture_ms=2.5,
            encode_ms=1.5,
            network_ms=1.0,
            skipped=(i % 10 == 0)  # Skip every 10th frame
        )

    stats = metrics.get_stats()
    print(f"Current FPS: {stats['current_fps']:.1f}")
    print(f"Avg Frame Time: {stats['avg_frame_time_ms']:.2f}ms")
    print(f"Skipped Frames: {stats['skipped_frames']} ({stats['skip_rate_percent']:.1f}%)")
    print()

    # Test adaptive quality
    print("=== Testing Adaptive Quality ===\n")
    controller = AdaptiveQualityController(target_fps=60)

    # Simulate low FPS
    quality = controller.adjust(current_fps=45, cpu_usage=75)
    print(f"Low FPS (45): Quality adjusted to {quality}")

    # Simulate good FPS
    quality = controller.adjust(current_fps=62, cpu_usage=50)
    print(f"Good FPS (62): Quality adjusted to {quality}")
