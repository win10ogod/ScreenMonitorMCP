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
    from ..server.config import config
except ImportError:
    # Fallback for direct execution
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    from core.screen_capture import ScreenCapture
    from core.streaming import stream_manager
    from core.performance_monitor import performance_monitor
    from server.config import config

# AI service is optional for MCP mode (only needed for HTTP server mode)
AI_SERVICE_AVAILABLE = False
ai_service = None
try:
    try:
        from .ai_service import ai_service as _ai_service
    except ImportError:
        from core.ai_service import ai_service as _ai_service

    ai_service = _ai_service
    AI_SERVICE_AVAILABLE = ai_service.is_available() if ai_service else False
    if AI_SERVICE_AVAILABLE:
        logger.info("AI service initialized (optional, for HTTP mode)")
    else:
        logger.info("AI service loaded but not configured (MCP-only mode)")
except ImportError:
    logger.info("AI service not loaded - MCP-only mode (recommended)")

# Initialize FastMCP server
mcp = FastMCP("screenmonitormcp-v2")

# Initialize components
screen_capture = ScreenCapture()

# Image cache for MCP resources (stores recent captures)
from collections import OrderedDict
import hashlib
_image_cache = OrderedDict()  # {resource_uri: (image_data, mime_type, metadata)}
_MAX_CACHE_SIZE = 10  # Keep last 10 captures

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
async def get_screen_capture(uri: str) -> str:
    """Get a captured screen image by resource URI.

    This resource provides the actual image data for captures.
    Use capture_screen tool to create new captures.
    """
    if uri not in _image_cache:
        raise ValueError(f"Capture not found: {uri}")

    image_data, mime_type, metadata = _image_cache[uri]

    # Return image data with proper MIME type
    # MCP will handle base64 encoding automatically
    return image_data

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
async def capture_screen_base64(
    monitor: int = 0,
    format: str = "jpeg",
    quality: int = 50,
    max_width: int = 1280
) -> str:
    """Capture screen and return base64 data (LEGACY, for compatibility)

    WARNING: This returns large base64 data in the response.
    For better performance, use capture_screen() which returns a resource URI instead.

    This method includes automatic image compression to reduce size:
    - Default format: JPEG (smaller than PNG)
    - Default quality: 50 (good balance between size and quality)
    - Default max_width: 1280 (scales down large screenshots)

    Args:
        monitor: Monitor number to capture (0 for primary)
        format: Image format (png or jpeg, default: jpeg)
        quality: Image quality for JPEG (1-100, default: 50)
        max_width: Maximum width in pixels (scales down if larger, default: 1280)

    Returns:
        JSON string with compressed image base64 data and metadata
    """
    try:
        capture_result = await screen_capture.capture_screen(monitor)
        if not capture_result.get("success"):
            return f"Error: Failed to capture screen - {capture_result.get('message', 'Unknown error')}"

        import json
        from PIL import Image
        import io

        # Decode and potentially resize image
        image_data = capture_result["image_data"]
        width = capture_result.get("width", 0)
        height = capture_result.get("height", 0)

        # If image is too large, resize it
        if width > max_width:
            # Decode base64 to PIL Image
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))

            # Calculate new dimensions maintaining aspect ratio
            ratio = max_width / width
            new_height = int(height * ratio)

            # Resize
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            # Re-encode with specified format and quality
            buffer = io.BytesIO()
            if format.lower() == "jpeg":
                img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
            else:
                img.save(buffer, format="PNG", optimize=True)

            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')
            width = max_width
            height = new_height
        elif format.lower() == "jpeg" and quality < 85:
            # Re-compress even if size is OK, to reduce quality
            img_bytes = base64.b64decode(image_data)
            img = Image.open(io.BytesIO(img_bytes))

            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
            image_data = base64.b64encode(buffer.getvalue()).decode('utf-8')

        result = {
            "success": True,
            "image_base64": image_data,
            "format": format,
            "monitor": monitor,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "width": width,
                "height": height,
                "quality": quality if format == "jpeg" else 100,
                "compressed": True
            }
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        logger.error(f"Screen capture failed: {e}")
        return f"Error: {str(e)}"

# Legacy AI-dependent tools removed (v2.1+)
# Use capture_screen_image() instead and let your MCP client analyze images

