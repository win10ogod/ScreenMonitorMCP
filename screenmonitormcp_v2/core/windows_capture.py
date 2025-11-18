#!/usr/bin/env python3
"""
Windows-Optimized Screen Capture for ScreenMonitorMCP v2

This module provides high-performance screen capture for Windows using:
1. Windows Graphics Capture (WGC) - Windows 10 1803+ (Most Secure)
2. DXGI Desktop Duplication - Windows 8+ (High Performance)
3. Fallback to MSS for compatibility

Performance Comparison:
- GDI (BitBlt/MSS): ~20-50ms, CPU-based, can't capture hardware-accelerated content
- DXGI: ~1-5ms, GPU-based, excellent for gaming/video
- WGC: ~1-5ms, GPU-based, secure with user authorization

Author: ScreenMonitorMCP Team
Version: 2.5.0
License: MIT
"""

import asyncio
import base64
import io
import logging
import platform
import sys
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from PIL import Image

logger = logging.getLogger(__name__)


class WindowsCaptureBackend:
    """Base class for Windows capture backends."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.backend_name = "base"
        self.is_initialized = False

    def initialize(self) -> bool:
        """Initialize the capture backend."""
        raise NotImplementedError

    def capture(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture screen and return PIL Image."""
        raise NotImplementedError

    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def get_performance_info(self) -> Dict[str, Any]:
        """Get backend performance information."""
        return {
            "backend": self.backend_name,
            "initialized": self.is_initialized
        }


