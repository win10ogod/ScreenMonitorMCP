"""ScreenMonitorMCP v2 - Model Context Protocol (MCP) Server Implementation

This module implements the MCP server for ScreenMonitorMCP v2, providing
screen capture and analysis capabilities through the Model Context Protocol.

The server operates using the official MCP Python SDK FastMCP API and provides tools for:
- Screen capture
- Screen analysis with AI
- Real-time monitoring

Author: ScreenMonitorMCP Team
Version: 2.0.0
License: MIT
"""

import asyncio
import logging
import base64
import sys
from typing import Any, Optional
from datetime import datetime

# Official MCP Python SDK FastMCP imports
from mcp.server.fastmcp import FastMCP

# Configure logger to use stderr for MCP mode - MUST BE EARLY
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)  # Only show errors in MCP mode

try:
    from .screen_capture import ScreenCapture
    from .streaming import stream_manager
    from .performance_monitor import performance_monitor
    from .window_capture import window_capture
    from .preset_loader import preset_loader
    from ..server.config import config
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from core.screen_capture import ScreenCapture
    from core.streaming import stream_manager
    from core.performance_monitor import performance_monitor
    from core.window_capture import window_capture
    from core.preset_loader import preset_loader
    from server.config import config

# Initialize FastMCP server
mcp = FastMCP("screenmonitormcp-v2")

# Add prompts to guide the MCP client on how to use this server
@mcp.prompt()
def capture_screenshot_prompt() -> str:
    """How to capture and view screenshots

    This prompt explains the correct way to capture and view screenshots
    using this MCP server.
    """
    return """To capture and view a screenshot:

1. Call the capture_screen tool:
   - This returns a resource_uri like "screen://capture/abc123"

2. The image will be automatically displayed to you
   - MCP clients (like Claude Desktop) automatically fetch and display resources
   - You don't need to call any additional tools
   - The image will appear in the conversation

3. You can then analyze the image naturally
   - Describe what you see
   - Answer questions about the image
   - Provide feedback or suggestions

Example usage:
- "Capture my screen and tell me what you see"
- "Take a screenshot and check if there are any errors"
- "Capture the screen and analyze the UI layout"

DO NOT try to read the resource URI with read_file or other file tools.
The MCP protocol handles resource fetching automatically."""

@mcp.prompt()
def streaming_guide_prompt() -> str:
    """How to use streaming in MCP mode

    This prompt explains how to use streaming features.
    """
    return """Screen streaming has TWO modes depending on your connection:

=== STDIO MODE (Claude Desktop, local MCP clients) ===

1. Create a stream with create_stream:
   - Returns a stream_id
   - Specify fps (frames per second), quality, and format
   - Example: create_stream(monitor=0, fps=10, quality=75)

2. Capture frames MANUALLY with capture_stream_frame:
   - Takes the stream_id
   - Returns a resource URI for the current frame
   - Image automatically displayed by MCP client
   - Example: capture_stream_frame(stream_id="abc123...")

3. Repeat step 2 as needed for each frame

4. Stop the stream when done:
   - Use stop_stream(stream_id) to end streaming

Stdio workflow:
1. "Create a stream at 5 fps"
2. "Capture a frame from the stream"
3. "Capture another frame" (repeatable)
4. "Stop the stream"

=== SSE MODE (MCP over HTTP, remote connections) ===

1. Create a stream with create_stream (same as stdio)

2. Start AUTO-PUSH with start_auto_push_stream:
   - Takes the stream_id and fps
   - Frames are automatically pushed to your client
   - NO need to call capture_stream_frame manually
   - Example: start_auto_push_stream(stream_id="abc123...", fps=5)

3. Frames arrive automatically at specified FPS

4. Stop auto-push and stream when done:
   - stop_auto_push_stream_tool(stream_id)
   - stop_stream(stream_id)

SSE workflow:
1. "Create a stream at 5 fps"
2. "Start auto-push for this stream at 5 fps"
3. (Frames arrive automatically)
4. "Stop auto-push and stream"

Monitor stream status:
- list_streams: See all active streams
- get_stream_info: Get detailed stream information

Streaming is useful for:
- Monitoring screen changes over time
- Periodic screenshots at specified FPS
- Analyzing how screens change"""

@mcp.prompt()
def system_info_prompt() -> str:
    """How to get system information

    This prompt explains how to check system status and performance.
    """
    return """To check system status and performance:

1. Use get_system_status to see overall system health:
   - Screen capture availability
   - Performance monitor status
   - Stream manager status

2. Use get_performance_metrics for detailed metrics:
   - CPU usage
   - Memory usage
   - Capture performance

3. Use get_capture_backend_info to see screenshot backend details:
   - Active backend (MSS, DXGI, or WGC)
   - Windows optimization status
   - Performance statistics
   - Expected improvements

4. Use get_memory_statistics for memory system stats"""

# Initialize components
screen_capture = ScreenCapture()

# Image cache for MCP resources (stores recent captures)
from collections import OrderedDict
import hashlib
_image_cache = OrderedDict()  # {resource_uri: (image_data, mime_type, metadata)}
_MAX_CACHE_SIZE = 120  # Keep last 120 captures (2 seconds @ 60 FPS)

