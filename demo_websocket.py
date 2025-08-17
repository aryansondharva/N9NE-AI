#!/usr/bin/env python3
"""
WebSocket Demo for N9NE AI Voice Agent
Demonstrates the WebSocket connection with a simple conversation
"""

import asyncio
import websockets
import time

async def demo_websocket():
    """Demonstrate WebSocket functionality"""
    uri = "ws://localhost:8000/ws"
    
    print("🎭 N9NE WebSocket Demo")
    print("=" * 50)
    print("This demo shows the WebSocket connection working!")
    print("The server will echo back every message we send.")
    print("-" * 50)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket server!")
            print("-" * 50)
            
            # Simple conversation demo
            conversation = [
                "Hello! This is N9NE AI Voice Agent.",
                "I'm testing the WebSocket connection.",
                "The server should echo back each message.",
                "This is working perfectly!",
                "Ready for real-time voice communication.",
                "Thank you for testing with me!"
            ]
            
            for i, message in enumerate(conversation, 1):
                print(f"👤 You: {message}")
                await websocket.send(message)
                
                # Get server response
                response = await websocket.recv()
                print(f"🤖 Server: {response}")
                print()
                
                # Brief pause for readability
                await asyncio.sleep(0.5)
            
            print("🎉 Demo completed successfully!")
            print("The WebSocket connection is working perfectly!")
            
    except websockets.exceptions.ConnectionClosed:
        print("❌ Connection closed by server")
    except ConnectionRefusedError:
        print("❌ Connection refused. Make sure the server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(demo_websocket())
