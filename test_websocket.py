#!/usr/bin/env python3
"""
Simple WebSocket test client for N9NE AI Voice Agent
Tests the /ws endpoint by sending messages and receiving echoes
"""

import asyncio
import websockets
import json
import time

async def test_websocket():
    """Test the WebSocket connection"""
    uri = "ws://localhost:8000/ws"
    
    print("🔌 Connecting to WebSocket server...")
    print(f"📍 URI: {uri}")
    print("-" * 50)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected successfully!")
            print("-" * 50)
            
            # Test messages to send
            test_messages = [
                "Hello, N9NE!",
                "This is a test message",
                "WebSocket is working!",
                "Ready for real-time communication",
                "Goodbye!"
            ]
            
            for i, message in enumerate(test_messages, 1):
                print(f"📤 Sending message {i}: {message}")
                await websocket.send(message)
                
                # Wait for response
                response = await websocket.recv()
                print(f"📥 Received: {response}")
                print("-" * 30)
                
                # Small delay between messages
                await asyncio.sleep(1)
            
            print("🎉 WebSocket test completed successfully!")
            
    except websockets.exceptions.ConnectionClosed:
        print("❌ Connection closed by server")
    except ConnectionRefusedError:
        print("❌ Connection refused. Make sure the server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 N9NE WebSocket Test Client")
    print("=" * 50)
    asyncio.run(test_websocket())
