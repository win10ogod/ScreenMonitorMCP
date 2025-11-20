#!/usr/bin/env python3
"""Simple WebSocket binary transfer example.

This shows the CORRECT way to get binary images via WebSocket MCP.
"""

import asyncio
import json
import websockets

async def main():
    uri = "ws://localhost:8000/mcp/ws/mcp"

    async with websockets.connect(uri) as ws:
        print("=" * 70)
        print("WebSocket Binary Transfer - Correct Flow")
        print("=" * 70)
        print()

        # 1. Receive welcome
        welcome = await ws.recv()
        print("✓ Connected")
        print()

        # 2. Initialize
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }))
        init_response = await ws.recv()
        print("✓ Initialized")
        print()

        # ==================================================================
        # STEP 1: Capture screen and get URI (NOT binary yet!)
        # ==================================================================
        print("Step 1: Capture screen (get resource URI)")
        print("-" * 70)

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

        # Extract the result text
        result_text = response.get("result", {}).get("content", [{}])[0].get("text", "")

        # Parse JSON from text
        result_json = json.loads(result_text)

        if not result_json.get("success"):
            print(f"✗ Capture failed: {result_text}")
            return

        resource_uri = result_json["resource_uri"]

        print(f"✓ Capture successful!")
        print(f"  Resource URI: {resource_uri}")
        print(f"  Binary transfer mode: {result_json.get('binary_transfer')}")
        print(f"  Size: {result_json['metadata']['width']}x{result_json['metadata']['height']}")
        print()

        # ==================================================================
        # STEP 2: Fetch resource as BINARY (this is the key!)
        # ==================================================================
        print("Step 2: Fetch resource as binary")
        print("-" * 70)

        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "resources/read",  # ← MCP method, not tool!
            "params": {"uri": resource_uri}
        }))

        # Expect 3 messages:

        # Message 1: Metadata (JSON text frame)
        metadata_msg = await ws.recv()
        if isinstance(metadata_msg, str):
            metadata = json.loads(metadata_msg)
            print(f"✓ Metadata received:")
            print(f"  Type: {metadata.get('type')}")
            print(f"  Size: {metadata.get('size'):,} bytes")
            print(f"  MIME: {metadata.get('mimeType')}")

        # Message 2: Binary data (binary frame - NO BASE64!)
        binary_data = await ws.recv()
        if isinstance(binary_data, bytes):
            print(f"✓ Binary data received: {len(binary_data):,} bytes")
            print(f"  Type: {type(binary_data)}")
            print(f"  Is bytes: {isinstance(binary_data, bytes)}")
        else:
            print(f"✗ Expected bytes, got: {type(binary_data)}")
            return

        # Message 3: Acknowledgment (JSON text frame)
        ack_msg = await ws.recv()
        if isinstance(ack_msg, str):
            ack = json.loads(ack_msg)
            print(f"✓ Acknowledgment received")

        print()

        # ==================================================================
        # STEP 3: Save binary data directly
        # ==================================================================
        print("Step 3: Save binary data")
        print("-" * 70)

        output_file = "websocket_capture.png"
        with open(output_file, "wb") as f:
            f.write(binary_data)

        print(f"✓ Saved to: {output_file}")
        print(f"  File size: {len(binary_data):,} bytes")

        # Compare with base64
        import base64
        base64_size = len(base64.b64encode(binary_data))
        savings = base64_size - len(binary_data)
        savings_pct = (savings / base64_size) * 100

        print()
        print("Size comparison:")
        print(f"  Binary (WebSocket): {len(binary_data):,} bytes")
        print(f"  Base64 (if used):   {base64_size:,} bytes")
        print(f"  Savings:            {savings:,} bytes ({savings_pct:.1f}%)")

        print()
        print("=" * 70)
        print("SUCCESS! Binary transfer completed")
        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
