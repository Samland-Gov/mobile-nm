import asyncio
import websockets
import json
from asyncio import Queue

# Dictionary to store which users are connected to this BMS
connected_users = {}

# Global message queue for communication between User Stations and MSC
message_queue = Queue()

# Global response queue for MSC responses to User Stations
response_queue = Queue()

# Function to handle incoming messages from User Stations
async def handle_user_station_connection(websocket, path, bms_id):
    try:
        while True:
            msg = await websocket.recv()
            message_data = json.loads(msg)

            if message_data["type"] == "auth":
                # Forward auth request to MSC via the message queue
                user_id = message_data["user_id"]
                auth_request = {"type": "auth", "user_id": user_id, "bms_id": bms_id}
                await message_queue.put(auth_request)

            elif message_data["type"] == "auth_response":
                # Proxy auth response via the message queue
                await message_queue.put(message_data)

            elif message_data["type"] == "auth_logout":
                # Handle user logout
                user_id = message_data["user_id"]
                if user_id in connected_users:
                    # Logout request to MSC via the message queue
                    logout_message = {
                        "type": "auth_logout",
                        "user_id": user_id,
                        "bms_id": bms_id
                    }
                    await message_queue.put(logout_message)

                    # Remove the user from the connected list
                    del connected_users[user_id]
                    await websocket.send(json.dumps({"status": "Logged out"}))
                else:
                    await websocket.send(json.dumps({"error": "User not found"}))

            elif message_data["type"] == "text":
                # Check if the target user is connected to this BMS
                target_user = message_data["target_user"]
                if target_user in connected_users:
                    # Deliver the message directly to the target user
                    await connected_users[target_user].send(json.dumps(message_data))
                else:
                    # Forward the message to the MSC for routing
                    await message_queue.put(message_data)

            else:
                await websocket.send(json.dumps({"error": "Unsupported message type"}))

            # Read response from the response queue and send it back to User Station
            if not response_queue.empty():
                response = await response_queue.get()
                await websocket.send(json.dumps(response))

    except Exception as e:
        print(f"Error handling User Station connection: {e}")
    finally:
        # Clean up when connection is closed
        user_to_remove = None
        for user_id, user_ws in connected_users.items():
            if user_ws == websocket:
                user_to_remove = user_id
                break
        if user_to_remove:
            # Notify the MSC about the user logout
            logout_message = {
                "type": "auth_logout",
                "user_id": user_to_remove,
                "bms_id": bms_id
            }
            await message_queue.put(logout_message)

            # Remove the user locally
            del connected_users[user_to_remove]
            print(f"User {user_to_remove} disconnected and logged out.")

# Function to handle MSC connection and processing the message queue
async def handle_msc_connection(bms_id):
    msc_uri = "ws://localhost:6789"  # MSC server URL
    async with websockets.connect(msc_uri) as msc_connection:
        # Register this BMS with the MSC by sending its BMS ID
        registration_message = {
            "type": "bms_register",
            "bms_id": bms_id
        }
        await msc_connection.send(json.dumps(registration_message))

        # Wait for confirmation from the MSC
        response = await msc_connection.recv()
        print(f"Registered BMS {bms_id} with MSC: {response}")

        # Loop to process messages from the queue and send them to MSC
        while True:
            message = await message_queue.get()  # Get the next message to send to MSC
            await msc_connection.send(json.dumps(message))

            # Wait for the response from the MSC and put it in the response queue
            msc_response = await msc_connection.recv()
            await response_queue.put(json.loads(msc_response))

# Function to handle WebSocket server for User Stations
async def handle_user_station_server(bms_id):
    server = await websockets.serve(
        lambda ws, path: handle_user_station_connection(ws, path, bms_id),
        "localhost", 6790
    )

    print(f"BMS {bms_id} started on ws://localhost:6790 (waiting for User Stations)")
    await server.wait_closed()

# Main function to handle the BMS startup process
async def start_bms(bms_id):
    # Start the loop for handling MSC connection
    msc_task = asyncio.create_task(handle_msc_connection(bms_id))

    # Start the WebSocket server for User Stations in a separate task
    user_station_server_task = asyncio.create_task(handle_user_station_server(bms_id))

    # Run both tasks concurrently
    await asyncio.gather(msc_task, user_station_server_task)

# Run the BMS with a unique BMS ID
if __name__ == "__main__":
    bms_id = "bms_001"  # Example BMS ID
    asyncio.run(start_bms(bms_id))