@mcp.tool()
async def list_ai_models() -> str:
    """List available AI models from the configured provider (HTTP mode only)

    Note: This tool is only available when AI service is configured.
    MCP mode does not require AI service configuration.

    Returns:
        List of available models as text
    """
    try:
        if not AI_SERVICE_AVAILABLE or ai_service is None:
            return "AI service not available. This tool is for HTTP server mode only. MCP mode uses client-side analysis."

        if not ai_service.is_available():
            return "Error: AI service is not configured. Please set OPENAI_API_KEY."

        result = await ai_service.list_models()

        if result.get("success"):
            models = result.get("models", [])
            if models:
                return f"Available models: {', '.join(models)}"
            else:
                return "No models available"
        else:
            return f"Error: {result.get('error', 'Unknown error occurred')}"
    except Exception as e:
        logger.error(f"Failed to list AI models: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
def get_ai_status() -> str:
    """Get AI service configuration status (HTTP mode only)

    Note: This tool is only relevant when AI service is configured.
    MCP mode does not require AI service configuration.

    Returns:
        AI service status information
    """
    try:
        if not AI_SERVICE_AVAILABLE or ai_service is None:
            return "AI service not loaded (MCP-only mode). This is normal and recommended for MCP usage."

        status = ai_service.get_status()
        return f"AI Service Status: {status}"
    except Exception as e:
        logger.error(f"Failed to get AI status: {e}")
        return f"Error: {str(e)}"

# First analyze_scene_from_memory function removed (duplicate)

# First query_memory function removed (duplicate)

# First get_memory_statistics function removed (duplicate)

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
            "ai_service": ai_service.is_available() if AI_SERVICE_AVAILABLE and ai_service else False,
            "ai_service_mode": "HTTP only" if AI_SERVICE_AVAILABLE else "Not loaded (MCP-only)",
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
        result = await stream_manager.stop_stream(stream_id)
        return f"Stream stopped: {result}"
    except Exception as e:
        logger.error(f"Failed to stop stream: {e}")
        return f"Error: {str(e)}"

# Memory System Tools

@mcp.tool()
async def analyze_scene_from_memory(
    query: str,
    stream_id: Optional[str] = None,
    time_range_minutes: int = 30,
    limit: int = 10
) -> str:
    """Analyze scene based on stored memory data (HTTP mode only)

    Note: This tool requires AI service for analysis.
    For MCP mode, use capture_screen_image and ask your client to analyze.

    Args:
        query: What to analyze or look for in the stored scenes
        stream_id: Specific stream to analyze (optional)
        time_range_minutes: Time range to search in minutes (default: 30)
        limit: Maximum number of results to analyze (default: 10)

    Returns:
        Scene analysis based on memory data
    """
    try:
        if not AI_SERVICE_AVAILABLE or ai_service is None:
            return "AI service not available. This tool requires AI service (HTTP mode only)."

        result = await ai_service.analyze_scene_from_memory(
            query=query,
            stream_id=stream_id,
            time_range_minutes=time_range_minutes,
            limit=limit
        )
        return f"Scene analysis: {result}"
    except Exception as e:
        logger.error(f"Failed to analyze scene from memory: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def query_memory(
    query: str,
    stream_id: Optional[str] = None,
    time_range_minutes: int = 60,
    limit: int = 20
) -> str:
    """Query the memory system for stored analysis data (HTTP mode only)

    Note: This tool requires AI service for querying.
    For MCP mode, memory operations should be done client-side.

    Args:
        query: Search query for memory entries
        stream_id: Filter by specific stream ID (optional)
        time_range_minutes: Time range to search in minutes (default: 60)
        limit: Maximum number of results (default: 20)

    Returns:
        Memory query results
    """
    try:
        if not AI_SERVICE_AVAILABLE or ai_service is None:
            return "AI service not available. This tool requires AI service (HTTP mode only)."

        result = await ai_service.query_memory_direct(
            query=query,
            stream_id=stream_id,
            time_range_minutes=time_range_minutes,
            limit=limit
        )
        return f"Memory query results: {result}"
    except Exception as e:
        logger.error(f"Failed to query memory: {e}")
        return f"Error: {str(e)}"

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
def get_stream_memory_stats() -> str:
    """Get memory system statistics for streaming
    
    Returns:
        Streaming memory statistics
    """
    try:
        stats = stream_manager.get_memory_stats()
        return f"Stream memory statistics: {stats}"
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