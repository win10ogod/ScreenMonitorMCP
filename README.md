# ScreenMonitorMCP v2

[![Version](https://img.shields.io/badge/version-2.0.7-blue.svg)](https://github.com/inkbytefo/ScreenMonitorMCP/releases/tag/v2.0.7)
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

### Recommended (Client-Side Analysis)

- **`capture_screen_image`** - Capture screenshot and return raw image data for your AI client to analyze
  - No API keys required
  - More secure and private
  - Uses your MCP client's built-in vision capabilities

### Streaming & Monitoring

- `create_stream` - Start live screen streaming
- `list_streams` - List active streams
- `stop_stream` - Stop a stream
- `get_performance_metrics` - System health monitoring
- `get_system_status` - Overall system status

### Legacy Tools (Deprecated - Require External AI API)

- `analyze_screen` - Server-side AI analysis (deprecated)
- `detect_ui_elements` - UI element detection (deprecated)
- `assess_system_performance` - Performance assessment (deprecated)
- `detect_anomalies` - Anomaly detection (deprecated)
- `generate_monitoring_report` - Generate reports (deprecated)
- `chat_completion` - Chat completion (deprecated)

**Note:** Legacy tools are maintained for backward compatibility but are not recommended for new implementations.

## Use Cases

- **UI/UX Analysis**: Get AI insights on interface design and usability
- **Debugging Assistance**: Visual debugging with AI-powered error detection
- **Content Creation**: Automated screenshot documentation and analysis
- **Accessibility Testing**: Screen reader and accessibility compliance checking
- **System Monitoring**: Visual system health and performance tracking

## Documentation

For detailed setup instructions and advanced configuration, see our [MCP Setup Guide](MCP_SETUP_GUIDE.md).

## Requirements

- Python 3.8+
- OpenAI API key (or compatible service)
- MCP-compatible client (Claude Desktop, etc.)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Previous Version

Looking for v1? Check the [v1 branch](https://github.com/inkbytefo/ScreenMonitorMCP/tree/v1) for the previous version.

---

**Built with ❤️ by [inkbytefo](https://github.com/inkbytefo)**
