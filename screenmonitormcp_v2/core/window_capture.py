"""Window-based capture for optimized gaming performance.

This module provides window-specific capture capabilities to reduce overhead
by capturing only the game window instead of the entire screen.
"""

import sys
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class WindowInfo:
    """Information about a window."""
    title: str
    pid: int
    x: int
    y: int
    width: int
    height: int
    is_visible: bool
    is_minimized: bool
    hwnd: Optional[int] = None  # Windows handle


class WindowCapture:
    """Window-based screen capture for gaming optimization."""

    def __init__(self):
        """Initialize window capture."""
        self.platform = sys.platform
        self._windows_available = False

        # Try to import platform-specific modules
        if self.platform == "win32":
            try:
                import win32gui
                import win32process
                import win32con
                self._win32gui = win32gui
                self._win32process = win32process
                self._win32con = win32con
                self._windows_available = True
                logger.info("Windows window capture available")
            except ImportError:
                logger.warning("pywin32 not available, window capture disabled")
        elif self.platform == "darwin":
            try:
                import Quartz
                self._quartz = Quartz
                logger.info("macOS window capture available")
            except ImportError:
                logger.warning("Quartz not available, window capture disabled")
        else:
            logger.info(f"Window capture not implemented for {self.platform}")

    async def list_windows(self, filter_visible: bool = True) -> List[WindowInfo]:
        """List all windows.

        Args:
            filter_visible: Only include visible windows

        Returns:
            List of WindowInfo objects
        """
        return await asyncio.to_thread(self._list_windows_sync, filter_visible)

    def _list_windows_sync(self, filter_visible: bool = True) -> List[WindowInfo]:
        """Synchronous window listing."""
        if self.platform == "win32" and self._windows_available:
            return self._list_windows_win32(filter_visible)
        elif self.platform == "darwin":
            return self._list_windows_macos(filter_visible)
        else:
            logger.warning(f"Window listing not supported on {self.platform}")
            return []

    def _list_windows_win32(self, filter_visible: bool) -> List[WindowInfo]:
        """List windows on Windows."""
        windows = []

        def enum_callback(hwnd, _):
            if filter_visible and not self._win32gui.IsWindowVisible(hwnd):
                return True

            title = self._win32gui.GetWindowText(hwnd)
            if not title:  # Skip windows without titles
                return True

            # Get window rect
            try:
                rect = self._win32gui.GetWindowRect(hwnd)
                x, y, right, bottom = rect
                width = right - x
                height = bottom - y

                # Get process ID
                _, pid = self._win32process.GetWindowThreadProcessId(hwnd)

                # Check if minimized
                is_minimized = self._win32gui.IsIconic(hwnd)

                windows.append(WindowInfo(
                    title=title,
                    pid=pid,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    is_visible=self._win32gui.IsWindowVisible(hwnd),
                    is_minimized=is_minimized,
                    hwnd=hwnd
                ))
            except Exception as e:
                logger.debug(f"Failed to get window info for {hwnd}: {e}")

            return True

        self._win32gui.EnumWindows(enum_callback, None)
        return windows

    def _list_windows_macos(self, filter_visible: bool) -> List[WindowInfo]:
        """List windows on macOS."""
        # This is a placeholder for macOS implementation
        logger.warning("macOS window listing not yet implemented")
        return []

    async def find_window_by_title(
        self,
        title_pattern: str,
        case_sensitive: bool = False
    ) -> Optional[WindowInfo]:
        """Find a window by title pattern.

        Args:
            title_pattern: Pattern to match (substring match)
            case_sensitive: Case-sensitive matching

        Returns:
            WindowInfo if found, None otherwise
        """
        windows = await self.list_windows(filter_visible=True)

        pattern = title_pattern if case_sensitive else title_pattern.lower()

        for window in windows:
            window_title = window.title if case_sensitive else window.title.lower()
            if pattern in window_title:
                return window

        return None

    async def find_window_by_pid(self, pid: int) -> Optional[WindowInfo]:
        """Find a window by process ID.

        Args:
            pid: Process ID

        Returns:
            WindowInfo if found, None otherwise
        """
        windows = await self.list_windows(filter_visible=True)

        for window in windows:
            if window.pid == pid:
                return window

        return None

    async def get_window_region(
        self,
        window_identifier: str,
        by: str = "title"
    ) -> Optional[Dict[str, int]]:
        """Get capture region for a window.

        Args:
            window_identifier: Window title or PID
            by: Search method ("title" or "pid")

        Returns:
            Region dict with {left, top, width, height} or None
        """
        window = None

        if by == "title":
            window = await self.find_window_by_title(window_identifier)
        elif by == "pid":
            try:
                pid = int(window_identifier)
                window = await self.find_window_by_pid(pid)
            except ValueError:
                logger.error(f"Invalid PID: {window_identifier}")
                return None
        else:
            logger.error(f"Invalid search method: {by}")
            return None

        if not window:
            logger.warning(f"Window not found: {window_identifier}")
            return None

        if window.is_minimized:
            logger.warning(f"Window is minimized: {window.title}")
            return None

        return {
            "left": window.x,
            "top": window.y,
            "width": window.width,
            "height": window.height
        }

    def get_platform_info(self) -> Dict[str, Any]:
        """Get platform and capability information.

        Returns:
            Platform info dict
        """
        return {
            "platform": self.platform,
            "window_capture_available": self._windows_available or self.platform == "darwin",
            "features": {
                "list_windows": self.platform in ["win32", "darwin"],
                "find_by_title": self.platform in ["win32", "darwin"],
                "find_by_pid": self.platform in ["win32", "darwin"]
            }
        }


# Global instance
window_capture = WindowCapture()