def _add_to_cache(image_data: str, mime_type: str, metadata: dict) -> str:
    """Add image to cache and return resource URI."""
    # Generate unique ID based on timestamp and monitor
    timestamp = metadata.get("timestamp", datetime.now().isoformat())
    monitor = metadata.get("monitor", 0)
    resource_id = hashlib.md5(f"{timestamp}_{monitor}".encode()).hexdigest()[:12]
    resource_uri = f"screen://capture/{resource_id}"

    # Add to cache
    _image_cache[resource_uri] = (image_data, mime_type, metadata)

    # Maintain cache size limit
    while len(_image_cache) > _MAX_CACHE_SIZE:
        _image_cache.popitem(last=False)  # Remove oldest

    return resource_uri

@mcp.resource("screen://capture/{capture_id}")
async def get_screen_capture(capture_id: str) -> bytes:
    """Get a captured screen image by resource URI.

    This resource provides the actual image data for captures.
    Use capture_screen tool to create new captures.

    Returns:
        bytes: Raw image data (FastMCP handles base64 encoding automatically)
    """
    # Reconstruct full URI from capture_id
    uri = f"screen://capture/{capture_id}"

    if uri not in _image_cache:
        raise ValueError(f"Capture not found: {uri}")

    image_data_base64, mime_type, metadata = _image_cache[uri]

    # Decode base64 to bytes - FastMCP will handle base64 encoding for MCP protocol
    image_bytes = base64.b64decode(image_data_base64)

    return image_bytes

