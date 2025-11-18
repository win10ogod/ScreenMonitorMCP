# MCP over SSE (Server-Sent Events) Guide

## Overview

ScreenMonitorMCP v2.5+ supports **two MCP transport modes**:

1. **stdio (Standard Input/Output)** - Local connections via process pipes
2. **SSE (Server-Sent Events)** - Remote connections via HTTP

This guide explains how to use MCP over SSE for remote connections.

## Why MCP over SSE?

**stdio Mode Limitations:**
- Only works locally (same machine)
- One client per server process
- Requires process spawning

**SSE Mode Benefits:**
- ✅ Remote connections over network
- ✅ Multiple clients can connect simultaneously
- ✅ Auto-push streaming (frames sent automatically)
- ✅ Works with web-based MCP clients
- ✅ Same server also provides REST API and WebSocket

## Installation

Install with HTTP dependencies:

```bash
# From PyPI
pip install screenmonitormcp-v2[http]

# Or with all dependencies
pip install screenmonitormcp-v2[all]

# From source
git clone https://github.com/inkbytefo/ScreenMonitorMCP.git
cd ScreenMonitorMCP
pip install -e ".[http]"
```

## Server Setup

### 1. Start HTTP Server

```bash
python -m screenmonitormcp_v2
```

Server starts at `http://localhost:8000`

**Server endpoints:**
- `http://localhost:8000/` - Server info
- `http://localhost:8000/mcp/sse` - MCP SSE endpoint
- `http://localhost:8000/mcp/messages` - MCP messages endpoint
- `http://localhost:8000/api/v2` - REST API
- `http://localhost:8000/ws` - WebSocket
- `http://localhost:8000/docs` - API documentation

### 2. Environment Variables (Optional)

Create `.env` file:

```env
# Server
HOST=0.0.0.0
PORT=8000

# Performance
MAX_STREAM_FPS=10
MAX_STREAM_QUALITY=75
MAX_CONCURRENT_STREAMS=25
```

## Client Configuration

### Claude Desktop

If your Claude Desktop client supports SSE transport:

```json
{
  "mcpServers": {
    "screenmonitormcp-v2": {
      "transport": "sse",
      "url": "http://localhost:8000/mcp",
      "timeout": 30000
    }
  }
}
```

**Note:** Claude Desktop (as of Dec 2024) primarily supports stdio transport. SSE support depends on your client version.

### Custom MCP Client

Using the MCP Python SDK:

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://localhost:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print("Available tools:", [tool.name for tool in tools.tools])

            # Capture screen
            result = await session.call_tool("capture_screen", {
                "monitor": 0,
                "format": "png",
                "quality": 85
            })
            print("Screen captured:", result)

asyncio.run(main())
```

### Using curl (for testing)

**Connect to SSE endpoint:**
```bash
curl -N -H "Accept: text/event-stream" http://localhost:8000/mcp/sse
```

**Send MCP message:**
```bash
curl -X POST http://localhost:8000/mcp/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

**Call a tool:**
```bash
curl -X POST http://localhost:8000/mcp/messages \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "capture_screen",
      "arguments": {
        "monitor": 0,
        "format": "png",
        "quality": 85
      }
    }
  }'
```

## Features Comparison

| Feature | stdio Mode | SSE Mode |
|---------|-----------|----------|
| **Connection** | Local only | Remote via HTTP |
| **Clients** | One per process | Multiple simultaneous |
| **Screen Capture** | ✅ `capture_screen` | ✅ `capture_screen` |
| **Manual Frame Capture** | ✅ `capture_stream_frame` | ✅ `capture_stream_frame` |
| **Auto-Push Streaming** | ❌ Not available | ✅ `start_auto_push_stream` |
| **Resources API** | ✅ Supported | ✅ Supported |
| **Prompts** | ✅ Available | ✅ Available |
| **REST API** | ❌ Not available | ✅ Available |
| **WebSocket** | ❌ Not available | ✅ Available |

## Auto-Push Streaming (SSE Mode Only)

One of the key benefits of SSE mode is automatic frame pushing:

### stdio Mode (Manual)
```
1. create_stream(monitor=0, fps=10)
2. capture_stream_frame(stream_id)  ← Manual call
3. capture_stream_frame(stream_id)  ← Manual call
4. capture_stream_frame(stream_id)  ← Manual call
5. stop_stream(stream_id)
```

### SSE Mode (Auto-Push)
```
1. create_stream(monitor=0, fps=10)
2. start_auto_push_stream(stream_id, fps=5)
3. (Frames arrive automatically every 200ms)
4. stop_auto_push_stream_tool(stream_id)
5. stop_stream(stream_id)
```

### Auto-Push Example

