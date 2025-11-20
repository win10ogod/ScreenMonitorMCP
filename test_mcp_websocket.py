#!/usr/bin/env python3
"""Test client for MCP over WebSocket with binary resource transfer.

This demonstrates how to connect to the MCP WebSocket endpoint and
receive binary resources (screen captures) without base64 encoding overhead.

Benefits over SSE:
- 33% smaller payloads (no base64 expansion)
- Lower CPU usage (no encode/decode)
- Real-time bidirectional communication
"""

import asyncio
import json
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("Error: websockets library not installed")
    print("Install with: pip install websockets")
    sys.exit(1)


class MCPWebSocketClient:
    """MCP client using WebSocket with binary resource support."""

    def __init__(self, url: str = "ws://localhost:8000/mcp/ws/mcp"):
        self.url = url
        self.websocket = None
        self.message_id = 0
        self.pending_resource_metadata = None

    async def connect(self):
        """Connect to MCP WebSocket server."""
        print(f"Connecting to {self.url}...")
        self.websocket = await websockets.connect(self.url)
        print("✓ Connected!")

        # Read welcome message
        welcome = await self.websocket.recv()
        if isinstance(welcome, str):
            msg = json.loads(welcome)
            print(f"✓ Server initialized: {msg.get('params', {}).get('serverInfo', {})}")

    async def send_request(self, method: str, params: dict = None) -> dict:
        """Send MCP JSON-RPC request and wait for response.

        Args:
            method: MCP method name
            params: Method parameters

        Returns:
            Response dict
        """
        self.message_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params or {}
        }

        await self.websocket.send(json.dumps(request))
        print(f"→ Sent: {method}")

        # Wait for response
        response = await self.websocket.recv()

        if isinstance(response, str):
            return json.loads(response)
        else:
            # Got binary data unexpectedly
            print(f"⚠ Received unexpected binary data: {len(response)} bytes")
            return None

    async def read_resource(self, uri: str) -> tuple[dict, bytes]:
        """Read a resource and receive binary data.

        Args:
            uri: Resource URI

        Returns:
            Tuple of (metadata_dict, binary_data)
        """
        self.message_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": "resources/read",
            "params": {"uri": uri}
        }

        await self.websocket.send(json.dumps(request))
        print(f"→ Sent: resources/read for {uri}")

        # Expect metadata first (JSON text frame)
        metadata_msg = await self.websocket.recv()
        if isinstance(metadata_msg, str):
            metadata = json.loads(metadata_msg)
            print(f"✓ Received metadata: {metadata.get('type', 'unknown')}")

            # If it's resource_metadata, expect binary data next
            if metadata.get("type") == "resource_metadata":
                self.pending_resource_metadata = metadata

                # Read binary data
                binary_data = await self.websocket.recv()
                if isinstance(binary_data, bytes):
                    print(f"✓ Received binary data: {len(binary_data)} bytes")

                    # Also expect JSON acknowledgment
                    ack = await self.websocket.recv()
                    if isinstance(ack, str):
                        ack_data = json.loads(ack)
                        print(f"✓ Resource transfer complete: {ack_data.get('result', {})}")

                    return (metadata, binary_data)
                else:
                    print("⚠ Expected binary data but got text")
                    return (metadata, None)
            else:
                # It's the JSON-RPC response (might be error)
                return (metadata, None)
        else:
            print("⚠ Expected metadata but got binary data first")
            return (None, metadata_msg)

    async def close(self):
        """Close WebSocket connection."""
        if self.websocket:
            await self.websocket.close()
            print("✓ Connection closed")


