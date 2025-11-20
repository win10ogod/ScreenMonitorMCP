# MCP WebSocket Binary Transport Guide

## Overview

ScreenMonitorMCP v2 now supports **MCP over WebSocket with native binary resource transfer**, providing significant performance improvements over HTTP/SSE transport.

### Key Benefits

| Feature | SSE (HTTP) | WebSocket (Binary) | Improvement |
|---------|------------|-------------------|-------------|
| **Payload Size** | Base64 encoded (+33%) | Raw bytes | **~33% smaller** |
| **CPU Usage** | Encode/decode overhead | Direct binary | **Lower CPU** |
| **Latency** | HTTP request overhead | WebSocket frames | **Lower latency** |
| **Communication** | Unidirectional | Full-duplex | **Bidirectional** |
| **Streaming** | Server-sent events | Binary frames | **More efficient** |

## Quick Start

### 1. Start Server

```bash
# Start the HTTP server with WebSocket support
python -m screenmonitormcp_v2

# Server will start on http://localhost:8000
# WebSocket endpoint: ws://localhost:8000/mcp/ws/mcp
```

### 2. Connect from Client

#### Python Client

```python
import asyncio
import websockets
import json

async def connect_mcp():
    uri = "ws://localhost:8000/mcp/ws/mcp"

    async with websockets.connect(uri) as ws:
        # Receive welcome message
        welcome = await ws.recv()
        print(json.loads(welcome))

        # Send initialize request
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "my-client", "version": "1.0"}
            }
        }))

        # Receive response
        response = await ws.recv()
        print(json.loads(response))

asyncio.run(connect_mcp())
```

#### JavaScript/Browser Client

```javascript
const ws = new WebSocket("ws://localhost:8000/mcp/ws/mcp");

ws.onopen = () => {
    console.log("Connected to MCP WebSocket");
};

ws.onmessage = (event) => {
    if (event.data instanceof Blob) {
        // Binary resource data
        console.log("Received binary data:", event.data.size, "bytes");
        handleBinaryResource(event.data);
    } else {
        // JSON-RPC message
        const msg = JSON.parse(event.data);
        console.log("Received message:", msg);
        handleMcpMessage(msg);
    }
};

// Send MCP request
ws.send(JSON.stringify({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
    params: {}
}));
```

## Protocol Details

### Message Flow

1. **Connection Established**
   - Client connects to `ws://localhost:8000/mcp/ws/mcp`
   - Server sends welcome notification

2. **Text Frames** (JSON-RPC)
   - Initialize, tools/list, tools/call, prompts, etc.
   - Standard MCP JSON-RPC format

3. **Binary Frames** (Resources)
   - Screen captures sent as raw bytes
   - No base64 encoding needed!

### Binary Resource Transfer

When you request a resource (e.g., screen capture), the server sends:

1. **Metadata** (text frame):
```json
{
    "type": "resource_metadata",
    "uri": "screen://capture/abc123",
    "mimeType": "image/png",
    "size": 245678,
    "metadata": {
        "timestamp": "2025-11-20T10:30:00Z",
        "width": 1920,
        "height": 1080
    }
}
```

2. **Binary Data** (binary frame):
   - Raw PNG/JPEG bytes
   - Size exactly as specified in metadata

3. **Acknowledgment** (text frame):
```json
{
    "jsonrpc": "2.0",
    "id": 123,
    "result": {
        "uri": "screen://capture/abc123",
        "binary": true,
        "size": 245678,
        "mimeType": "image/png",
        "message": "Binary data sent separately"
    }
}
```

## Example Usage

### Capture Screen and Receive Binary Image

```python
import asyncio
import websockets
import json

async def capture_screen():
    uri = "ws://localhost:8000/mcp/ws/mcp"

    async with websockets.connect(uri) as ws:
        # Wait for welcome
        await ws.recv()

        # Initialize
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }))
        await ws.recv()

        # Call capture_screen tool (with include_image=False for binary transfer)
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "capture_screen",
                "arguments": {
                    "monitor": 0,
                    "format": "png",
                    "include_image": False  # Return URI only, not base64
                }
            }
        }))

        # Get tool result (contains resource URI in JSON)
        result = json.loads(await ws.recv())
        result_text = result.get("result", {}).get("content", [{}])[0].get("text", "")
        result_json = json.loads(result_text)

        if result_json.get("success"):
            resource_uri = result_json.get("resource_uri")
            print(f"✓ Resource URI: {resource_uri}")

            # Request resource (this triggers binary transfer)
            await ws.send(json.dumps({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "resources/read",
                "params": {"uri": resource_uri}
            }))

            # Receive metadata
            metadata = json.loads(await ws.recv())
            print(f"Receiving {metadata['size']} bytes...")

            # Receive BINARY data (no base64 decoding needed!)
            binary_data = await ws.recv()  # This is bytes, not string!

            # Receive acknowledgment
            ack = json.loads(await ws.recv())

            # Save image
            with open("screenshot.png", "wb") as f:
                f.write(binary_data)

            print(f"✓ Saved {len(binary_data)} bytes to screenshot.png")
        else:
            print(f"✗ Capture failed: {result_text}")

asyncio.run(capture_screen())
```

## Performance Comparison

### Payload Size

