# MCP Binary Transfer - Usage Guide

## 🎯 Unified Resource-Based Transfer

ScreenMonitorMCP v2 uses the **standard MCP resource protocol** for all image transfers.

### Single Workflow for All Transports

```
1. Call tool (capture_screen) → Get resource_uri
2. Call resources/read(uri) → Get image data
```

The transport automatically optimizes the data format:
- **WebSocket**: Binary PNG/JPEG bytes (no base64) - **33% smaller!**
- **SSE/HTTP**: Base64 encoded (JSON compatible)
- **stdio**: Standard MCP resource protocol

### Benefits

- ✅ **Consistent API** - Same workflow everywhere
- ✅ **Automatic optimization** - Binary on WebSocket, base64 on SSE
- ✅ **MCP standard** - Follows protocol specifications
- ✅ **No confusion** - One clear way to get images

---

## 📖 WebSocket Binary Transfer

### Complete Example

```python
import asyncio
import websockets
import json

async def capture_with_binary():
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

        # ====================================
        # STEP 1: Get resource URI
        # ====================================
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "capture_screen",
                "arguments": {
                    "monitor": 0,
                    "format": "png"
                }
            }
        }))

        response = json.loads(await ws.recv())
        result_text = response["result"]["content"][0]["text"]
        result_json = json.loads(result_text)

        resource_uri = result_json["resource_uri"]
        print(f"Got URI: {resource_uri}")

        # ====================================
        # STEP 2: Fetch as BINARY
        # ====================================
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",
            "params": {"uri": resource_uri}
        }))

        # Receive 3 messages:
        metadata = json.loads(await ws.recv())      # 1. Metadata (JSON)
        binary_data = await ws.recv()              # 2. Binary image (bytes!)
        ack = json.loads(await ws.recv())          # 3. Acknowledgment (JSON)

        # Save directly - NO BASE64 DECODING!
        with open("screenshot.png", "wb") as f:
            f.write(binary_data)

        print(f"Saved {len(binary_data):,} bytes")

asyncio.run(capture_with_binary())
```

---

## ⚡ Performance Comparison

### Data Flow

**WebSocket (Efficient):**
```
Screen → PNG bytes → WebSocket binary frame → Client
                          ↓
                   NO ENCODING!
```

**SSE/HTTP (Compatible):**
```
Screen → PNG bytes → base64 encode → JSON → Client → base64 decode → PNG bytes
                         ↓                               ↓
                    +33% larger                     CPU overhead
```

### Size Example

For a 1920x1080 PNG screenshot:

| Transport | Payload Size | Overhead |
|-----------|--------------|----------|
| **WebSocket Binary** | 2,500,000 bytes | 0% |
| **SSE Base64** | 3,333,333 bytes | **+33%** |
| **Savings** | **833 KB** | - |

### Speed Example

For 60 FPS streaming (16.67ms per frame):

| Operation | WebSocket | SSE | Savings |
|-----------|-----------|-----|---------|
| Encode | 0ms | ~2ms | 2ms |
| Transfer | ~6ms | ~8ms | 2ms |
| Decode | 0ms | ~2ms | 2ms |
| **Total** | **~6ms** | **~12ms** | **50% faster!** |

---

## 🎮 When to Use Each Transport

### Use WebSocket When:
- ✅ High-frequency streaming (30+ FPS)
- ✅ Real-time applications
- ✅ Bandwidth is limited
- ✅ CPU efficiency is critical
- ✅ Remote connections

### Use SSE When:
- ✅ Simple web clients
- ✅ One-way server push needed
- ✅ Firewall restrictions on WebSocket

### Use stdio When:
- ✅ Claude Desktop integration
- ✅ Command-line tools
- ✅ Local-only usage

---

## 🔧 Quick Reference

### Workflow (All Transports)

```python
# Step 1: Get URI
capture_screen(monitor=0)
→ Returns: {"resource_uri": "screen://capture/abc123"}

# Step 2: Fetch image
resources/read(uri="screen://capture/abc123")
→ Returns:
  - WebSocket: binary bytes
  - SSE: base64 string
  - stdio: per MCP protocol
```

### Important Rules

1. **Tools always return text** (JSON or Markdown)
2. **Resources can return binary** (WebSocket only)
3. **Use resources/read, not tools/call** for image data
4. **Two-step process required** for all image transfers

---

## 📝 Complete Test Example

See `simple_websocket_binary_test.py` for a working example:

```bash
# Install dependencies
pip install websockets

# Run test
python simple_websocket_binary_test.py
```

Output shows:
- ✅ Resource URI received
- ✅ Binary transfer (bytes type)
- ✅ File saved successfully
- ✅ Size comparison (binary vs base64)

---

## 🐛 Troubleshooting

### Q: Still getting base64 data?

**A:** You're probably calling the tool and expecting binary directly.

❌ **Wrong:**
```python
capture_screen()  # Returns JSON text with URI
```

✅ **Correct:**
```python
# Step 1: Get URI
capture_screen() → {"resource_uri": "screen://..."}

# Step 2: Fetch binary
resources/read(uri="screen://...") → binary bytes
```

### Q: How do I know if I got binary?

**A:** Check the data type:

```python
data = await ws.recv()

if isinstance(data, bytes):
    print("✓ Got binary data!")
else:
    print("✗ Got text, need resources/read")
```

### Q: Can I use this with Claude Desktop?

**A:** Yes! Claude Desktop's MCP client handles resources/read automatically. Just call `capture_screen()` and it will fetch the resource for you.

---

## 📚 Related Documentation

- `MCP_WEBSOCKET_GUIDE.md` - Complete WebSocket transport guide
- `simple_websocket_binary_test.py` - Working example code
- `test_mcp_websocket.py` - Comprehensive test suite
- `README.md` - General project documentation

---

**Last Updated:** 2025-11-20
**Version:** 2.5.0

**Key Change:** Removed `include_image` parameter. All image transfers now use the standard two-step resource protocol for consistency and clarity.
