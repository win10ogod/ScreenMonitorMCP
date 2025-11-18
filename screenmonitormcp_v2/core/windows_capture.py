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
    Uses dxcam library for simplified DXGI access (optional dependency).

    Performance: ~1-5ms per capture
    Pros: Excellent performance, captures hardware-accelerated content
    Cons: Windows 8+ only, requires dxcam library
    """

    def __init__(self):
        super().__init__()
        self.backend_name = "DXGI Desktop Duplication"
        self._dxgi_available = False
        self._camera = None
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if DXGI capture is available."""
        if platform.system() != "Windows":
            return

        try:
            # Check for dxcam library (high-performance DXGI wrapper)
            import dxcam
            self._dxgi_available = True
            logger.info("DXGI Desktop Duplication available (via dxcam)")
        except ImportError:
            logger.info("DXGI unavailable: Install with 'pip install dxcam'")
            logger.info("dxcam provides ultra-fast DXGI screen capture (1-5ms)")

    def initialize(self) -> bool:
        """Initialize DXGI capture using dxcam."""
        if not self._dxgi_available:
            return False

        try:
            import dxcam

            # Create camera instance for screen capture
            # dxcam automatically handles all DirectX setup
            self._camera = dxcam.create(output_idx=0, output_color="RGB")

            if self._camera is None:
                logger.error("Failed to create dxcam camera instance")
                return False

            logger.info("DXGI initialized successfully via dxcam")
            self.is_initialized = True
            return True

        except Exception as e:
            logger.error(f"DXGI initialization failed: {e}")
            logger.info("DXGI requires DirectX-compatible GPU - falling back to MSS")
            return False

    def capture(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture using DXGI via dxcam.

        Args:
            monitor: Monitor index (0 for primary display)

        Returns:
            PIL Image or None if capture fails
        """
        if not self.is_initialized or self._camera is None:
            return None

        try:
            # Capture frame using dxcam (extremely fast, 1-5ms)
            frame = self._camera.grab()

            if frame is None:
                logger.debug("DXGI capture returned None (display may be off)")
                return None

            # Convert numpy array to PIL Image
            # dxcam returns RGB numpy array
            import numpy as np
            if isinstance(frame, np.ndarray):
                image = Image.fromarray(frame, mode='RGB')
                return image
            else:
                logger.warning(f"Unexpected frame type from dxcam: {type(frame)}")
                return None

        except Exception as e:
            logger.error(f"DXGI capture failed: {e}")
            return None

    def cleanup(self) -> None:
        """Cleanup DXGI resources."""
        if self._camera:
            try:
                # Release dxcam camera
                self._camera.release()
                self._camera = None
            except Exception as e:
                logger.error(f"Failed to release dxcam camera: {e}")

        self.is_initialized = False


class WGCCaptureBackend(WindowsCaptureBackend):
    """Windows Graphics Capture backend (Windows 10 1803+).

    Modern, secure GPU-based capture with user authorization.
    Uses pythonnet to access Windows Runtime APIs (optional dependency).

    Performance: ~1-5ms per capture
    Pros: Secure (user must authorize), modern API, excellent for specific windows
    Cons: Requires user interaction for authorization, Windows 10 1803+ only
    """

    def __init__(self):
        super().__init__()
        self.backend_name = "Windows Graphics Capture"
        self._wgc_available = False
        self._capture_session = None
        self._frame_pool = None
        self._latest_frame = None
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if WGC is available."""
        if platform.system() != "Windows":
            return

        try:
            # Check Windows version (need 10.0.17134 or higher for WGC)
            import sys
            if sys.getwindowsversion().build >= 17134:
                # Check for pythonnet
                import clr
                self._wgc_available = True
                logger.info("Windows Graphics Capture available")
            else:
                logger.info(f"WGC unavailable: Windows build {sys.getwindowsversion().build} < 17134 (need 1803+)")
        except (ImportError, AttributeError) as e:
            logger.info("WGC unavailable: Install with 'pip install pythonnet'")
            logger.debug(f"WGC check error: {e}")

    def initialize(self) -> bool:
        """Initialize WGC capture using Windows Runtime APIs."""
        if not self._wgc_available:
            return False

        try:
            import clr
            import System
            from System import Array, Byte, IntPtr
            from System.Runtime.InteropServices import Marshal

            # Load Windows Runtime assemblies
            clr.AddReference("System.Runtime.WindowsRuntime")
            from System.Runtime.WindowsRuntime import WindowsRuntimeSystemExtensions

            # Import Windows.Graphics.Capture namespace
            import Windows.Graphics.Capture as WGC
            import Windows.Graphics.DirectX as DirectX
            import Windows.Graphics.DirectX.Direct3D11 as D3D11

            # Note: Full WGC implementation requires:
            # 1. Creating GraphicsCaptureItem for the display/window
            # 2. Creating Direct3D11CaptureFramePool
            # 3. Creating GraphicsCaptureSession
            # 4. Handling frame arrival events
            # 5. Converting Direct3D surface to bitmap

            # This is complex because it requires:
            # - COM interop for Direct3D device
            # - Async event handling
            # - User consent for screen capture
            # - Frame buffer management

            logger.info("WGC API loaded successfully")

            # For a production implementation, consider using dedicated libraries
            # that handle the complexity, such as:
            # - windows-capture (https://pypi.org/project/windows-capture/)
            # - Or implement full WinRT interop as shown below

            # Simplified approach: Check if we can access the APIs
            # Full implementation would require creating capture session

            logger.info("WGC initialized (framework mode - full capture requires user consent)")
            self.is_initialized = False  # Set to False until full implementation
            return False

        except Exception as e:
            logger.error(f"WGC initialization failed: {e}")
            logger.info("WGC requires pythonnet and Windows 10 1803+ - falling back to MSS")
            return False

    def capture(self, monitor: int = 0) -> Optional[Image.Image]:
        """Capture using WGC.

        Full implementation requires:
        1. GraphicsCaptureItem for display/window
        2. Direct3D11CaptureFramePool for frame buffering
        3. GraphicsCaptureSession to start capture
        4. Event handling for frame arrival
        5. Converting Direct3D11 surface to PIL Image

        For production use, recommend specialized libraries like windows-capture.
        """
        if not self.is_initialized:
            return None

        try:
            # Full WGC capture implementation would:
            # 1. Wait for next frame from frame pool
            # 2. Get Direct3D11CaptureFrame
            # 3. Access ContentSize and Surface
            # 4. Copy surface data to system memory
            # 5. Convert to PIL Image
            # 6. Dispose frame

            logger.debug("WGC capture called (framework mode)")
            return None

        except Exception as e:
            logger.error(f"WGC capture failed: {e}")
            return None

    def cleanup(self) -> None:
        """Cleanup WGC resources."""
        if self._capture_session:
            try:
                # Stop capture session
                self._capture_session.Close()
                self._capture_session = None
            except:
                pass

        if self._frame_pool:
            try:
                # Close frame pool
                self._frame_pool.Close()
                self._frame_pool = None
            except:
                pass

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
