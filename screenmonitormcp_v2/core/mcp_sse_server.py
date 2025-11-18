"""MCP over SSE (Server-Sent Events) transport implementation.

This allows MCP clients to connect over HTTP instead of stdio,
enabling remote connections and web-based MCP clients.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from collections import OrderedDict

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)

# Import MCP server implementation
from .mcp_server import mcp, screen_capture, stream_manager

# Storage for active SSE connections and their message queues
_sse_connections: Dict[str, asyncio.Queue] = {}
_connection_lock = asyncio.Lock()

# Create router for SSE endpoints
sse_router = APIRouter()


async def _process_mcp_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process MCP request and return response.

    This handles MCP JSON-RPC requests from SSE clients.
    """
    try:
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        # Handle MCP protocol methods
        if method == "tools/list":
            # Return list of available tools
            tools = []
            for tool_name, tool_func in mcp._tool_manager.list_tools().items():
                tools.append({
                    "name": tool_name,
                    "description": tool_func.__doc__ or "",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},  # FastMCP handles this
                    }
                })

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": tools}
            }

        elif method == "tools/call":
            # Call a tool
            tool_name = params.get("name")
            tool_params = params.get("arguments", {})

            # Get tool function from FastMCP
            tools = mcp._tool_manager.list_tools()
            if tool_name not in tools:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }

            # Call the tool
            tool_func = tools[tool_name]
            try:
                if asyncio.iscoroutinefunction(tool_func):
                    result = await tool_func(**tool_params)
                else:
                    result = tool_func(**tool_params)

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": str(result)
                            }
                        ]
                    }
                }
            except Exception as e:
                logger.error(f"Tool execution failed: {e}", exc_info=True)
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Tool execution failed: {str(e)}"
                    }
                }

        elif method == "resources/list":
            # Return list of available resources
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": [
                        {
                            "uri": "screen://capture/{id}",
                            "name": "Screen Capture",
                            "description": "Captured screen images",
                            "mimeType": "image/png"
                        }
                    ]
                }
            }

        elif method == "resources/read":
            # Read a resource
            uri = params.get("uri")

            # Use the resource handler from mcp_server
            from .mcp_server import get_screen_capture

            # Extract capture_id from URI
            if uri and uri.startswith("screen://capture/"):
                capture_id = uri.replace("screen://capture/", "")
                try:
                    image_bytes = await get_screen_capture(capture_id)

                    import base64
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')

                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "contents": [
                                {
                                    "uri": uri,
                                    "mimeType": "image/png",
                                    "blob": image_base64
                                }
                            ]
                        }
                    }
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": f"Resource not found: {str(e)}"
                        }
                    }

        elif method == "prompts/list":
            # Return list of available prompts
            prompts = []
            for prompt_name, prompt_func in mcp._prompt_manager.list_prompts().items():
                prompts.append({
                    "name": prompt_name,
                    "description": prompt_func.__doc__ or "",
                })

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"prompts": prompts}
            }

        elif method == "prompts/get":
            # Get a prompt
            prompt_name = params.get("name")

            prompts = mcp._prompt_manager.list_prompts()
            if prompt_name not in prompts:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Prompt not found: {prompt_name}"
                    }
                }

            prompt_func = prompts[prompt_name]
            try:
                result = prompt_func()

                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "messages": [
                            {
                                "role": "user",
                                "content": {
                                    "type": "text",
                                    "text": result
                                }
                            }
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": f"Prompt execution failed: {str(e)}"
                    }
                }

        else:
            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    except Exception as e:
        logger.error(f"MCP request processing failed: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": request_data.get("id"),
            "error": {
                "code": -32000,
                "message": f"Internal error: {str(e)}"
            }
        }


