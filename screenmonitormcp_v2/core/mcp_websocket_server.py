"""MCP over WebSocket transport implementation.

This provides a WebSocket transport for MCP that supports binary resource transfer,
avoiding the base64 encoding overhead required by SSE and HTTP transports.

Key advantages over SSE:
- Binary frame support: Send images as raw bytes, not base64
- ~33% smaller payload size (no base64 expansion)
- Lower CPU usage (no encode/decode overhead)
- Full-duplex communication
- Lower latency for real-time streaming

Protocol:
- Text frames: JSON-RPC MCP messages (tools, prompts, etc.)
- Binary frames: Raw resource data (images, etc.)
- Resource metadata sent as text, followed by binary data
"""

import asyncio
import json
import logging
import uuid
import base64
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Import MCP server implementation
from .mcp_server import mcp, screen_capture, stream_manager, _image_cache

# Storage for active WebSocket connections
_ws_connections: Dict[str, WebSocket] = {}
_connection_lock = asyncio.Lock()

# Create router for WebSocket endpoints
ws_router = APIRouter()


class BinaryResourceResponse:
    """Represents a binary resource response to be sent over WebSocket."""

    def __init__(self, uri: str, mime_type: str, data: bytes, metadata: Optional[Dict] = None):
        self.uri = uri
        self.mime_type = mime_type
        self.data = data
        self.metadata = metadata or {}


async def _send_binary_resource(websocket: WebSocket, response: BinaryResourceResponse):
    """Send a binary resource over WebSocket.

    Protocol:
    1. Send metadata as JSON text frame
    2. Send binary data as binary frame

    Args:
        websocket: WebSocket connection
        response: Binary resource response to send
    """
    try:
        # Send metadata first
        metadata_msg = {
            "type": "resource_metadata",
            "uri": response.uri,
            "mimeType": response.mime_type,
            "size": len(response.data),
            "metadata": response.metadata
        }
        await websocket.send_json(metadata_msg)

        # Send binary data
        await websocket.send_bytes(response.data)

        logger.debug(f"Sent binary resource: {response.uri}, {len(response.data)} bytes")

    except Exception as e:
        logger.error(f"Failed to send binary resource: {e}")
        raise


async def _process_mcp_request(request_data: Dict[str, Any], websocket: WebSocket) -> Optional[Dict[str, Any]]:
    """Process MCP request and return response.

    This handles MCP JSON-RPC requests from WebSocket clients.
    For resources, sends binary data directly instead of base64.

    Args:
        request_data: MCP JSON-RPC request
        websocket: WebSocket connection for binary responses

    Returns:
        JSON response dict, or None if binary response was sent
    """
    try:
        method = request_data.get("method")
        params = request_data.get("params", {})
        request_id = request_data.get("id")

        # Handle MCP protocol methods
        if method == "initialize":
            # MCP initialization handshake
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "screenmonitormcp-v2",
                        "version": "2.5.0"
                    },
                    "capabilities": {
                        "tools": {},
                        "resources": {
                            "subscribe": True,
                            "listChanged": True
                        },
                        "prompts": {}
                    },
                    "experimental": {
                        "binaryResources": True  # Advertise binary resource support
                    }
                }
            }

        elif method == "tools/list":
            # Return list of available tools
            tool_list = mcp._tool_manager.list_tools()
            tools = []
            for tool in tool_list:
                tools.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.parameters if hasattr(tool, 'parameters') else {
                        "type": "object",
                        "properties": {}
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
            tool_list = mcp._tool_manager.list_tools()
            tool_func = None
            for tool in tool_list:
                if tool.name == tool_name:
                    tool_func = tool.fn
                    break

            if tool_func is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Tool not found: {tool_name}"
                    }
                }

            # Call the tool
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
                            "description": "Captured screen images (binary transfer supported)",
                            "mimeType": "image/png"
                        }
                    ]
                }
            }

        elif method == "resources/read":
            # Read a resource - send as BINARY over WebSocket
            uri = params.get("uri")

            if uri and uri.startswith("screen://capture/"):
                try:
                    # Get the cached entry
                    if uri not in _image_cache:
                        return {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {
                                "code": -32000,
                                "message": f"Resource not found: {uri}"
                            }
                        }

                    # Get image data from cache
                    image_data_base64, mime_type, metadata = _image_cache[uri]

                    # Decode base64 to bytes for binary transfer
                    image_bytes = base64.b64decode(image_data_base64)

                    # Send as binary resource
                    binary_response = BinaryResourceResponse(
                        uri=uri,
                        mime_type=mime_type,
                        data=image_bytes,
                        metadata=metadata
                    )

                    await _send_binary_resource(websocket, binary_response)

                    # Return JSON acknowledgment
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "uri": uri,
                            "binary": True,
                            "size": len(image_bytes),
                            "mimeType": mime_type,
                            "message": "Binary data sent separately"
                        }
                    }

                except Exception as e:
                    logger.error(f"Resource read failed: {e}", exc_info=True)
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
            prompt_list = mcp._prompt_manager.list_prompts()
            prompts = []
            for prompt in prompt_list:
                prompts.append({
                    "name": prompt.name,
                    "description": prompt.description or "",
                })

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"prompts": prompts}
            }

        elif method == "prompts/get":
            # Get a prompt
            prompt_name = params.get("name")

            prompt_list = mcp._prompt_manager.list_prompts()
            prompt_func = None
            for prompt in prompt_list:
                if prompt.name == prompt_name:
                    prompt_func = prompt.fn
                    break

            if prompt_func is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Prompt not found: {prompt_name}"
                    }
                }

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

        elif method and method.startswith("notifications/"):
            # Handle notifications (no response expected)
            logger.info(f"Received notification: {method}")
            return None

        else:
            # Unknown method - only return error if this is a request (has id)
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                }
            else:
                # Notification with unknown method - log and ignore
                logger.warning(f"Unknown notification received: {method}")
                return None

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


