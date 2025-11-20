# MCP Binary Transfer - Usage Guide

## 🎯 Two Modes of Operation

ScreenMonitorMCP v2 now supports **two modes** for image transfer:

### 1. **Binary Mode** (WebSocket/SSE) - RECOMMENDED for remote connections
- Returns only resource URI
- Fetch image via `resources/read` as binary data
- **No base64 encoding** → 33% smaller payloads
- **Lower CPU usage** → No encode/decode overhead
- **Default mode** (when `include_image=False`)

### 2. **Embedded Mode** (stdio/Claude Desktop) - For local clients
- Returns image embedded in response as base64 data URL
- Image displays immediately in Claude Desktop
- Larger payload but works in text-only environments
- Use when `include_image=True`

---

## 📖 How to Use Each Mode

### Binary Mode (WebSocket - Recommended)

**Step 1: Capture screen without embedded image**
```python
await ws.send(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "capture_screen",
        "arguments": {
            "monitor": 0,
            "format": "png",
            "include_image": False  # ← KEY: Return URI only
        }
    }
}))
```

**Response:**
```json
{
  "success": true,
  "resource_uri": "screen://capture/abc123",
  "mime_type": "image/png",
  "metadata": {
    "timestamp": "2025-11-20T10:30:00Z",
    "width": 1920,
    "height": 1080
  },
  "message": "Use resources/read with this URI to fetch binary image data",
  "binary_transfer": true
}
```

**Step 2: Fetch resource as binary**
```python
# Send resources/read request
await ws.send(json.dumps({
    "jsonrpc": "2.0",
    "id": 2,
    "method": "resources/read",
    "params": {"uri": "screen://capture/abc123"}
}))

# Receive metadata (JSON text frame)
metadata = json.loads(await ws.recv())
# {
#   "type": "resource_metadata",
#   "uri": "screen://capture/abc123",
#   "mimeType": "image/png",
#   "size": 2500000
# }

# Receive binary data (binary frame - NO BASE64!)
binary_data = await ws.recv()  # bytes object

# Receive acknowledgment (JSON text frame)
ack = json.loads(await ws.recv())

# Save directly
with open("screenshot.png", "wb") as f:
    f.write(binary_data)
```

---

### Embedded Mode (stdio/Claude Desktop)

**Step 1: Capture screen with embedded image**
```python
await ws.send(json.dumps({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "capture_screen",
        "arguments": {
            "monitor": 0,
            "format": "png",
            "include_image": True  # ← Embed base64 image
        }
    }
}))
```

**Response:**
```markdown
✅ Screen captured successfully!

**Metadata:**
- Monitor: 0
- Format: png
- Size: 1920x1080
- Timestamp: 2025-11-20T10:30:00Z
- Resource URI: `screen://capture/abc123`

**Image:**
![Screenshot](data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...)

The screenshot is embedded above. The image can also be accessed later via the resource URI: `screen://capture/abc123`
```

The image displays immediately in Claude Desktop UI.

---

## ⚡ Performance Comparison

### Data Flow

**Binary Mode (Efficient):**
```
Screen → PNG bytes → Cache → WebSocket binary frame → Client
                                  ↓
                          NO ENCODING/DECODING!
```

**Embedded Mode (Compatible):**
```
Screen → PNG bytes → base64 encode → JSON → WebSocket text → base64 decode → PNG bytes
                         ↓                                        ↓
                    +33% larger                              CPU overhead
```

### Size Example

For a 1920x1080 PNG screenshot:

| Mode | Payload Size | Overhead |
|------|--------------|----------|
| **Binary** | 2,500,000 bytes | 0% |
| **Embedded** | 3,333,333 bytes | **+33%** |
| **Savings** | **833 KB** | - |

### Speed Example

For 60 FPS streaming:

| Operation | Binary Mode | Embedded Mode | Savings |
|-----------|-------------|---------------|---------|
| Encode | 0ms | ~2ms | 2ms |
| Transfer | ~6ms | ~8ms | 2ms |
| Decode | 0ms | ~2ms | 2ms |
| **Total** | **~6ms** | **~12ms** | **50% faster!** |

---

## 🎮 When to Use Each Mode

### Use Binary Mode (include_image=False) When:
- ✅ Using WebSocket or SSE transport
- ✅ High-frequency streaming (30+ FPS)
- ✅ Bandwidth is limited
- ✅ CPU efficiency is critical
- ✅ Remote connections
- ✅ Production deployments

### Use Embedded Mode (include_image=True) When:
- ✅ Using stdio transport (Claude Desktop)
- ✅ Need immediate display in chat UI
- ✅ Text-only environment
- ✅ Single screenshot (not streaming)
- ✅ Local development/testing

---

## 🔧 Quick Reference

### Binary Mode Workflow

```python
# 1. Capture (URI only)
capture_screen(monitor=0, include_image=False)
→ Returns: {"resource_uri": "screen://capture/abc123", ...}

# 2. Fetch binary
resources/read(uri="screen://capture/abc123")
→ Returns: binary PNG/JPEG data (no encoding!)

# 3. Use directly
save_to_file(binary_data)
```

### Embedded Mode Workflow

```python
# 1. Capture (with image)
capture_screen(monitor=0, include_image=True)
→ Returns: Markdown with embedded base64 image

# 2. Display immediately
Claude Desktop shows image in chat
```

---

## 📝 Complete Example

See `test_mcp_websocket.py` for a complete working example that:
1. Connects to WebSocket MCP server
2. Calls `capture_screen(include_image=False)`
3. Extracts resource URI from JSON response
4. Fetches resource via `resources/read`
5. Receives binary data (3 frames: metadata, binary, ack)
6. Saves to file
7. Shows size comparison

Run it:
```bash
pip install websockets
python test_mcp_websocket.py
```

---

## 🚀 Best Practices

1. **Default to Binary Mode** for WebSocket/SSE connections
2. **Use Embedded Mode** only for stdio/Claude Desktop
3. **Monitor payload sizes** with `/mcp/ws/mcp/stats`
4. **Use JPEG format** for streaming (smaller than PNG)
5. **Lower quality** (50-75) for high FPS
6. **Cache resource URIs** for later fetch if needed

---

## 🐛 Troubleshooting

### Still getting base64 data?

**Problem:** Calling `capture_screen()` without `include_image=False`

**Solution:**
```python
# ✗ Wrong - uses default (now False, but be explicit)
capture_screen(monitor=0)

# ✓ Correct - explicitly request binary mode
capture_screen(monitor=0, include_image=False)
```

### How do I know if binary mode is active?

Check the tool response:
```json
{
  "success": true,
  "resource_uri": "screen://capture/abc123",
  "binary_transfer": true  ← This indicates binary mode
}
```

### WebSocket returns text, not binary?

You need **two steps**:
1. Call `capture_screen(include_image=False)` → get URI
2. Call `resources/read(uri=...)` → get binary

Don't expect binary from `capture_screen` directly!

---

## 📚 Related Documentation

- `MCP_WEBSOCKET_GUIDE.md` - Complete WebSocket transport guide
- `test_mcp_websocket.py` - Working example code
- `README.md` - General project documentation

---

**Last Updated:** 2025-11-20
**Version:** 2.5.0