@sse_router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """SSE endpoint for MCP over HTTP.

    This endpoint provides Server-Sent Events for MCP protocol,
    allowing clients to connect over HTTP instead of stdio.

    Returns:
        EventSourceResponse: SSE stream with MCP messages
    """
    connection_id = str(uuid.uuid4())
    message_queue = asyncio.Queue()

    async with _connection_lock:
        _sse_connections[connection_id] = message_queue

    logger.info(f"SSE connection established: {connection_id}")

    async def event_generator():
        """Generate SSE events."""
        try:
            # Send initial connection message
            yield {
                "event": "message",
                "data": json.dumps({
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {
                            "name": "screenmonitormcp-v2",
                            "version": "2.5.0"
                        },
                        "capabilities": {
                            "tools": {},
                            "resources": {},
                            "prompts": {}
                        }
                    }
                })
            }

            # Stream messages from queue
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        message_queue.get(),
                        timeout=30.0
                    )

                    yield {
                        "event": "message",
                        "data": json.dumps(message)
                    }

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield {
                        "event": "ping",
                        "data": ""
                    }

        finally:
            # Cleanup connection
            async with _connection_lock:
                if connection_id in _sse_connections:
                    del _sse_connections[connection_id]

            logger.info(f"SSE connection closed: {connection_id}")

    return EventSourceResponse(event_generator())


@sse_router.post("/messages")
async def mcp_message_endpoint(request: Request):
    """Handle MCP messages from client.

    This endpoint receives MCP JSON-RPC requests from clients
    and returns responses.

    Returns:
        JSON response with MCP result or error
    """
    try:
        request_data = await request.json()

        # Process MCP request
        response = await _process_mcp_request(request_data)

        return response

    except Exception as e:
        logger.error(f"Message processing failed: {e}", exc_info=True)
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32700,
                "message": f"Parse error: {str(e)}"
            }
        }


async def broadcast_to_sse_clients(message: Dict[str, Any]):
    """Broadcast a message to all connected SSE clients.

    Args:
        message: MCP message to broadcast
    """
    async with _connection_lock:
        for connection_id, queue in _sse_connections.items():
            try:
                await queue.put(message)
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")


# Auto-push streaming functionality
_auto_push_streams: Dict[str, asyncio.Task] = {}


async def _auto_push_stream_frames(stream_id: str, interval: float = 1.0):
    """Automatically push stream frames to SSE clients.

    Args:
        stream_id: Stream ID to push frames from
        interval: Interval between frames in seconds
    """
    logger.info(f"Starting auto-push for stream {stream_id}")

    try:
        while True:
            # Check if stream still exists
            stream_info = await stream_manager.get_stream_info(stream_id)
            if not stream_info:
                logger.info(f"Stream {stream_id} no longer exists, stopping auto-push")
                break

            # Capture frame
            monitor = stream_info.get("monitor", 0)
            capture_result = await screen_capture.capture_screen(monitor)

            if capture_result.get("success"):
                # Create resource URI
                from .mcp_server import _add_to_cache

                metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "stream_id": stream_id,
                    "monitor": monitor,
                    "width": capture_result.get("width"),
                    "height": capture_result.get("height"),
                }

                mime_type = f"image/{stream_info.get('format', 'jpeg')}"
                resource_uri = _add_to_cache(
                    capture_result["image_data"],
                    mime_type,
                    metadata
                )

                # Broadcast frame notification to SSE clients
                await broadcast_to_sse_clients({
                    "jsonrpc": "2.0",
                    "method": "notifications/resources/updated",
                    "params": {
                        "uri": resource_uri,
                        "stream_id": stream_id,
                        "metadata": metadata
                    }
                })

            # Wait for next frame
            await asyncio.sleep(interval)

    except asyncio.CancelledError:
        logger.info(f"Auto-push cancelled for stream {stream_id}")
    except Exception as e:
        logger.error(f"Auto-push error for stream {stream_id}: {e}", exc_info=True)


async def start_auto_push_stream(stream_id: str, fps: int = 5):
    """Start automatically pushing frames from a stream.

    Args:
        stream_id: Stream ID to auto-push
        fps: Frames per second to push
    """
    interval = 1.0 / fps

    # Cancel existing auto-push if any
    if stream_id in _auto_push_streams:
        _auto_push_streams[stream_id].cancel()

    # Start new auto-push task
    task = asyncio.create_task(_auto_push_stream_frames(stream_id, interval))
    _auto_push_streams[stream_id] = task

    logger.info(f"Started auto-push for stream {stream_id} at {fps} fps")


async def stop_auto_push_stream(stream_id: str):
    """Stop automatically pushing frames from a stream.

    Args:
        stream_id: Stream ID to stop auto-pushing
    """
    if stream_id in _auto_push_streams:
        _auto_push_streams[stream_id].cancel()
        del _auto_push_streams[stream_id]
        logger.info(f"Stopped auto-push for stream {stream_id}")