class DXGICaptureBackend(WindowsCaptureBackend):
    """DXGI Desktop Duplication backend (Windows 8+).

    High-performance GPU-based capture using DirectX Graphics Infrastructure.
    Uses dxcam library for production-ready DXGI Desktop Duplication API access.

    Performance: ~1-5ms per capture (240+ FPS capable)
    Pros: Excellent performance, captures hardware-accelerated content, multi-monitor support
    Cons: Windows 8+ only, requires dxcam library
    """

    def __init__(self):
        super().__init__()
        self.backend_name = "DXGI Desktop Duplication"
        self._dxgi_available = False
        self._cameras = {}  # Dict[int, dxcam.DXCamera]
        self._device_info = None
        self._output_info = None
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if DXGI capture is available."""
        if platform.system() != "Windows":
            return

        try:
            # Check for dxcam library (high-performance DXGI wrapper)
            import dxcam

            # Get device and output information
            self._device_info = dxcam.device_info()
            self._output_info = dxcam.output_info()

            self._dxgi_available = True
            logger.info(f"DXGI Desktop Duplication available (via dxcam)")
            logger.info(f"Available GPUs: {len(self._device_info) if self._device_info else 0}")
            logger.info(f"Available outputs: {len(self._output_info) if self._output_info else 0}")
        except ImportError:
            logger.info("DXGI unavailable: Install with 'pip install dxcam'")
            logger.info("dxcam provides ultra-fast DXGI screen capture (1-5ms, 240+ FPS)")
        except Exception as e:
            logger.warning(f"DXGI availability check failed: {e}")

    def initialize(self) -> bool:
        """Initialize DXGI capture using dxcam.

        Creates camera instances for available monitors with intelligent defaults.
        """
        if not self._dxgi_available:
            return False

        try:
            import dxcam

            # Create camera for primary monitor (output_idx=0)
            # Using RGB color format for PIL compatibility
            primary_camera = dxcam.create(
                device_idx=0,      # Primary GPU
                output_idx=0,      # Primary monitor
                output_color="RGB", # RGB for PIL Image
                max_buffer_len=2   # Small buffer for low latency
            )

            if primary_camera is None:
                logger.error("Failed to create dxcam camera for primary monitor")
                return False

            self._cameras[0] = primary_camera
            logger.info(f"DXGI initialized successfully via dxcam (primary monitor)")
            self.is_initialized = True
            return True

        except Exception as e:
            logger.error(f"DXGI initialization failed: {e}")
            logger.info("DXGI requires DirectX-compatible GPU - falling back to MSS")
            return False

    def _ensure_camera(self, monitor: int) -> bool:
        """Ensure camera exists for specified monitor.

        Args:
            monitor: Monitor index

        Returns:
            True if camera is available, False otherwise
        """
        if monitor in self._cameras:
            return True

        if not self._dxgi_available:
            return False

        try:
            import dxcam

            # Create camera for this monitor
            camera = dxcam.create(
                device_idx=0,
                output_idx=monitor,
                output_color="RGB",
                max_buffer_len=2
            )

            if camera is None:
                logger.warning(f"Could not create camera for monitor {monitor}")
                return False

            self._cameras[monitor] = camera
            logger.info(f"Created DXGI camera for monitor {monitor}")
            return True

        except Exception as e:
            logger.error(f"Failed to create camera for monitor {monitor}: {e}")
            return False

    def capture(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture using DXGI via dxcam.

        Args:
            monitor: Monitor index (0 for primary display)

        Returns:
            PIL Image or None if capture fails
        """
        if not self.is_initialized:
            return None

        # Ensure camera exists for this monitor
        if not self._ensure_camera(monitor):
            logger.debug(f"No camera available for monitor {monitor}")
            return None

        try:
            camera = self._cameras[monitor]

            # Capture frame using dxcam (extremely fast, 1-5ms)
            # Returns None if no new frame since last call
            frame = camera.grab()

            if frame is None:
                # No new frame available - try one more time
                # This can happen on first call or if display is off
                import time
                time.sleep(0.001)  # 1ms delay
                frame = camera.grab()

                if frame is None:
                    logger.debug(f"DXGI capture returned None for monitor {monitor}")
                    return None

            # Convert numpy array to PIL Image
            # dxcam returns RGB numpy array in shape (H, W, 3)
            import numpy as np
            if isinstance(frame, np.ndarray):
                # Ensure correct format
                if frame.ndim == 3 and frame.shape[2] == 3:
                    image = Image.fromarray(frame, mode='RGB')
                    return image
                else:
                    logger.warning(f"Unexpected frame shape from dxcam: {frame.shape}")
                    return None
            else:
                logger.warning(f"Unexpected frame type from dxcam: {type(frame)}")
                return None

        except Exception as e:
            logger.error(f"DXGI capture failed for monitor {monitor}: {e}")
            return None

    def get_monitor_count(self) -> int:
        """Get number of available monitors."""
        if self._output_info:
            return len(self._output_info)
        return 1

    def get_performance_info(self) -> Dict[str, Any]:
        """Get backend performance information."""
        info = {
            "backend": self.backend_name,
            "initialized": self.is_initialized,
            "active_cameras": len(self._cameras),
            "available_monitors": self.get_monitor_count()
        }

        if self._device_info:
            info["gpu_devices"] = len(self._device_info)

        return info

    def cleanup(self) -> None:
        """Cleanup DXGI resources."""
        for monitor_id, camera in self._cameras.items():
            try:
                logger.debug(f"Releasing DXGI camera for monitor {monitor_id}")
                camera.release()
            except Exception as e:
                logger.error(f"Failed to release camera for monitor {monitor_id}: {e}")

        self._cameras.clear()
        self.is_initialized = False