```python
async with ClientSession(read, write) as session:
    # Create stream
    result = await session.call_tool("create_stream", {
        "monitor": 0,
        "fps": 10,
        "quality": 75,
        "format": "jpeg"
    })
    stream_id = result.content[0].text.split(": ")[1]

    # Start auto-push
    await session.call_tool("start_auto_push_stream", {
        "stream_id": stream_id,
        "fps": 5
    })

    # Frames arrive automatically via SSE notifications
    # Listen for 'notifications/resources/updated' events

    # Stop auto-push
    await session.call_tool("stop_auto_push_stream_tool", {
        "stream_id": stream_id
    })

    # Stop stream
    await session.call_tool("stop_stream", {
        "stream_id": stream_id
    })
```

## Security Considerations

### Network Security

When running SSE mode:

1. **Local network only** (default: `HOST=0.0.0.0`)
2. **Firewall**: Restrict port 8000 to trusted IPs
3. **HTTPS**: Use reverse proxy (nginx/caddy) for production
4. **API Keys**: Configure if exposing to network

### HTTPS Setup with nginx

```nginx
server {
    listen 443 ssl;
    server_name screenmonitor.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /mcp/ {
        proxy_pass http://localhost:8000/mcp/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;

        # SSE specific
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header X-Accel-Buffering no;
    }
}
```

## Troubleshooting

### Connection Issues

**Problem:** Client can't connect to SSE endpoint

**Solution:**
```bash
# Check if server is running
curl http://localhost:8000/

# Check if SSE endpoint is available
curl -v http://localhost:8000/mcp/sse
```

### Auto-Push Not Working

**Problem:** `start_auto_push_stream` returns error

**Causes:**
1. Not running in SSE mode (using stdio instead)
2. Stream doesn't exist
3. HTTP dependencies not installed

**Solution:**
```bash
# Ensure HTTP dependencies installed
pip install screenmonitormcp-v2[http]

# Start server (not mcp_main)
python -m screenmonitormcp_v2

# Verify stream exists first
create_stream(monitor=0, fps=10)
```

### Port Already in Use

**Problem:** `Address already in use` error

**Solution:**
```bash
# Use different port
PORT=8001 python -m screenmonitormcp_v2

# Or kill existing process
lsof -ti:8000 | xargs kill -9
```

## Performance Tuning

### Optimize for High FPS

```env
# In .env file
MAX_STREAM_FPS=30
MAX_STREAM_QUALITY=60
MAX_CONCURRENT_STREAMS=5

# Windows optimization
# Install GPU-accelerated capture
pip install screenmonitormcp-v2[windows-all]
```

### Optimize for Multiple Clients

```env
MAX_CONNECTIONS=100
CONNECTION_TIMEOUT=30
REQUEST_TIMEOUT=60
```

## Examples

### Full Auto-Push Workflow

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def auto_push_example():
    async with sse_client("http://localhost:8000/mcp") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Create stream
            print("Creating stream...")
            result = await session.call_tool("create_stream", {
                "monitor": 0,
                "fps": 10,
                "quality": 75
            })
            stream_id = result.content[0].text.split(": ")[1]
            print(f"Stream created: {stream_id}")

            # Start auto-push
            print("Starting auto-push...")
            await session.call_tool("start_auto_push_stream", {
                "stream_id": stream_id,
                "fps": 5
            })

            # Wait for frames (they arrive automatically via SSE)
            print("Receiving frames for 10 seconds...")
            await asyncio.sleep(10)

            # Stop auto-push
            print("Stopping auto-push...")
            await session.call_tool("stop_auto_push_stream_tool", {
                "stream_id": stream_id
            })

            # Stop stream
            print("Stopping stream...")
            await session.call_tool("stop_stream", {
                "stream_id": stream_id
            })

            print("Done!")

asyncio.run(auto_push_example())
```

## Migration from stdio to SSE

### Before (stdio)
```json
{
  "mcpServers": {
    "screenmonitormcp-v2": {
      "command": "python",
      "args": ["-m", "screenmonitormcp_v2.mcp_main"]
    }
  }
}
```

### After (SSE)
```json
{
  "mcpServers": {
    "screenmonitormcp-v2": {
      "transport": "sse",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Additional steps:**
1. Install HTTP dependencies: `pip install screenmonitormcp-v2[http]`
2. Start HTTP server: `python -m screenmonitormcp_v2`
3. Keep server running while using MCP client

## Support

- **Issues**: https://github.com/inkbytefo/ScreenMonitorMCP/issues
- **Documentation**: https://github.com/inkbytefo/ScreenMonitorMCP/
- **MCP Specification**: https://modelcontextprotocol.io/

---

**Last Updated:** 2025-11-18
**Version:** 2.5.0