For a typical 1920x1080 PNG screenshot (~2.5 MB):

| Transport | Size | Overhead |
|-----------|------|----------|
| **WebSocket Binary** | 2,500,000 bytes | 0% |
| **SSE Base64** | 3,333,333 bytes | +33% |

**WebSocket saves ~833 KB per capture!**

### CPU Usage

Encoding/decoding overhead eliminated:

```
SSE/HTTP:   bytes → base64 → JSON → network → JSON → base64 → bytes
WebSocket:  bytes → network → bytes  ✓ No conversion!
```

### Latency

For 60 FPS streaming (16.67ms per frame):

| Operation | SSE | WebSocket | Savings |
|-----------|-----|-----------|---------|
| Encode | ~2ms | 0ms | 2ms |
| Transfer | ~8ms | ~6ms | 2ms |
| Decode | ~2ms | 0ms | 2ms |
| **Total** | **~12ms** | **~6ms** | **50% faster** |

## Test Client

A complete test client is provided:

```bash
# Install websockets library
pip install websockets

# Run test client
python test_mcp_websocket.py
```

The test client demonstrates:
- Connection and initialization
- Listing tools and resources
- Capturing screen
- Receiving binary resources
- Size comparison (binary vs base64)
- Saving binary data to file

## API Reference

### Endpoints

- **WebSocket**: `ws://localhost:8000/mcp/ws/mcp`
- **Stats**: `GET http://localhost:8000/mcp/ws/mcp/stats`

### Capabilities

The server advertises binary resource support:

```json
{
    "experimental": {
        "binaryResources": true
    }
}
```

### Supported Methods

All standard MCP methods are supported:

- `initialize`
- `tools/list`
- `tools/call`
- `resources/list`
- `resources/read` (returns BINARY data)
- `prompts/list`
- `prompts/get`
- Notifications

## Streaming

For real-time screen streaming, use auto-push:

1. Create a stream:
```python
await ws.send(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "create_stream",
        "arguments": {"monitor": 0, "fps": 30, "format": "jpeg"}
    }
}))
```

2. Start auto-push:
```python
await ws.send(json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
        "name": "start_auto_push_stream",
        "arguments": {"stream_id": "...", "fps": 30}
    }
}))
```

3. Receive frames as binary:
```python
while True:
    msg = await ws.recv()
    if isinstance(msg, bytes):
        # Binary frame data
        process_frame(msg)
    else:
        # Metadata or other JSON
        handle_message(json.loads(msg))
```

## Security Considerations

### CORS

The server includes CORS middleware for cross-origin requests.

### Authentication

For production, add authentication:

```python
# In your client
headers = {
    "Authorization": "Bearer your-api-key"
}

async with websockets.connect(uri, extra_headers=headers) as ws:
    # ...
```

### WSS (Secure WebSocket)

For production, use WSS with TLS:

```bash
# Use nginx or similar as reverse proxy
ws://localhost:8000/mcp/ws/mcp  # Development
wss://your-domain.com/mcp/ws/mcp  # Production
```

## Troubleshooting

### Connection Refused

```
Error: Connection refused to ws://localhost:8000/mcp/ws/mcp
```

**Solution**: Make sure the HTTP server is running:
```bash
python -m screenmonitormcp_v2
```

### Binary Data Not Received

If you only receive text frames, check:

1. Server advertises `binaryResources: true`
2. Using `resources/read` method (not direct tool calls)
3. WebSocket client properly handles binary frames

### Performance Issues

For high-FPS streaming (60+):

1. Use JPEG format instead of PNG
2. Lower quality setting (50-75)
3. Use binary WebSocket (not SSE)
4. Enable frame skipping

## Comparison: All Transports

| Feature | stdio | SSE | WebSocket |
|---------|-------|-----|-----------|
| **Use Case** | Claude Desktop | Web/Remote | Real-time apps |
| **Direction** | Bidirectional | Server→Client | Bidirectional |
| **Binary Support** | ✓ Yes | ✗ No (base64) | ✓ Yes (native) |
| **Streaming** | Manual | Auto-push | Auto-push |
| **Overhead** | Minimal | +33% (base64) | Minimal |
| **Setup** | Simple | Medium | Medium |

## When to Use WebSocket

**Use WebSocket transport when:**

- ✓ High-frequency streaming (30+ FPS)
- ✓ Real-time applications
- ✓ Bandwidth-constrained environments
- ✓ CPU efficiency is critical
- ✓ Web/mobile clients

**Use SSE when:**

- Web browsers without WebSocket support
- Simple request/response patterns
- Don't need binary transfer

**Use stdio when:**

- Claude Desktop integration
- Command-line tools
- Local-only usage

## Examples

See `test_mcp_websocket.py` for a complete working example.

## Contributing

To add binary resource support to custom tools:

```python
@mcp.resource("custom://data/{id}")
async def get_custom_data(data_id: str) -> bytes:
    """Return raw bytes for WebSocket binary transfer."""
    # FastMCP will automatically:
    # - Send as binary over WebSocket
    # - Encode as base64 over SSE/HTTP
    return raw_binary_data
```

The framework handles transport-specific encoding automatically!

## License

MIT License - See LICENSE file for details.

---

**ScreenMonitorMCP v2** - High-performance screen monitoring with AI vision capabilities