@mcp.tool()
async def capture_screen(
    monitor: int = 0,
    format: str = "png",
    quality: int = 85
) -> str:
    """Capture screen and return resource URI (NOT base64 data)

    This is the RECOMMENDED approach - returns a resource URI that can be
    used to fetch the actual image data. This avoids sending large base64
    data in the tool response.

    Args:
        monitor: Monitor number to capture (0 for primary)
        format: Image format (png or jpeg)
        quality: Image quality for JPEG (1-100)

    Returns:
        JSON with resource URI and metadata (without embedded image data)
    """
    try:
        capture_result = await screen_capture.capture_screen(monitor)
        if not capture_result.get("success"):
            return f"Error: Failed to capture screen - {capture_result.get('message', 'Unknown error')}"

        # Prepare metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "monitor": monitor,
            "width": capture_result.get("width"),
            "height": capture_result.get("height"),
            "format": format,
            "quality": quality if format == "jpeg" else 100
        }

        # Determine MIME type
        mime_type = f"image/{format}"

        # Add to cache and get resource URI
        resource_uri = _add_to_cache(
            capture_result["image_data"],
            mime_type,
            metadata
        )

        import json
        result = {
            "success": True,
            "resource_uri": resource_uri,
            "mime_type": mime_type,
            "metadata": metadata,
            "note": "Use the resource_uri to fetch the actual image data via MCP resources"
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_performance_metrics() -> str:
    """Get detailed performance metrics and system health
    
    Returns:
        Performance metrics as text
    """
    try:
        metrics = performance_monitor.get_metrics()
        return f"Performance Metrics: {metrics}"
    except Exception as e:
        logger.error(f"Failed to get performance metrics: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_system_status() -> str:
    """Get overall system status and health information

    Returns:
        System status information
    """
    try:
        status = {
            "timestamp": datetime.now().isoformat(),
            "screen_capture": screen_capture.is_available(),
            "performance_monitor": performance_monitor.is_running(),
            "stream_manager": stream_manager.is_running()
        }
        return f"System Status: {status}"
    except Exception as e:
        logger.error(f"Failed to get system status: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def create_stream(
    monitor: int = 0,
    fps: int = 10,
    quality: int = 80,
    format: str = "jpeg"
) -> str:
    """Create a new screen streaming session
    
    Args:
        monitor: Monitor number to stream (0 for primary)
        fps: Frames per second for streaming
        quality: Image quality (1-100)
        format: Image format (jpeg or png)
    
    Returns:
        Stream ID or error message
    """
    try:
        stream_id = await stream_manager.create_stream("screen", fps, quality, format)
        return f"Stream created with ID: {stream_id}"
    except Exception as e:
        logger.error(f"Failed to create stream: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def list_streams() -> str:
    """List all active streaming sessions
    
    Returns:
        List of active streams
    """
    try:
        streams = stream_manager.list_streams()
        return f"Active streams: {streams}"
    except Exception as e:
        logger.error(f"Failed to list streams: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_stream_info(stream_id: str) -> str:
    """Get information about a specific stream
    
    Args:
        stream_id: Stream ID to get information for
    
    Returns:
        Stream information
    """
    try:
        info = await stream_manager.get_stream_info(stream_id)
        return f"Stream info: {info}"
    except Exception as e:
        logger.error(f"Failed to get stream info: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def stop_stream(stream_id: str) -> str:
    """Stop a specific streaming session

    Args:
        stream_id: Stream ID to stop

    Returns:
        Success or error message
    """
    try:
        # Stop auto-push if active
        try:
            from .mcp_sse_server import stop_auto_push_stream
            await stop_auto_push_stream(stream_id)
        except ImportError:
            pass  # SSE mode not available

        result = await stream_manager.stop_stream(stream_id)
        return f"Stream stopped: {result}"
    except Exception as e:
        logger.error(f"Failed to stop stream: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def start_auto_push_stream(
    stream_id: str,
    fps: int = 5
) -> str:
    """Start automatically pushing frames from a stream (SSE mode only)

    This enables automatic frame push to SSE clients without manual capture.
    Only works when connected via MCP over SSE (HTTP mode).

    Args:
        stream_id: Stream ID to start auto-push for
        fps: Frames per second to push (default: 5)

    Returns:
        Success or error message
    """
    try:
        # Check if SSE mode is available
        try:
            from .mcp_sse_server import start_auto_push_stream as _start_auto_push
        except ImportError:
            return "Error: Auto-push requires MCP over SSE mode (HTTP server mode). Use stdio mode with capture_stream_frame for manual capture."

        # Verify stream exists
        stream_info = await stream_manager.get_stream_info(stream_id)
        if not stream_info:
            return f"Error: Stream {stream_id} not found"

        # Start auto-push
        await _start_auto_push(stream_id, fps)

        return f"Auto-push started for stream {stream_id} at {fps} fps. Frames will be pushed automatically via SSE."
    except Exception as e:
        logger.error(f"Failed to start auto-push: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def stop_auto_push_stream_tool(stream_id: str) -> str:
    """Stop automatically pushing frames from a stream

    Args:
        stream_id: Stream ID to stop auto-push for

    Returns:
        Success or error message
    """
    try:
        # Check if SSE mode is available
        try:
            from .mcp_sse_server import stop_auto_push_stream as _stop_auto_push
        except ImportError:
            return "Error: Auto-push requires MCP over SSE mode (HTTP server mode)"

        await _stop_auto_push(stream_id)

        return f"Auto-push stopped for stream {stream_id}"
    except Exception as e:
        logger.error(f"Failed to stop auto-push: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def capture_stream_frame(stream_id: str) -> str:
    """Capture current frame from an active stream and return resource URI

    This allows using streams in MCP mode by capturing individual frames
    as resources. The client will automatically fetch and display the image.

    Args:
        stream_id: Stream ID to capture from

    Returns:
        JSON with resource URI and metadata
    """
    try:
        # Get stream info to check if it exists
        stream_info = await stream_manager.get_stream_info(stream_id)
        if not stream_info:
            return f"Error: Stream {stream_id} not found"

        # Get monitor from stream config
        monitor = stream_info.get("monitor", 0)

        # Capture current frame using screen_capture
        capture_result = await screen_capture.capture_screen(monitor)
        if not capture_result.get("success"):
            return f"Error: Failed to capture frame - {capture_result.get('message', 'Unknown error')}"

        # Prepare metadata
        metadata = {
            "timestamp": datetime.now().isoformat(),
            "stream_id": stream_id,
            "monitor": monitor,
            "width": capture_result.get("width"),
            "height": capture_result.get("height"),
            "format": stream_info.get("format", "jpeg"),
            "quality": stream_info.get("quality", 75)
        }

        # Determine MIME type
        mime_type = f"image/{stream_info.get('format', 'jpeg')}"

        # Add to cache and get resource URI
        resource_uri = _add_to_cache(
            capture_result["image_data"],
            mime_type,
            metadata
        )

        import json
        result = {
            "success": True,
            "resource_uri": resource_uri,
            "mime_type": mime_type,
            "metadata": metadata,
            "note": "Use the resource_uri to fetch the actual image data via MCP resources"
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Failed to capture stream frame: {e}")
        return f"Error: {str(e)}"

# Memory System Tools

@mcp.tool()
async def get_memory_statistics() -> str:
    """Get memory system statistics and health information

    Returns:
        Memory system statistics
    """
    try:
        from .memory_system import memory_system
        stats = await memory_system.get_statistics()
        return f"Memory statistics: {stats}"
    except ImportError:
        from core.memory_system import memory_system
        stats = await memory_system.get_statistics()
        return f"Memory statistics: {stats}"
    except Exception as e:
        logger.error(f"Failed to get memory statistics: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_stream_memory_stats(stream_id: str = None) -> str:
    """Get memory system statistics for streaming

    Args:
        stream_id: Optional stream ID to get stats for a specific stream.
                   If not provided, returns stats for all streams.

    Returns:
        Streaming memory statistics
    """
    try:
        all_stats = stream_manager.get_memory_stats()

        # If stream_id is provided, return stats for that specific stream
        if stream_id:
            if stream_id in all_stats.get("streams", {}):
                stream_stats = all_stats["streams"][stream_id]
                return f"Memory stats for stream {stream_id}: {stream_stats}"
            else:
                return f"Error: Stream {stream_id} not found"

        # Otherwise return all stats
        return f"Stream memory statistics: {all_stats}"
    except Exception as e:
        logger.error(f"Failed to get stream memory stats: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def configure_stream_memory(
    enabled: bool = True,
    analysis_interval: int = 5
) -> str:
    """Configure memory system for streaming
    
    Args:
        enabled: Enable or disable memory system for streaming
        analysis_interval: Analysis interval in frames (default: 5)
    
    Returns:
        Configuration result
    """
    try:
        stream_manager.enable_memory_system(enabled)
        if analysis_interval > 0:
            stream_manager.set_analysis_interval(analysis_interval)
        
        return f"Stream memory configured: enabled={enabled}, interval={analysis_interval}"
    except Exception as e:
        logger.error(f"Failed to configure stream memory: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_memory_usage() -> str:
    """Get detailed memory usage and performance metrics
    
    Returns:
        Detailed memory usage statistics
    """
    try:
        from .memory_system import memory_system
        
        usage_stats = await memory_system.get_memory_usage()
        
        if "error" in usage_stats:
            return f"Error getting memory usage: {usage_stats['error']}"
        
        response_lines = [
            "Memory Usage Statistics:",
            f"- Database size: {usage_stats.get('database_size_mb', 0)} MB",
            f"- Process memory: {usage_stats.get('process_memory_mb', 0)} MB",
            f"- Total entries: {usage_stats.get('total_entries', 0)}",
            f"- Recent entries (1h): {usage_stats.get('recent_entries_1h', 0)}",
            f"- Auto cleanup enabled: {usage_stats.get('auto_cleanup_enabled', False)}"
        ]
        
        cleanup_stats = usage_stats.get('cleanup_stats', {})
        if cleanup_stats:
            response_lines.extend([
                "\nCleanup Statistics:",
                f"- Cleanup runs: {cleanup_stats.get('cleanup_runs', 0)}",
                f"- Last cleanup: {cleanup_stats.get('last_cleanup', 'Never')}"
            ])
        
        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to get memory usage: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def configure_auto_cleanup(
    enabled: bool,
    max_age_days: int = 7
) -> str:
    """Configure automatic memory cleanup settings
    
    Args:
        enabled: Enable or disable auto cleanup
        max_age_days: Maximum age for entries in days (default: 7)
    
    Returns:
        Configuration result
    """
    try:
        from .memory_system import memory_system
        
        result = await memory_system.configure_auto_cleanup(enabled, max_age_days)
        
        if result.get("success"):
            return result.get("message", "Auto cleanup configured successfully")
        else:
            return f"Error: {result.get('error', 'Unknown error occurred')}"
            
    except Exception as e:
         logger.error(f"Failed to configure auto cleanup: {e}")
         return f"Error: {str(e)}"

@mcp.tool()
def get_stream_resource_stats() -> str:
    """Get streaming resource usage statistics
    
    Returns:
        Streaming resource usage statistics
    """
    try:
        stats = stream_manager.get_resource_stats()
        
        response_lines = [
            "Streaming Resource Statistics:",
            f"- Memory usage: {stats.get('memory_usage_mb', 'N/A')} MB",
            f"- Memory limit: {stats.get('memory_limit_mb', 'N/A')} MB",
            f"- Active streams: {stats.get('active_streams', 0)}",
            f"- Max streams: {stats.get('max_streams', 'N/A')}",
            f"- Last cleanup: {stats.get('last_cleanup', 'Never')}",
            f"- Cleanup interval: {stats.get('cleanup_interval', 'N/A')} seconds"
        ]
        
        frame_buffers = stats.get('frame_buffers', {})
        if frame_buffers:
            response_lines.append("\nFrame Buffers:")
            for stream_id, buffer_size in frame_buffers.items():
                response_lines.append(f"- {stream_id}: {buffer_size} frames")
        
        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to get stream resource stats: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def configure_stream_resources(
    max_memory_mb: Optional[int] = None,
    max_streams: Optional[int] = None,
    frame_buffer_size: Optional[int] = None,
    cleanup_interval: Optional[int] = None
) -> str:
    """Configure streaming resource limits
    
    Args:
        max_memory_mb: Maximum memory usage in MB (optional)
        max_streams: Maximum concurrent streams (optional)
        frame_buffer_size: Maximum frames to buffer per stream (optional)
        cleanup_interval: Cleanup interval in seconds (optional)
    
    Returns:
        Configuration result
    """
    try:
        stream_manager.configure_resource_limits(
            max_memory_mb=max_memory_mb,
            max_streams=max_streams,
            frame_buffer_size=frame_buffer_size,
            cleanup_interval=cleanup_interval
        )
        
        config_items = []
        if max_memory_mb is not None:
            config_items.append(f"max_memory_mb={max_memory_mb}")
        if max_streams is not None:
            config_items.append(f"max_streams={max_streams}")
        if frame_buffer_size is not None:
            config_items.append(f"frame_buffer_size={frame_buffer_size}")
        if cleanup_interval is not None:
            config_items.append(f"cleanup_interval={cleanup_interval}")
        
        return f"Stream resource limits configured: {', '.join(config_items)}"
    except Exception as e:
        logger.error(f"Failed to configure stream resources: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_database_pool_stats() -> str:
    """Get database connection pool statistics
    
    Returns:
        Database pool usage statistics
    """
    try:
        from .memory_system import memory_system
        
        if not memory_system._db_pool:
            return "Database pool not initialized"
        
        stats = await memory_system._db_pool.get_stats()
        
        response_lines = [
            "Database Pool Statistics:",
            f"- Total connections: {stats.total_connections}",
            f"- Active connections: {stats.active_connections}",
            f"- Idle connections: {stats.idle_connections}",
            f"- Total queries: {stats.total_queries}",
            f"- Failed queries: {stats.failed_queries}",
            f"- Average query time: {stats.average_query_time:.4f}s",
            f"- Pool created: {stats.pool_created_at.strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        
        if stats.last_cleanup:
            response_lines.append(f"- Last cleanup: {stats.last_cleanup.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            response_lines.append("- Last cleanup: Never")
        
        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to get database pool stats: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def database_pool_health_check() -> str:
    """Perform database pool health check

    Returns:
        Database pool health status
    """
    try:
        from .memory_system import memory_system

        if not memory_system._db_pool:
            return "Database pool not initialized"

        health = await memory_system._db_pool.health_check()

        if health["healthy"]:
            response_lines = [
                "Database Pool Health: HEALTHY ✓",
                f"- Total connections: {health['total_connections']}",
                f"- Active connections: {health['active_connections']}",
                f"- Idle connections: {health['idle_connections']}",
                f"- Pool utilization: {health['pool_utilization']:.1%}",
                f"- Average query time: {health['average_query_time']:.4f}s"
            ]
        else:
            response_lines = [
                "Database Pool Health: UNHEALTHY ✗",
                f"- Error: {health.get('error', 'Unknown error')}"
            ]

        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to perform database health check: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_capture_backend_info() -> str:
    """Get screen capture backend information and optimization status

    Returns detailed information about:
    - Active capture backend (MSS, DXGI, WGC)
    - Windows optimization availability and status
    - Platform-specific recommendations
    - Performance statistics for different backends

    This is useful for understanding:
    - Whether Windows GPU-accelerated capture is being used
    - Installation requirements for optimizations
    - Expected performance improvements

    Returns:
        Capture backend information and recommendations
    """
    try:
        backend_info = screen_capture.get_backend_info()
        perf_stats = screen_capture.get_performance_stats()

        response_lines = [
            "Screen Capture Backend Information:",
            f"- Platform: {backend_info['platform']}",
            f"- Active Backend: {backend_info['active_backend']}",
            f"- Windows Optimization Available: {backend_info['windows_optimization_available']}",
            f"- Windows Optimization Active: {backend_info['windows_optimization_active']}",
            "",
            "Performance Statistics:",
            f"- Total Captures: {perf_stats['total_captures']}",
            f"- Cache Hit Rate: {perf_stats['cache_hit_rate_percent']}%",
            f"- Average Capture Time: {perf_stats['avg_capture_time_ms']:.2f}ms",
            f"- Windows Optimized Captures: {perf_stats['windows_opt_captures']} ({perf_stats['windows_opt_usage_percent']}%)",
            f"- MSS Captures: {perf_stats['mss_captures']} ({perf_stats['mss_usage_percent']}%)",
        ]

        # Add backend details if available
        if backend_info.get('backend_details'):
            details = backend_info['backend_details']
            response_lines.append("")
            response_lines.append("Backend Details:")
            response_lines.append(f"- Available Backends: {', '.join(details.get('available_backends', []))}")
            if details.get('backend_details'):
                for name, info in details['backend_details'].items():
                    response_lines.append(f"  - {name}: {info.get('backend', 'N/A')} (initialized: {info.get('initialized', False)})")

        # Add recommendations
        recommendations = backend_info.get('recommendations', {})
        if recommendations:
            response_lines.append("")
            response_lines.append("Recommendations:")
            response_lines.append(f"- {recommendations.get('message', 'No recommendations')}")
            if 'wgc_install' in recommendations:
                response_lines.append(f"- For WGC: {recommendations['wgc_install']}")
            if 'dxgi_install' in recommendations:
                response_lines.append(f"- For DXGI: {recommendations['dxgi_install']}")
            if 'benefits' in recommendations:
                response_lines.append(f"- Benefits: {recommendations['benefits']}")

        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to get capture backend info: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def enable_gaming_mode(
    mode: str = "performance",
    fps: Optional[int] = None,
    quality: Optional[int] = None,
    enable_frame_skip: bool = True
) -> str:
    """Enable gaming mode optimizations for high-performance screen streaming

    Gaming mode provides specialized configurations optimized for real-time
    game streaming with high FPS (30-120) and low latency.

    Available modes:
    - "quality": 10 FPS, 95% quality, PNG format (screenshots)
    - "balanced": 30 FPS, 75% quality, JPEG format (casual gaming)
    - "performance": 60 FPS, 50% quality, JPEG format (competitive gaming)
    - "extreme": 120 FPS, 30% quality, JPEG format (esports/high-end hardware)

    Args:
        mode: Performance mode preset ("quality", "balanced", "performance", "extreme")
        fps: Override FPS setting (default: mode preset)
        quality: Override quality setting 1-100 (default: mode preset)
        enable_frame_skip: Enable frame skipping to maintain stable FPS (default: True)

    Returns:
        Configuration status and performance expectations

    Example:
        enable_gaming_mode(mode="performance", fps=60, quality=50)
    """
    try:
        from .gaming_mode import PerformanceMode, GameStreamConfig

        # Validate mode
        try:
            perf_mode = PerformanceMode(mode.lower())
        except ValueError:
            return f"Error: Invalid mode '{mode}'. Must be one of: quality, balanced, performance, extreme"

        # Create configuration
        game_config = GameStreamConfig(mode=perf_mode)

        # Apply overrides
        if fps is not None:
            if fps < 1 or fps > 120:
                return "Error: FPS must be between 1 and 120"
            game_config.fps = fps

        if quality is not None:
            if quality < 1 or quality > 100:
                return "Error: Quality must be between 1 and 100"
            game_config.quality = quality

        game_config.enable_frame_skip = enable_frame_skip

        # Store configuration in server config
        config.enable_gaming_mode = True
        config.gaming_max_fps = game_config.fps
        config.gaming_quality = game_config.quality
        config.gaming_enable_frame_skip = game_config.enable_frame_skip

        response_lines = [
            "Gaming Mode Enabled ✓",
            "",
            "Configuration:",
            f"- Mode: {perf_mode.value.upper()}",
            f"- Target FPS: {game_config.fps}",
            f"- Image Quality: {game_config.quality}%",
            f"- Image Format: {game_config.format.upper()}",
            f"- Frame Skipping: {'Enabled' if game_config.enable_frame_skip else 'Disabled'}",
            f"- Adaptive Quality: {'Enabled' if game_config.adaptive_quality else 'Disabled'}",
            f"- Cache Size: {game_config.cache_size} frames",
            "",
            "Expected Performance:",
        ]

        # Add performance expectations
        if game_config.fps <= 10:
            response_lines.append("- Latency: 15-25ms/frame")
            response_lines.append("- Best for: Screenshots, documentation")
        elif game_config.fps <= 30:
            response_lines.append("- Latency: 8-12ms/frame")
            response_lines.append("- Best for: Casual gaming, monitoring")
        elif game_config.fps <= 60:
            response_lines.append("- Latency: 5-8ms/frame")
            response_lines.append("- Best for: Competitive gaming, fast action")
        else:
            response_lines.append("- Latency: 3-5ms/frame")
            response_lines.append("- Best for: Esports, high-end hardware")
            response_lines.append("- Requires: GPU-accelerated capture (DXGI/WGC on Windows)")

        response_lines.extend([
            "",
            "Next Steps:",
            "1. Use create_stream() to start a gaming stream",
            "2. Monitor performance with get_gaming_metrics()",
            "3. For lowest latency, use /mcp/game-stream WebSocket endpoint"
        ])

        return "\n".join(response_lines)

    except Exception as e:
        logger.error(f"Failed to enable gaming mode: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def get_gaming_metrics() -> str:
    """Get current gaming mode performance metrics

    Returns real-time performance statistics for active gaming streams:
    - Current and average FPS
    - Frame timing breakdown (capture, encode, network)
    - Dropped and skipped frame rates
    - Latency percentiles (p50, p95, p99)
    - Session duration and total frames

    This is useful for:
    - Monitoring gaming stream performance
    - Identifying bottlenecks
    - Optimizing configuration
    - Troubleshooting latency issues

    Returns:
        Detailed performance metrics for all active gaming streams
    """
    try:
        # Try to get metrics from SSE server
        try:
            from .mcp_sse_server import _stream_metrics

            if not _stream_metrics:
                return "No active gaming streams. Use create_stream() to start streaming."

            response_lines = [
                "Gaming Mode Performance Metrics",
                "=" * 50,
                ""
            ]

            for stream_id, metrics in _stream_metrics.items():
                stats = metrics.get_stats()

                if not stats.get("available"):
                    continue

                response_lines.extend([
                    f"Stream: {stream_id}",
                    "-" * 50,
                    "",
                    "Frame Rate:",
                    f"  Current FPS: {stats['current_fps']:.1f}",
                    f"  Average Session FPS: {stats['avg_session_fps']:.1f}",
                    "",
                    "Frame Timing (milliseconds):",
                    f"  Average Total: {stats['avg_frame_time_ms']:.2f}ms",
                    f"  P50 (Median): {stats['p50_frame_time_ms']:.2f}ms",
                    f"  P95: {stats['p95_frame_time_ms']:.2f}ms",
                    f"  P99: {stats['p99_frame_time_ms']:.2f}ms",
                    f"  Min: {stats['min_frame_time_ms']:.2f}ms",
                    f"  Max: {stats['max_frame_time_ms']:.2f}ms",
                    "",
                    "Timing Breakdown:",
                    f"  Capture: {stats['avg_capture_ms']:.2f}ms",
                    f"  Encode: {stats['avg_encode_ms']:.2f}ms",
                    f"  Network: {stats['avg_network_ms']:.2f}ms",
                    "",
                    "Frame Statistics:",
                    f"  Total Frames: {stats['total_frames']}",
                    f"  Dropped Frames: {stats['dropped_frames']} ({stats['drop_rate_percent']:.1f}%)",
                    f"  Skipped Frames: {stats['skipped_frames']} ({stats['skip_rate_percent']:.1f}%)",
                    "",
                    "Session Info:",
                    f"  Duration: {stats['session_duration_seconds']:.1f}s",
                    f"  Sample Window: {stats['sample_window_size']} frames",
                    ""
                ])

                # Add performance assessment
                fps = stats['current_fps']
                drop_rate = stats['drop_rate_percent']

                if fps >= 55 and drop_rate < 1:
                    assessment = "✓ Excellent - Stable high FPS"
                elif fps >= 45 and drop_rate < 5:
                    assessment = "✓ Good - Acceptable for gaming"
                elif fps >= 25 and drop_rate < 10:
                    assessment = "⚠ Fair - Consider lowering quality"
                else:
                    assessment = "✗ Poor - Reduce FPS or quality settings"

                response_lines.append(f"Performance: {assessment}")
                response_lines.append("")

            if config.enable_gaming_mode:
                response_lines.extend([
                    "",
                    "Gaming Mode Status:",
                    f"- Enabled: Yes",
                    f"- Max FPS: {config.gaming_max_fps}",
                    f"- Quality: {config.gaming_quality}%",
                    f"- Frame Skip: {'Enabled' if config.gaming_enable_frame_skip else 'Disabled'}",
                ])
            else:
                response_lines.extend([
                    "",
                    "Gaming Mode: Not enabled",
                    "Use enable_gaming_mode() to optimize for gaming"
                ])

            return "\n".join(response_lines)

        except ImportError:
            return "Gaming metrics not available. SSE server module not found."

    except Exception as e:
        logger.error(f"Failed to get gaming metrics: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def list_windows(filter_visible: bool = True) -> str:
    """List all windows on the system for game window selection

    Lists all application windows with their titles, positions, and sizes.
    Useful for finding the game window to optimize capture performance.

    Args:
        filter_visible: Only include visible windows (default: True)

    Returns:
        Formatted list of windows with details

    Example:
        list_windows(filter_visible=True)
    """
    try:
        windows = await window_capture.list_windows(filter_visible)

        if not windows:
            return "No windows found. Window capture may not be available on this platform."

        response_lines = [
            f"Found {len(windows)} window(s)",
            "=" * 70,
            ""
        ]

        for i, window in enumerate(windows, 1):
            response_lines.extend([
                f"{i}. {window.title}",
                f"   Position: ({window.x}, {window.y})",
                f"   Size: {window.width}x{window.height}",
                f"   PID: {window.pid}",
                f"   Visible: {window.is_visible}, Minimized: {window.is_minimized}",
                ""
            ])

        platform_info = window_capture.get_platform_info()
        response_lines.extend([
            "Platform Information:",
            f"- Platform: {platform_info['platform']}",
            f"- Window Capture Available: {platform_info['window_capture_available']}",
            "",
            "Usage:",
            "Use find_game_window() to search for a specific game window",
            "Use capture_game_window() to capture only the game window"
        ])

        return "\n".join(response_lines)

    except Exception as e:
        logger.error(f"Failed to list windows: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def find_game_window(
    game_title: str,
    case_sensitive: bool = False
) -> str:
    """Find a game window by title pattern

    Searches for a window matching the given title pattern.
    Useful for locating the game window before setting up optimized capture.

    Args:
        game_title: Game title or pattern to search for (substring match)
        case_sensitive: Case-sensitive search (default: False)

    Returns:
        Window information if found, error message otherwise

    Example:
        find_game_window(game_title="Counter-Strike")
        find_game_window(game_title="minecraft", case_sensitive=False)
    """
    try:
        window = await window_capture.find_window_by_title(game_title, case_sensitive)

        if not window:
            return f"Game window not found: '{game_title}'\n\nTip: Use list_windows() to see all available windows"

        response_lines = [
            f"✓ Found Game Window: {window.title}",
            "=" * 70,
            "",
            "Window Details:",
            f"- Title: {window.title}",
            f"- Position: ({window.x}, {window.y})",
            f"- Size: {window.width}x{window.height}",
            f"- PID: {window.pid}",
            f"- Visible: {window.is_visible}",
            f"- Minimized: {window.is_minimized}",
            "",
            "Capture Region:",
            f"{{",
            f"  \"left\": {window.x},",
            f"  \"top\": {window.y},",
            f"  \"width\": {window.width},",
            f"  \"height\": {window.height}",
            f"}}",
            "",
            "Next Steps:",
            "1. Use capture_game_window() to capture this window",
            "2. Or use create_stream() with window_title parameter for streaming"
        ]

        if window.is_minimized:
            response_lines.append("\n⚠ Warning: Window is minimized. Restore it before capturing.")

        return "\n".join(response_lines)

    except Exception as e:
        logger.error(f"Failed to find game window: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def capture_game_window(
    window_title: str,
    format: str = "png",
    quality: int = 85,
    case_sensitive: bool = False
) -> str:
    """Capture a specific game window instead of the entire screen

    This optimizes performance by capturing only the game window region,
    reducing CPU usage and improving frame rates for gaming scenarios.

    Args:
        window_title: Game window title or pattern to search for
        format: Image format (png or jpeg, default: png)
        quality: JPEG quality 1-100 (default: 85)
        case_sensitive: Case-sensitive title search (default: False)

    Returns:
        JSON string with image data and metadata

    Example:
        capture_game_window(window_title="Counter-Strike", format="jpeg", quality=75)
    """
    try:
        # Find the game window
        window = await window_capture.find_window_by_title(window_title, case_sensitive)

        if not window:
            return f"Error: Game window not found: '{window_title}'. Use list_windows() to find it."

        if window.is_minimized:
            return f"Error: Window '{window.title}' is minimized. Please restore it first."

        # Get the window region
        region = {
            "left": window.x,
            "top": window.y,
            "width": window.width,
            "height": window.height
        }

        # Capture the region
        capture_result = await screen_capture.capture_screen(
            monitor_id=0,  # Use primary monitor
            region=region,
            format=format,
            quality=quality
        )

        if not capture_result.get("success"):
            return f"Error: Failed to capture window"

        import json
        result = {
            "success": True,
            "window_title": window.title,
            "window_pid": window.pid,
            "image_base64": capture_result["image_data"],
            "format": format,
            "region": region,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "width": window.width,
                "height": window.height,
                "capture_mode": "window_optimized"
            }
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Failed to capture game window: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def list_gaming_presets() -> str:
    """List all available gaming presets

    Shows all predefined gaming configurations including:
    - Standard presets (casual, competitive, esports, etc.)
    - Game-specific presets (Counter-Strike, League of Legends, etc.)

    Returns:
        Formatted list of available presets with descriptions
    """
    try:
        presets = preset_loader.list_presets()

        if not presets:
            return "No gaming presets available. Check gaming_presets.json file."

        response_lines = [
            "Available Gaming Presets",
            "=" * 70,
            ""
        ]

        # Separate standard and game-specific presets
        standard_presets = {}
        game_presets = {}

        for name, desc in presets.items():
            if name in ["screenshot", "casual_gaming", "competitive_gaming", "esports",
                       "streaming_observer", "mobile_gaming", "retro_gaming", "vr_gaming",
                       "recording", "low_end_system"]:
                standard_presets[name] = desc
            else:
                game_presets[name] = desc

        # List standard presets
        response_lines.extend([
            "Standard Presets:",
            "-" * 70,
            ""
        ])

        for name, desc in standard_presets.items():
            response_lines.append(f"• {name}")
            response_lines.append(f"  {desc}")
            response_lines.append("")

        # List game-specific presets if any
        if game_presets:
            response_lines.extend([
                "",
                "Game-Specific Presets:",
                "-" * 70,
                ""
            ])

            for name, desc in game_presets.items():
                response_lines.append(f"• {name}")
                response_lines.append(f"  {desc}")
                response_lines.append("")

        response_lines.extend([
            "",
            "Usage:",
            "1. Get preset details: get_preset_info(preset_name='competitive_gaming')",
            "2. Use preset: use_gaming_preset(preset_name='competitive_gaming')",
            "3. Customize: use_gaming_preset(preset_name='esports', fps=90, quality=40)"
        ])

        return "\n".join(response_lines)

    except Exception as e:
        logger.error(f"Failed to list presets: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_preset_info(preset_name: str) -> str:
    """Get detailed information about a gaming preset

    Shows complete configuration details for a specific preset including:
    - FPS and quality settings
    - Format and optimization options
    - Expected latency
    - Recommended use cases

    Args:
        preset_name: Name of the preset (e.g., 'competitive_gaming', 'esports')

    Returns:
        Detailed preset information

    Example:
        get_preset_info(preset_name='competitive_gaming')
    """
    try:
        info = preset_loader.get_preset_info(preset_name)

        if not info:
            return f"Preset not found: '{preset_name}'\n\nUse list_gaming_presets() to see all available presets."

        return info

    except Exception as e:
        logger.error(f"Failed to get preset info: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def use_gaming_preset(
    preset_name: str,
    fps: Optional[int] = None,
    quality: Optional[int] = None
) -> str:
    """Apply a gaming preset configuration

    Load and apply a predefined gaming configuration from presets.
    You can override specific settings while using a preset as base.

    Args:
        preset_name: Name of the preset to use
        fps: Override FPS setting (optional)
        quality: Override quality setting (optional)

    Returns:
        Configuration status and details

    Example:
        use_gaming_preset(preset_name='competitive_gaming')
        use_gaming_preset(preset_name='esports', fps=90, quality=40)
    """
    try:
        # Build overrides
        overrides = {}
        if fps is not None:
            overrides['fps'] = fps
        if quality is not None:
            overrides['quality'] = quality

        # Load preset config
        game_config = preset_loader.get_config_from_preset(preset_name, **overrides)

        if not game_config:
            return f"Error: Preset not found: '{preset_name}'\n\nUse list_gaming_presets() to see all available presets."

        # Apply configuration to server config
        config.enable_gaming_mode = True
        config.gaming_max_fps = game_config.fps
        config.gaming_quality = game_config.quality
        config.gaming_enable_frame_skip = game_config.enable_frame_skip
        config.gaming_adaptive_quality = game_config.adaptive_quality
        config.gaming_cache_size = game_config.cache_size

        # Get preset info for display
        preset = preset_loader.get_preset(preset_name)
        preset_info = preset.get("name", preset_name) if preset else preset_name

        response_lines = [
            f"✓ Gaming Preset Applied: {preset_info}",
            "=" * 70,
            "",
            "Active Configuration:",
            f"- FPS: {game_config.fps}",
            f"- Quality: {game_config.quality}%",
            f"- Format: {game_config.format.upper()}",
            f"- Frame Skipping: {'Enabled' if game_config.enable_frame_skip else 'Disabled'}",
            f"- Adaptive Quality: {'Enabled' if game_config.adaptive_quality else 'Disabled'}",
            f"- Cache Size: {game_config.cache_size} frames",
            ""
        ]

        if preset:
            response_lines.extend([
                f"Expected Latency: {preset.get('expected_latency_ms', 'N/A')}ms",
                f"Recommended For: {preset.get('recommended_for', 'N/A')}",
                ""
            ])

            if "use_cases" in preset:
                response_lines.append("Optimized For:")
                for use_case in preset["use_cases"]:
                    response_lines.append(f"  • {use_case}")
                response_lines.append("")

        response_lines.extend([
            "Next Steps:",
            "1. Use create_stream() to start streaming",
            "2. Monitor performance with get_gaming_metrics()",
            "3. For lowest latency, use WebSocket at /mcp/game-stream"
        ])

        return "\n".join(response_lines)

    except Exception as e:
        logger.error(f"Failed to use preset: {e}")
        return f"Error: {str(e)}"

# Additional deprecated AI tools removed (v2.1+)
# Use capture_screen_image() and ask your MCP client for analysis instead

def setup_logging():
    """Setup logging configuration for MCP mode."""
    # Disable all loggers except critical errors
    logging.getLogger().setLevel(logging.CRITICAL)
    
    # Disable specific noisy loggers
    for logger_name in ['httpx', 'openai', 'urllib3', 'requests']:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)
        logging.getLogger(logger_name).disabled = True

def run_mcp_server():
    """Run the MCP server."""
    setup_logging()
    
    try:
        # Run the FastMCP server (it handles its own event loop)
        mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise

if __name__ == "__main__":
    run_mcp_server()