class WGCCaptureBackend(WindowsCaptureBackend):
    """Windows Graphics Capture backend (Windows 10 1803+).

    Modern, secure GPU-based capture using Windows Runtime APIs.
    Uses winsdk for Windows Graphics Capture API access (optional dependency).

    Performance: ~1-5ms per capture
    Pros: Modern API, secure capture, excellent quality, window-specific capture
    Cons: Windows 10 1803+ only, requires winsdk package, async-based
    """

    def __init__(self):
        super().__init__()
        self.backend_name = "Windows Graphics Capture"
        self._wgc_available = False
        self._direct3d_device = None
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if WGC is available."""
        if platform.system() != "Windows":
            return

        try:
            # Check Windows version (need 10.0.17134 or higher for WGC)
            import sys
            if sys.getwindowsversion().build >= 17134:
                # Try importing winsdk (modern WinRT bindings)
                try:
                    from winsdk.windows.graphics.capture import Direct3D11CaptureFramePool
                    from winsdk.windows.graphics.capture.interop import create_for_monitor
                    self._wgc_available = True
                    logger.info("Windows Graphics Capture available (via winsdk)")
                except ImportError as e:
                    # winsdk not available or has missing dependencies
                    logger.debug(f"WGC winsdk import failed: {e}")
                    # Fallback to try winrt
                    try:
                        from winrt.windows.graphics.capture import Direct3D11CaptureFramePool
                        self._wgc_available = True
                        logger.info("Windows Graphics Capture available (via winrt)")
                    except ImportError:
                        logger.debug("WGC unavailable: Install with 'pip install winsdk' or 'pip install winrt-Windows.Graphics.Capture'")
                except Exception as e:
                    # Catch any other errors during import (like System.Runtime.WindowsRuntime missing)
                    logger.debug(f"WGC check failed: {e}")
                    self._wgc_available = False
            else:
                logger.debug(f"WGC unavailable: Windows build {sys.getwindowsversion().build} < 17134 (need 1803+)")
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"WGC availability check failed: {e}")
            self._wgc_available = False

    def initialize(self) -> bool:
        """Initialize WGC capture using Windows Runtime APIs."""
        if not self._wgc_available:
            logger.debug("WGC not available - skipping initialization")
            return False

        try:
            # Import helper function to create Direct3D device
            self._direct3d_device = self._create_direct3d_device()

            if self._direct3d_device is None:
                logger.debug("Failed to create Direct3D device for WGC - this is optional")
                return False

            logger.info("WGC initialized successfully with Direct3D device")
            self.is_initialized = True
            return True

        except Exception as e:
            logger.debug(f"WGC initialization failed (optional feature): {e}")
            return False

    def _create_direct3d_device(self):
        """Create Direct3D device for WGC.

        This is a helper function to create the required Direct3D device.
        """
        try:
            # Try winsdk first
            try:
                from winsdk.windows.graphics.directx.direct3d11 import IDirect3DDevice
                from winsdk.windows.graphics.capture import Direct3D11CaptureFramePool
                import ctypes
                from ctypes import wintypes

                # Create D3D11 device using ctypes
                d3d11 = ctypes.windll.d3d11
                dxgi = ctypes.windll.dxgi

                D3D_DRIVER_TYPE_HARDWARE = 1
                D3D11_CREATE_DEVICE_BGRA_SUPPORT = 0x20
                D3D11_SDK_VERSION = 7

                device = ctypes.c_void_p()
                feature_level = ctypes.c_uint()
                context = ctypes.c_void_p()

                hr = d3d11.D3D11CreateDevice(
                    None,  # pAdapter
                    D3D_DRIVER_TYPE_HARDWARE,
                    None,  # Software
                    D3D11_CREATE_DEVICE_BGRA_SUPPORT,
                    None,  # pFeatureLevels
                    0,  # FeatureLevels
                    D3D11_SDK_VERSION,
                    ctypes.byref(device),
                    ctypes.byref(feature_level),
                    ctypes.byref(context)
                )

                if hr == 0 and device.value:
                    # Wrap native D3D device
                    # This is a simplified version - full implementation would properly wrap the device
                    return device
                else:
                    logger.debug(f"D3D11CreateDevice failed with HRESULT: {hr}")
                    return None

            except (ImportError, Exception) as e:
                # winsdk not available or import failed
                logger.debug(f"winsdk D3D device creation failed: {e}")
                # Try winrt fallback
                try:
                    from winrt.windows.graphics.directx.direct3d11 import IDirect3DDevice
                    # Similar implementation for winrt
                    logger.debug("Using winrt package - winsdk recommended for better compatibility")
                    return None
                except (ImportError, Exception):
                    return None

        except Exception as e:
            logger.debug(f"Failed to create Direct3D device (optional feature): {e}")
            return None

    def capture(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture using WGC async APIs.

        Args:
            monitor: Monitor index (0 for primary display)

        Returns:
            PIL Image or None if capture fails

        Note: This implementation uses async/await for WGC APIs.
        """
        if not self.is_initialized:
            return None

        try:
            # WGC requires async execution
            # We need to run async capture in sync context
            loop = None
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run async capture
            if loop.is_running():
                # If loop is already running, we can't use run_until_complete
                # This happens in some contexts (like Jupyter)
                logger.warning("Event loop already running - WGC capture may not work correctly")
                return None
            else:
                return loop.run_until_complete(self._capture_async(monitor))

        except Exception as e:
            logger.error(f"WGC capture failed: {e}")
            return None

    async def _capture_async(self, monitor: int = 0) -> Optional[Image.Image]:
        """Async implementation of WGC capture.

        This is the core async capture implementation using WGC APIs.
        """
        try:
            # Try winsdk implementation
            try:
                from winsdk.windows.graphics.capture.interop import create_for_monitor
                from winsdk.windows.graphics.capture import Direct3D11CaptureFramePool, Direct3D11CaptureFrame
                from winsdk.windows.graphics.directx import DirectXPixelFormat
                from winsdk.windows.graphics.imaging import SoftwareBitmap, BitmapBufferAccessMode
                from winsdk.system import Object
                import ctypes
                from ctypes import wintypes
                import numpy as np

                # Get monitor HMONITOR handle
                # For primary monitor (monitor 0), use MonitorFromPoint
                user32 = ctypes.windll.user32
                if monitor == 0:
                    hmonitor = user32.MonitorFromPoint(ctypes.wintypes.POINT(0, 0), 2)  # MONITOR_DEFAULTTOPRIMARY
                else:
                    # For other monitors, would need to enumerate
                    logger.warning(f"WGC multi-monitor support requires monitor enumeration - using primary")
                    hmonitor = user32.MonitorFromPoint(ctypes.wintypes.POINT(0, 0), 2)

                # Create GraphicsCaptureItem for monitor
                item = create_for_monitor(hmonitor)

                if item is None:
                    logger.error("Failed to create GraphicsCaptureItem for monitor")
                    return None

                # Create event loop for async operations
                event_loop = asyncio.get_running_loop()
                future = event_loop.create_future()

                # Create frame pool
                frame_pool = Direct3D11CaptureFramePool.create_free_threaded(
                    self._direct3d_device,
                    DirectXPixelFormat.B8_G8_R8_A8_UINT_NORMALIZED,
                    1,
                    item.size
                )

                # Create capture session
                session = frame_pool.create_capture_session(item)
                session.is_border_required = False
                session.is_cursor_capture_enabled = False

                # Frame arrival callback
                def frame_arrived(pool: Direct3D11CaptureFramePool, args: Object):
                    try:
                        frame: Direct3D11CaptureFrame = pool.try_get_next_frame()
                        if frame and not future.done():
                            future.set_result(frame)
                        session.close()
                    except Exception as e:
                        if not future.done():
                            future.set_exception(e)

                # Register callback
                frame_pool.add_frame_arrived(
                    lambda fp, o: event_loop.call_soon_threadsafe(frame_arrived, fp, o)
                )

                # Start capture
                session.start_capture()

                # Wait for frame (with timeout)
                try:
                    frame = await asyncio.wait_for(future, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error("WGC frame capture timed out")
                    session.close()
                    return None

                # Convert frame to software bitmap
                software_bitmap = await SoftwareBitmap.create_copy_from_surface_async(frame.surface)

                # Lock buffer and convert to numpy array
                buffer = software_bitmap.lock_buffer(BitmapBufferAccessMode.READ_WRITE)
                image_data = np.frombuffer(buffer.create_reference(), dtype=np.uint8)
                image_data.shape = (item.size.height, item.size.width, 4)  # BGRA format

                # Convert BGRA to RGB
                image_rgb = image_data[:, :, [2, 1, 0]]  # BGR -> RGB (skip alpha)

                # Convert to PIL Image
                image = Image.fromarray(image_rgb, mode='RGB')

                return image

            except ImportError:
                logger.debug("winsdk package not available - WGC capture requires winsdk")
                return None

        except Exception as e:
            logger.debug(f"WGC async capture failed (optional feature): {e}")
            import traceback
            logger.debug(f"WGC capture traceback: {traceback.format_exc()}")
            return None

    def get_performance_info(self) -> Dict[str, Any]:
        """Get backend performance information."""
        return {
            "backend": self.backend_name,
            "initialized": self.is_initialized,
            "requires_async": True,
            "d3d_device_available": self._direct3d_device is not None
        }

    def cleanup(self) -> None:
        """Cleanup WGC resources."""
        # Direct3D device cleanup
        if self._direct3d_device:
            try:
                # Release D3D device
                self._direct3d_device = None
            except Exception as e:
                logger.error(f"Failed to cleanup D3D device: {e}")

        self.is_initialized = False


class OptimizedWindowsCapture:
    """
    Optimized Windows capture manager with automatic backend selection.

    Backend Priority:
    1. WGC (Windows Graphics Capture) - Most secure, Windows 10 1803+
    2. DXGI (Desktop Duplication) - High performance, Windows 8+
    3. MSS (Fallback) - Cross-platform compatible

    Usage:
        capture = OptimizedWindowsCapture()
        image = await capture.capture_optimized(monitor=0)
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.backends: Dict[str, WindowsCaptureBackend] = {}
        self.active_backend: Optional[str] = None
        self._initialize_backends()

    def _initialize_backends(self) -> None:
        """Initialize available Windows capture backends."""
        if platform.system() != "Windows":
            logger.info("Not on Windows - Windows optimization unavailable")
            return

        # Try to initialize backends in priority order
        backends_to_try = [
            ("wgc", WGCCaptureBackend),
            ("dxgi", DXGICaptureBackend)
        ]

        for backend_name, backend_class in backends_to_try:
            try:
                backend = backend_class()
                if backend.initialize():
                    self.backends[backend_name] = backend
                    if not self.active_backend:
                        self.active_backend = backend_name
                    logger.info(f"Initialized {backend.backend_name}")
            except Exception as e:
                logger.debug(f"Failed to initialize {backend_name}: {e}")

        if self.active_backend:
            logger.info(f"Active backend: {self.backends[self.active_backend].backend_name}")
        else:
            logger.info("No Windows optimization backends available - using MSS fallback")

    async def capture_optimized(self, monitor: int = 0) -> Optional[Image.Image]:
        """
        Capture using the best available backend.

        Args:
            monitor: Monitor number to capture

        Returns:
            PIL Image or None if capture fails
        """
        if not self.active_backend or not self.backends:
            return None

        try:
            backend = self.backends[self.active_backend]
            loop = asyncio.get_event_loop()
            image = await loop.run_in_executor(None, backend.capture, monitor)
            return image
        except Exception as e:
            logger.error(f"Optimized capture failed: {e}")
            return None

    def get_backend_info(self) -> Dict[str, Any]:
        """Get information about available backends."""
        return {
            "platform": platform.system(),
            "active_backend": self.active_backend,
            "available_backends": list(self.backends.keys()),
            "backend_details": {
                name: backend.get_performance_info()
                for name, backend in self.backends.items()
            },
            "optimization_available": bool(self.active_backend),
            "recommendations": self._get_recommendations()
        }

    def _get_recommendations(self) -> Dict[str, str]:
        """Get recommendations for enabling Windows optimization."""
        if platform.system() != "Windows":
            return {"message": "Windows optimization only available on Windows"}

        if self.active_backend:
            return {"message": f"Using optimized backend: {self.active_backend}"}

        # Provide installation instructions
        recommendations = {
            "message": "Windows optimization not available - using MSS fallback",
            "wgc_install": "pip install pythonnet (for Windows Graphics Capture)",
            "dxgi_install": "pip install comtypes pywin32 (for DXGI Desktop Duplication)",
            "benefits": "2-10x faster capture, GPU-accelerated, better for gaming/video"
        }

        return recommendations

    def cleanup(self) -> None:
        """Cleanup all backends."""
        for backend in self.backends.values():
            try:
                backend.cleanup()
            except Exception as e:
                logger.error(f"Backend cleanup error: {e}")


# Singleton instance for optional Windows optimization
_windows_capture_instance: Optional[OptimizedWindowsCapture] = None


def get_windows_capture() -> Optional[OptimizedWindowsCapture]:
    """Get or create Windows capture instance."""
    global _windows_capture_instance

    if platform.system() != "Windows":
        return None

    if _windows_capture_instance is None:
        _windows_capture_instance = OptimizedWindowsCapture()

    return _windows_capture_instance


def is_windows_optimization_available() -> bool:
    """Check if Windows optimization is available."""
    if platform.system() != "Windows":
        return False

    capture = get_windows_capture()
    return capture is not None and capture.active_backend is not None
