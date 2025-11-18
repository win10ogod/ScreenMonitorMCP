"""
ScreenMonitorMCP v2 - Streamable HTTP/SSE Architecture

Revolutionary AI Vision Server with modern HTTP/SSE/WebSocket transport.
"""

__version__ = "2.6.0"
__author__ = "inkbytefo"
__email__ = "inkbytefo@gmail.com"
__license__ = "MIT"

# Lazy import for HTTP server components to support MCP-only mode
# MCP mode doesn't require HTTP server dependencies
def create_app(*args, **kwargs):
    """Create HTTP/SSE server application (lazy import).

    This import is deferred to allow MCP-only mode without HTTP dependencies.
    """
    from .server.app import create_app as _create_app
    return _create_app(*args, **kwargs)

__all__ = ["create_app"]