async def main():
    """Main test function."""
    print("=" * 70)
    print("MCP WebSocket Binary Transport Test")
    print("=" * 70)
    print()

    client = MCPWebSocketClient()

    try:
        # Connect
        await client.connect()
        print()

        # Test 1: Initialize
        print("Test 1: Initialize MCP")
        print("-" * 70)
        response = await client.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        })
        print(f"✓ Server capabilities: {list(response.get('result', {}).get('capabilities', {}).keys())}")
        print(f"✓ Binary resources supported: {response.get('result', {}).get('experimental', {}).get('binaryResources', False)}")
        print()

        # Test 2: List tools
        print("Test 2: List Tools")
        print("-" * 70)
        response = await client.send_request("tools/list")
        tools = response.get("result", {}).get("tools", [])
        print(f"✓ Found {len(tools)} tools")
        for tool in tools[:5]:  # Show first 5
            print(f"  - {tool['name']}: {tool['description'][:60]}...")
        if len(tools) > 5:
            print(f"  ... and {len(tools) - 5} more")
        print()

        # Test 3: Capture screen (returns URI only)
        print("Test 3: Capture Screen (Get Resource URI)")
        print("-" * 70)
        response = await client.send_request("tools/call", {
            "name": "capture_screen",
            "arguments": {
                "monitor": 0,
                "format": "png",
                "quality": 85
            }
        })

        # Extract result - should be JSON with resource_uri
        result_text = response.get("result", {}).get("content", [{}])[0].get("text", "")

        # Parse JSON response
        import json as json_module
        try:
            result_json = json_module.loads(result_text)
            if result_json.get("success"):
                resource_uri = result_json.get("resource_uri")
                print(f"✓ Capture successful!")
                print(f"  - Resource URI: {resource_uri}")
                print(f"  - MIME type: {result_json.get('mime_type')}")
                print(f"  - Binary transfer: {result_json.get('binary_transfer')}")
                print(f"  - Size: {result_json['metadata']['width']}x{result_json['metadata']['height']}")
                print()
            else:
                print(f"✗ Capture failed: {result_text[:200]}")
                resource_uri = None
        except json_module.JSONDecodeError:
            print(f"✗ Expected JSON response, got: {result_text[:200]}")
            # Try to extract URI from text (fallback)
            import re
            uri_match = re.search(r'screen://capture/[a-f0-9]+', result_text)
            resource_uri = uri_match.group(0) if uri_match else None
            if resource_uri:
                print(f"✓ Extracted resource URI: {resource_uri}")
                print()

        if resource_uri:

            # Test 4: Read resource as BINARY
            print("Test 4: Read Resource (Binary Transfer)")
            print("-" * 70)
            metadata, binary_data = await client.read_resource(resource_uri)

            if binary_data:
                print(f"✓ Binary transfer successful!")
                print(f"  - MIME type: {metadata.get('mimeType')}")
                print(f"  - Size: {len(binary_data):,} bytes")
                print(f"  - Timestamp: {metadata.get('metadata', {}).get('timestamp')}")
                print()

                # Calculate size comparison
                import base64
                base64_size = len(base64.b64encode(binary_data))
                saving = base64_size - len(binary_data)
                saving_percent = (saving / base64_size) * 100

                print("Size Comparison:")
                print(f"  - Binary (WebSocket): {len(binary_data):,} bytes")
                print(f"  - Base64 (SSE/HTTP): {base64_size:,} bytes")
                print(f"  - Savings: {saving:,} bytes ({saving_percent:.1f}%)")
                print()

                # Save to file (optional)
                output_file = f"test_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                with open(output_file, 'wb') as f:
                    f.write(binary_data)
                print(f"✓ Saved to: {output_file}")
            else:
                print("✗ Failed to receive binary data")
        else:
            print("✗ Could not find resource URI in response")

        print()

        # Test 5: List resources
        print("Test 5: List Resources")
        print("-" * 70)
        response = await client.send_request("resources/list")
        resources = response.get("result", {}).get("resources", [])
        print(f"✓ Found {len(resources)} resource types")
        for resource in resources:
            print(f"  - {resource['name']}: {resource['uri']}")
        print()

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.close()

    print()
    print("=" * 70)
    print("Test Complete!")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