@ws_router.websocket("/mcp")
async def mcp_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for MCP with binary resource support.

    This endpoint provides full-duplex MCP communication with native
    binary transfer for resources, avoiding base64 encoding overhead.

    Protocol:
    - Client sends: JSON-RPC requests (text frames)
    - Server sends: JSON-RPC responses (text frames)
    - Server sends: Binary resources (binary frames)

    Benefits:
    - 33% smaller payloads (no base64 expansion)
    - Lower CPU usage (no encoding/decoding)
    - Lower latency for high-FPS streaming
    - Real-time notifications

    Usage:
        ws = new WebSocket("ws://localhost:8000/mcp/ws")
        ws.onmessage = (event) => {
            if (event.data instanceof Blob) {
                // Binary resource data
                handleBinaryResource(event.data)
            } else {
                // JSON-RPC message
                const msg = JSON.parse(event.data)
                handleMcpMessage(msg)
            }
        }
    """
    connection_id = str(uuid.uuid4())

    try:
        # Accept WebSocket connection
        await websocket.accept()

        # Store connection
        async with _connection_lock:
            _ws_connections[connection_id] = websocket

        logger.info(f"WebSocket MCP connection established: {connection_id}")

        # Send welcome message
        await websocket.send_json({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {
                "connectionId": connection_id,
                "protocolVersion": "2024-11-05",
                "serverInfo": {
                    "name": "screenmonitormcp-v2",
                    "version": "2.5.0"
                },
                "capabilities": {
                    "tools": {},
                    "resources": {},
                    "prompts": {}
                },
                "experimental": {
                    "binaryResources": True
                }
            }
        })

        # Message loop
        while True:
            # Receive message from client
            try:
                # WebSocket can receive text or binary
                message = await websocket.receive()

                if "text" in message:
                    # JSON-RPC request
                    request_data = json.loads(message["text"])

                    # Process MCP request
                    response = await _process_mcp_request(request_data, websocket)

                    # Send JSON response if not None (binary responses return acknowledgment)
                    if response is not None:
                        await websocket.send_json(response)

                elif "bytes" in message:
                    # Client sent binary data (not expected in standard MCP)
                    logger.warning(f"Received unexpected binary data from client: {len(message['bytes'])} bytes")

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON from client: {e}")
                await websocket.send_json({
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": f"Parse error: {str(e)}"
                    }
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket MCP connection closed: {connection_id}")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        # Cleanup connection
        async with _connection_lock:
            if connection_id in _ws_connections:
                del _ws_connections[connection_id]

        # Close WebSocket if still open
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.close()
            except:
                pass


async def broadcast_to_ws_clients(message: Dict[str, Any]):
    """Broadcast a message to all connected WebSocket clients.

    Args:
        message: MCP message to broadcast
    """
    async with _connection_lock:
        for connection_id, websocket in _ws_connections.items():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send message to {connection_id}: {e}")


async def broadcast_binary_resource(resource: BinaryResourceResponse):
    """Broadcast a binary resource to all connected WebSocket clients.

    Args:
        resource: Binary resource to broadcast
    """
    async with _connection_lock:
        for connection_id, websocket in _ws_connections.items():
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await _send_binary_resource(websocket, resource)
            except Exception as e:
                logger.error(f"Failed to send binary resource to {connection_id}: {e}")


# Auto-push streaming functionality for WebSocket
_ws_auto_push_streams: Dict[str, asyncio.Task] = {}


async def _ws_auto_push_stream_frames(stream_id: str, interval: float = 1.0):
    """Automatically push stream frames to WebSocket clients as binary data.

    This is optimized for WebSocket binary transfer - no base64 encoding needed!

    Args:
        stream_id: Stream ID to push frames from
        interval: Interval between frames in seconds
    """
    import time

    logger.info(f"Starting WebSocket auto-push for stream {stream_id} at {1.0/interval:.1f} FPS")

    try:
        while True:
            frame_start = time.time()

            # Check if stream still exists
            stream_info = await stream_manager.get_stream_info(stream_id)
            if not stream_info:
                logger.info(f"Stream {stream_id} no longer exists, stopping WebSocket auto-push")
                break

            # Capture frame
            monitor = stream_info.get("monitor", 0)
            capture_result = await screen_capture.capture_screen(
                monitor,
                quality=stream_info.get('quality', 75) if stream_info.get('format') == 'jpeg' else 100
            )

            if capture_result.get("success"):
                # Decode base64 to bytes for binary transfer
                image_bytes = base64.b64decode(capture_result["image_data"])

                metadata = {
                    "timestamp": datetime.now().isoformat(),
                    "stream_id": stream_id,
                    "monitor": monitor,
                    "width": capture_result.get("width"),
                    "height": capture_result.get("height"),
                }

                mime_type = f"image/{stream_info.get('format', 'jpeg')}"

                # Create binary resource
                resource = BinaryResourceResponse(
                    uri=f"stream://{stream_id}/frame",
                    mime_type=mime_type,
                    data=image_bytes,
                    metadata=metadata
                )

                # Broadcast to all WebSocket clients
                await broadcast_binary_resource(resource)

            # Wait for next frame
            elapsed = time.time() - frame_start
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        logger.info(f"WebSocket auto-push cancelled for stream {stream_id}")
    except Exception as e:
        logger.error(f"WebSocket auto-push error for stream {stream_id}: {e}", exc_info=True)


async def start_ws_auto_push_stream(stream_id: str, fps: int = 5):
    """Start automatically pushing frames from a stream via WebSocket.

    Args:
        stream_id: Stream ID to auto-push
        fps: Frames per second to push
    """
    interval = 1.0 / fps

    # Cancel existing auto-push if any
    if stream_id in _ws_auto_push_streams:
        _ws_auto_push_streams[stream_id].cancel()

    # Start new auto-push task
    task = asyncio.create_task(_ws_auto_push_stream_frames(stream_id, interval))
    _ws_auto_push_streams[stream_id] = task

    logger.info(f"Started WebSocket auto-push for stream {stream_id} at {fps} fps")


async def stop_ws_auto_push_stream(stream_id: str):
    """Stop automatically pushing frames from a stream.

    Args:
        stream_id: Stream ID to stop auto-pushing
    """
    if stream_id in _ws_auto_push_streams:
        _ws_auto_push_streams[stream_id].cancel()
        del _ws_auto_push_streams[stream_id]
        logger.info(f"Stopped WebSocket auto-push for stream {stream_id}")


@ws_router.get("/mcp/stats")
async def get_ws_stats():
    """Get WebSocket connection statistics.

    Returns:
        JSON with WebSocket stats
    """
    async with _connection_lock:
        active_connections = len(_ws_connections)

    return {
        "success": True,
        "timestamp": datetime.now().isoformat(),
        "active_connections": active_connections,
        "active_streams": len(_ws_auto_push_streams),
        "transport": "websocket",
        "binary_support": True
    }
