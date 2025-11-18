# ScreenMonitorMCP v2

[![Version](https://img.shields.io/badge/version-2.5.0-blue.svg)](https://github.com/inkbytefo/ScreenMonitorMCP/releases/tag/v2.5.0)
[![PyPI](https://img.shields.io/pypi/v/screenmonitormcp-v2.svg)](https://pypi.org/project/screenmonitormcp-v2/)
[![Python](https://img.shields.io/pypi/pyversions/screenmonitormcp-v2.svg)](https://pypi.org/project/screenmonitormcp-v2/)
[![Verified on MseeP](https://mseep.ai/badge.svg)](https://mseep.ai/app/a2dbda0f-f46d-40e1-9c13-0b47eff9df3a)
[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/inkbytefo-screenmonitormcp-badge.png)](https://mseep.ai/app/inkbytefo-screenmonitormcp)

A powerful Model Context Protocol (MCP) server that gives AI assistants real-time vision capabilities through screen capture. Let your AI see your screen - the AI assistant analyzes what it sees using its own vision capabilities.

## 🎯 Recommended Architecture (v2.1+)

**ScreenMonitorMCP now follows MCP best practices:**
- **Server captures** screenshots and returns raw image data
- **Your MCP client** (like Claude Desktop) analyzes images with its own vision model
- **No external AI APIs** required - more secure, simpler, and privacy-focused
- **No API key management** - works out of the box

This approach is more secure, conventional, and follows the Model Context Protocol philosophy.

## What is ScreenMonitorMCP?

ScreenMonitorMCP v2 is a revolutionary MCP server that bridges the gap between AI and visual computing. It enables AI assistants to capture screenshots, analyze screen content, and provide intelligent insights about what's happening on your display.

## Key Features

- **Real-time Screen Capture**: Instant screenshot capabilities across multiple monitors
- **AI-Powered Analysis**: Advanced screen content analysis using state-of-the-art vision models
- **Streaming Support**: Live screen streaming for continuous monitoring
- **Performance Monitoring**: Built-in system health and performance metrics
- **Multi-Platform**: Works seamlessly on Windows, macOS, and Linux
- **Easy Integration**: Simple setup with Claude Desktop and other MCP clients

## 🚀 Windows Performance Optimization (v2.5+)

**NEW:** Ultra-fast GPU-accelerated screen capture for Windows users!

ScreenMonitorMCP v2.5+ includes optional Windows-specific optimizations for **4-50x faster** screen capture:

### Performance Comparison

| Method | Capture Time | Technology | Use Case |
|--------|-------------|------------|----------|
| **MSS (Default)** | 20-50ms | CPU (GDI BitBlt) | Cross-platform, compatibility |
| **DXGI** | 1-5ms ⚡ | GPU (DirectX) | High-performance capture, gaming |
| **WGC** | 1-5ms ⚡ | GPU (DirectX, Secure) | Secure apps, window capture |

### Installation (Optional)

Windows optimization works automatically if you install the optional packages:

```bash
# For DXGI Desktop Duplication (240+ FPS capable - RECOMMENDED):
pip install screenmonitormcp-v2[windows-perf]

# For Windows Graphics Capture (async-based, modern API):
pip install screenmonitormcp-v2[windows-wgc]

# Install both for maximum compatibility:
pip install screenmonitormcp-v2[windows-all]
```

**Implementation Status:**
- ✅ **DXGI (via dxcam)**: Fully implemented - 1-5ms capture, 240+ FPS, multi-monitor
- ✅ **WGC (via winsdk)**: Fully implemented - 1-5ms async capture, modern API
- ✅ **MSS**: Always available - 20-50ms CPU-based capture

**Note**: These packages are optional. ScreenMonitorMCP works perfectly without them using the cross-platform MSS backend.

### Benefits

- ✅ **4-50x Faster**: 1-5ms capture vs 20-50ms with traditional methods
- ✅ **Lower CPU Usage**: 70-90% reduction in CPU overhead
- ✅ **Better Quality**: Captures DirectX/OpenGL/Vulkan hardware-accelerated content
- ✅ **Automatic**: No configuration needed - detects and uses best available method
- ✅ **Secure**: WGC requires user authorization for screen access

### Check Your Backend

Use the `get_capture_backend_info()` MCP tool to see which backend is active:

```
Active Backend: wgc (Windows Graphics Capture)
Performance: 1-5ms per capture
Windows Optimization: Active ✓
```

## Quick Start

### Installation

```bash
# Install from PyPI
pip install screenmonitormcp

# Or install from source
git clone https://github.com/inkbytefo/screenmonitormcp.git
cd screenmonitormcp
pip install -e .
```

### Configuration

**Recommended (Simpler & More Secure):**

Add to your Claude Desktop config - No API keys needed!

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

Restart Claude Desktop and start using:
- Use `capture_screen_image` tool to capture screenshots
- Claude will analyze the images with its own vision model
- No configuration, no API keys, no complexity!

**Alternative (Legacy - Requires External AI API):**

If you want to use the deprecated server-side AI analysis tools, configure:

```json
{
  "mcpServers": {
    "screenmonitormcp-v2": {
      "command": "python",
      "args": ["-m", "screenmonitormcp_v2.mcp_main"],
      "env": {
        "OPENAI_API_KEY": "your-openai-api-key-here",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_MODEL": "gpt-4o"
      }
    }
  }
}
```

Note: This approach is deprecated. Use the recommended client-side analysis instead.

## Available Tools

### Screen Capture

- **`capture_screen`** - Capture screenshot and return MCP Resource URI
  - Returns tiny response (~200 bytes) with resource URI
  - Client fetches image via MCP Resources API automatically
  - **Eliminates token explosion** - no large data in responses
  - No API keys required, uses your MCP client's built-in vision
  - Cache keeps last 10 captures for resource requests
  - **This is the ONLY way to capture screens** - simple and efficient

### System Monitoring

- `get_performance_metrics` - System health and performance metrics
- `get_system_status` - Overall system status
- `get_capture_backend_info` - Screenshot backend status (MSS/DXGI/WGC)

### Streaming (HTTP Mode Only)

**Note**: Streaming is designed for HTTP/WebSocket mode. For MCP mode, use `capture_screen` for single screenshots.

- `create_stream` - Start live screen streaming (HTTP mode)
- `list_streams` - List active streams
- `stop_stream` - Stop a stream
- `get_stream_info` - Get stream information

### Memory & Database

- `get_memory_statistics` - Memory system statistics
- `get_memory_usage` - Detailed memory usage
- `get_database_pool_stats` - Database connection pool statistics
- `database_pool_health_check` - Database health check

### Backend Information

- `get_capture_backend_info` - Screen capture backend status (MSS/DXGI/WGC)

## Use Cases

- **Screen Analysis**: Capture screenshots for AI client analysis (Claude Desktop, etc.)
- **Debugging Assistance**: Visual debugging with screenshot capture
- **Content Creation**: Automated screenshot documentation
- **Accessibility Testing**: Screen capture for accessibility review
- **System Monitoring**: Visual system health tracking

## Documentation

For detailed setup instructions and advanced configuration, see our [MCP Setup Guide](MCP_SETUP_GUIDE.md).

## Requirements

- Python 3.10+
- MCP-compatible client (Claude Desktop, etc.)
- **No external API keys required** for MCP mode

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Previous Version

Looking for v1? Check the [v1 branch](https://github.com/inkbytefo/ScreenMonitorMCP/tree/v1) for the previous version.

---

**Built with ❤️ by [inkbytefo](https://github.com/inkbytefo)**
