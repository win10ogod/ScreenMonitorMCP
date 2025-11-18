#!/usr/bin/env python3
"""
Screen Capture Module for ScreenMonitorMCP v2

This module provides optimized screen capture functionality with platform-specific optimizations.
- Windows: Optional WGC/DXGI GPU-accelerated capture
- Cross-platform: MSS library fallback

Author: ScreenMonitorMCP Team
Version: 2.5.0
License: MIT
"""

import asyncio
import base64
import io
import logging
import platform
import time
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from functools import lru_cache

import mss
from PIL import Image

logger = logging.getLogger(__name__)

# Optional Windows optimization
try:
    from .windows_capture import get_windows_capture, is_windows_optimization_available
    WINDOWS_OPT_AVAILABLE = platform.system() == "Windows"
except ImportError:
    WINDOWS_OPT_AVAILABLE = False
    get_windows_capture = None
    is_windows_optimization_available = lambda: False


class ScreenCapture:
    """Optimized screen capture functionality using mss library with optional Windows optimization."""

    def __init__(self):
        """Initialize the screen capture system with performance optimizations."""
        self.logger = logging.getLogger(__name__)
        self._capture_cache = {}
        self._cache_ttl = timedelta(milliseconds=100)  # 100ms cache
        self._performance_stats = {
            "total_captures": 0,
            "cache_hits": 0,
            "avg_capture_time_ms": 0.0,
            "windows_opt_captures": 0,
            "mss_captures": 0
        }

        # Initialize Windows optimization if available
        self._windows_capture = None
        if WINDOWS_OPT_AVAILABLE:
            try:
                self._windows_capture = get_windows_capture()
                if self._windows_capture and self._windows_capture.active_backend:
                    self.logger.info(
                        f"Windows optimization enabled: {self._windows_capture.active_backend}"
                    )
                else:
                    self.logger.info("Windows optimization available but no backends active")
            except Exception as e:
                self.logger.warning(f"Windows optimization initialization failed: {e}")
                self._windows_capture = None
    
    async def capture_screen(self, monitor: int = 0, region: Optional[Dict[str, int]] = None,
                           format: str = "png", use_cache: bool = True) -> Dict[str, Any]:
        """Capture screen and return image data with performance optimizations.

        Args:
            monitor: Monitor number to capture (0 for primary)
            region: Optional region dict with x, y, width, height
            format: Image format (png, jpeg)
            use_cache: Whether to use cache for repeated captures

        Returns:
            Dict containing success status and image_data as base64 string
        """
        try:
            start_time = time.perf_counter()

            # Check cache if enabled
            cache_key = None
            if use_cache:
                cache_key = f"{monitor}_{region}_{format}"
                cached = self._get_from_cache(cache_key)
                if cached:
                    self._performance_stats["cache_hits"] += 1
                    return cached

            # Run capture in executor to avoid blocking
            loop = asyncio.get_event_loop()
            image_bytes = await loop.run_in_executor(
                None, self._capture_screen_sync, monitor, region, format
            )

            # Convert to base64 for MCP compatibility
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            result = {
                "success": True,
                "image_data": image_base64,
                "format": format,
                "size": len(image_bytes)
            }

            # Update cache if enabled
            if use_cache and cache_key:
                self._add_to_cache(cache_key, result)

            # Update performance stats
            capture_time_ms = (time.perf_counter() - start_time) * 1000
            self._update_performance_stats(capture_time_ms)

            return result
        except Exception as e:
            self.logger.error(f"Screen capture failed: {e}")
            return {
                "success": False,
                "message": str(e),
                "image_data": None
            }

    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached capture if not expired."""
        if key in self._capture_cache:
            cached_time, cached_data = self._capture_cache[key]
            if datetime.now() - cached_time < self._cache_ttl:
                return cached_data
            else:
                del self._capture_cache[key]
        return None

    def _add_to_cache(self, key: str, data: Dict[str, Any]) -> None:
        """Add capture to cache with timestamp."""
        self._capture_cache[key] = (datetime.now(), data)
        # Clean old cache entries (simple cleanup)
        if len(self._capture_cache) > 10:
            oldest_key = min(self._capture_cache.keys(),
                           key=lambda k: self._capture_cache[k][0])
            del self._capture_cache[oldest_key]

    def _update_performance_stats(self, capture_time_ms: float) -> None:
        """Update performance statistics."""
        self._performance_stats["total_captures"] += 1
        total = self._performance_stats["total_captures"]
        current_avg = self._performance_stats["avg_capture_time_ms"]
        # Running average
        self._performance_stats["avg_capture_time_ms"] = (
            (current_avg * (total - 1) + capture_time_ms) / total
        )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get capture performance statistics."""
        cache_hit_rate = 0.0
        if self._performance_stats["total_captures"] > 0:
            cache_hit_rate = (self._performance_stats["cache_hits"] /
                            self._performance_stats["total_captures"]) * 100

        # Calculate backend usage percentages
        windows_opt_percent = 0.0
        mss_percent = 0.0
        total_backend_captures = (self._performance_stats["windows_opt_captures"] +
                                 self._performance_stats["mss_captures"])
        if total_backend_captures > 0:
            windows_opt_percent = (self._performance_stats["windows_opt_captures"] /
                                  total_backend_captures) * 100
            mss_percent = (self._performance_stats["mss_captures"] /
                          total_backend_captures) * 100

        return {
            **self._performance_stats,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "cache_size": len(self._capture_cache),
            "windows_opt_usage_percent": round(windows_opt_percent, 2),
            "mss_usage_percent": round(mss_percent, 2)
        }

    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about the active capture backend and available optimizations."""
        backend_info = {
            "platform": platform.system(),
            "active_backend": "mss",
            "windows_optimization_available": WINDOWS_OPT_AVAILABLE,
            "windows_optimization_active": False,
            "backend_details": None,
            "recommendations": {}
        }

        if self._windows_capture:
            windows_info = self._windows_capture.get_backend_info()
            backend_info.update({
                "windows_optimization_active": bool(self._windows_capture.active_backend),
                "active_backend": self._windows_capture.active_backend or "mss",
                "backend_details": windows_info,
                "recommendations": windows_info.get("recommendations", {})
            })
        elif WINDOWS_OPT_AVAILABLE:
            backend_info["recommendations"] = {
                "message": "Windows optimization available but not initialized",
                "suggestion": "Restart the application to enable Windows optimization"
            }
        elif platform.system() == "Windows":
            backend_info["recommendations"] = {
                "message": "Windows optimization not available - using MSS fallback",
                "wgc_install": "pip install pythonnet (for Windows Graphics Capture)",
                "dxgi_install": "pip install comtypes pywin32 (for DXGI Desktop Duplication)",
                "benefits": "2-10x faster capture, GPU-accelerated, better for gaming/video"
            }
        else:
            backend_info["recommendations"] = {
                "message": "Using MSS (cross-platform capture) - optimal for this platform"
            }

        return backend_info
    
    async def capture_screen_raw(self, monitor: int = 0, region: Optional[Dict[str, int]] = None, 
                               format: str = "png") -> bytes:
        """Capture screen and return raw image bytes (for backward compatibility).
        
        Args:
            monitor: Monitor number to capture (0 for primary)
            region: Optional region dict with x, y, width, height
            format: Image format (png, jpeg)
            
        Returns:
            Image data as bytes
        """
        try:
            # Run capture in executor to avoid blocking
            loop = asyncio.get_event_loop()
            image_data = await loop.run_in_executor(
                None, self._capture_screen_sync, monitor, region, format
            )
            return image_data
        except Exception as e:
            self.logger.error(f"Screen capture failed: {e}")
            raise

    def _capture_screen_sync(self, monitor: int, region: Optional[Dict[str, int]],
                           format: str) -> bytes:
        """Synchronous screen capture implementation with Windows optimization."""

        # Try Windows optimization first (if available and no region specified)
        # Region-based capture not yet supported for Windows optimization
        if self._windows_capture and not region:
            try:
                # Attempt optimized Windows capture
                img = asyncio.run(self._windows_capture.capture_optimized(monitor))
                if img:
                    self._performance_stats["windows_opt_captures"] += 1

                    # Convert PIL Image to bytes with optimized compression
                    img_bytes = io.BytesIO()
                    if format.lower() == "jpeg":
                        img.save(img_bytes, format="JPEG", quality=75, optimize=True)
                    else:
                        img.save(img_bytes, format="PNG", compress_level=6, optimize=True)

                    return img_bytes.getvalue()
            except Exception as e:
                self.logger.debug(f"Windows optimization failed, falling back to MSS: {e}")

        # Fallback to MSS (cross-platform)
        self._performance_stats["mss_captures"] += 1

        with mss.mss() as sct:
            # Get monitor info
            if monitor >= len(sct.monitors):
                raise ValueError(f"Monitor {monitor} not found. Available: {len(sct.monitors) - 1}")

            # Use specific region or full monitor
            if region:
                capture_area = {
                    "left": region["x"],
                    "top": region["y"],
                    "width": region["width"],
                    "height": region["height"]
                }
            else:
                capture_area = sct.monitors[monitor]

            # Capture screenshot
            screenshot = sct.grab(capture_area)

            # Convert to PIL Image - handle different pixel formats safely
            try:
                img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            except Exception:
                # Fallback to RGBA format if BGRX fails
                img = Image.frombytes("RGBA", screenshot.size, screenshot.bgra, "raw", "BGRA")
                img = img.convert("RGB")

            # Save to bytes with optimized compression
            img_bytes = io.BytesIO()
            if format.lower() == "jpeg":
                # Optimized JPEG: quality=75 provides good balance
                img.save(img_bytes, format="JPEG", quality=75, optimize=True)
            else:
                # Optimized PNG: compress_level=6 is faster than default 9
                img.save(img_bytes, format="PNG", compress_level=6, optimize=True)

            return img_bytes.getvalue()
    
    async def get_monitors(self) -> list[Dict[str, Any]]:
        """Get information about available monitors."""
        try:
            loop = asyncio.get_event_loop()
            monitors = await loop.run_in_executor(None, self._get_monitors_sync)
            return monitors
        except Exception as e:
            self.logger.error(f"Failed to get monitors: {e}")
            raise
    
    def _get_monitors_sync(self) -> list[Dict[str, Any]]:
        """Synchronous monitor detection."""
        with mss.mss() as sct:
            monitors = []
            for i, monitor in enumerate(sct.monitors):
                monitors.append({
                    "id": i,
                    "left": monitor["left"],
                    "top": monitor["top"],
                    "width": monitor["width"],
                    "height": monitor["height"],
                    "is_primary": i == 0
                })
            return monitors
    
    async def capture_hq_frame(self, format: str = "png") -> Dict[str, Any]:
        """Capture high-quality frame for PNG high-quality captures.
        
        Args:
            format: Image format (png for high quality, jpeg also supported)
            
        Returns:
            Dict containing success status, image_bytes, dimensions, file_size, and format
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._capture_hq_frame_sync, format
            )
            return result
        except Exception as e:
            self.logger.error(f"HQ frame capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _capture_hq_frame_sync(self, format: str) -> Dict[str, Any]:
        """Synchronous high-quality frame capture implementation."""
        try:
            with mss.mss() as sct:
                # Capture primary monitor (monitor 0)
                monitor = sct.monitors[0]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image - handle different pixel formats safely
                try:
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                except Exception:
                    # Fallback to RGBA format if BGRX fails
                    img = Image.frombytes("RGBA", screenshot.size, screenshot.bgra, "raw", "BGRA")
                    img = img.convert("RGB")
                
                # Save to bytes with high quality
                img_buffer = io.BytesIO()
                if format.lower() == "jpeg":
                    img.save(img_buffer, format="JPEG", quality=95, optimize=True)
                else:
                    img.save(img_buffer, format="PNG", optimize=True)
                
                image_bytes = img_buffer.getvalue()
                
                return {
                    "success": True,
                    "image_bytes": image_bytes,
                    "width": img.width,
                    "height": img.height,
                    "file_size": len(image_bytes),
                    "format": format.lower()
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def capture_preview_frame(self, quality: int = 40, resolution: Optional[Tuple[int, int]] = None) -> Dict[str, Any]:
        """Capture low-quality preview frame for JPEG low-quality captures.
        
        Args:
            quality: JPEG quality (1-100, default 40 for low quality)
            resolution: Optional tuple (width, height) for resizing
            
        Returns:
            Dict containing success status, image_bytes, dimensions, file_size, and format
        """
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, self._capture_preview_frame_sync, quality, resolution
            )
            return result
        except Exception as e:
            self.logger.error(f"Preview frame capture failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _capture_preview_frame_sync(self, quality: int, resolution: Optional[Tuple[int, int]]) -> Dict[str, Any]:
        """Synchronous preview frame capture implementation."""
        try:
            with mss.mss() as sct:
                # Capture primary monitor (monitor 0)
                monitor = sct.monitors[0]  # Primary monitor
                screenshot = sct.grab(monitor)
                
                # Convert to PIL Image - handle different pixel formats safely
                try:
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                except Exception:
                    # Fallback to RGBA format if BGRX fails
                    img = Image.frombytes("RGBA", screenshot.size, screenshot.bgra, "raw", "BGRA")
                    img = img.convert("RGB")
                
                # Resize if resolution specified
                if resolution:
                    img = img.resize(resolution, Image.Resampling.LANCZOS)
                
                # Save to bytes with specified quality (JPEG for preview)
                img_buffer = io.BytesIO()
                img.save(img_buffer, format="JPEG", quality=quality, optimize=True)
                image_bytes = img_buffer.getvalue()
                
                return {
                    "success": True,
                    "image_bytes": image_bytes,
                    "width": img.width,
                    "height": img.height,
                    "file_size": len(image_bytes),
                    "format": "jpeg"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def is_available(self) -> bool:
        """Check if screen capture is available."""
        try:
            with mss.mss() as sct:
                return len(sct.monitors) > 0
        except Exception:
            return False