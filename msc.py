import asyncio
import websockets
import json
import random
import hashlib

# Dictionary to store user secrets (passwords/keys)
user_secrets = {
    "1234567890": "secretkey123",  # Example secret key for user with MSISDN-like ID
    "0987654321": "anothersecret",  # Another user
}

# Dictionary to track authentication states for each user
user_authenticated = {}

# Dictionary to track which BMS is handling each user
user_bms_mapping = {}

# Dictionary to track BMS registration (ID -> WebSocket)
bms_connections = {}

# Function to generate a challenge (random number)
def generate_challenge():
    return random.randint(100000, 999999)

# Function to validate the response to the challenge
def validate_response(user_id, response):
    """ Generate the correct response based on the secret key. """
    if user_id not in user_secrets:
        return False
    if "challenge" not in response or "response" not in response:
        return False  # Handle missing fields gracefully
    secret_key = user_secrets[user_id]
    expected_response = hashlib.sha256(f"{secret_key}{response['challenge']}".encode()).hexdigest()
    return expected_response == response["response"]

# Handle incoming messages from BMS
async def handle_bms_connection(websocket, path):
    try:
        # BMS Registration - Receive BMS ID
        msg = await websocket.recv()
        print(msg)
        message_data = json.loads(msg)

        if message_data["type"] == "bms_register" and "bms_id" in message_data:
            # Save BMS ID and associate it with the WebSocket connection
            bms_id = message_data["bms_id"]
            bms_connections[bms_id] = websocket
            print(f"BMS {bms_id} registered successfully.")
            await websocket.send(json.dumps({"status": "BMS registered"}))
        else:
            await websocket.send(json.dumps({"error": "Invalid registration message"}))

        while True:
            msg = await websocket.recv()
            message_data = json.loads(msg)

            if message_data["type"] == "auth":
                user_id = message_data["user_id"]
                bms_id = message_data["bms_id"]

                if user_id in user_authenticated and user_bms_mapping.get(user_id) == bms_id:
                    await websocket.send(json.dumps({"status": "Already authenticated"}))
                    continue

                # Generate a challenge and send to the BMS
                challenge = generate_challenge()
                challenge_message = {"challenge": challenge, "user_id": user_id}
                await websocket.send(json.dumps(challenge_message))

            elif message_data["type"] == "auth_response":
                user_id = message_data["user_id"]
                response = message_data["response"]

                # Validate the response
                if validate_response(user_id, response):
                    user_authenticated[user_id] = True
                    user_bms_mapping[user_id] = message_data["bms_id"]
                    await websocket.send(json.dumps({"status": "Authenticated"}))
                else:
                    await websocket.send(json.dumps({"error": "Authentication failed"}))

            elif message_data["type"] == "auth_logout" and message_data.get("user_id") and message_data.get("bms_id"):
                # Handle user logout
                user_id = message_data["user_id"]
                bms_id = message_data["bms_id"]

                # Check if the user is authenticated
                if user_id in user_authenticated and user_bms_mapping.get(user_id) == bms_id:
                    del user_authenticated[user_id]
                    del user_bms_mapping[user_id]
                    await websocket.send(json.dumps({"status": "User logged out"}))
                else:
                    await websocket.send(json.dumps({"error": "User not authenticated or BMS mismatch"}))

            elif message_data["type"] == "text" and message_data.get("target_user"):
                # Handle message forwarding to the correct BMS
                source_user = message_data["source_user"]
                target_user = message_data["target_user"]
                message = message_data["message"]

                # Check if target_user is authenticated
                if target_user in user_authenticated and user_authenticated[target_user]:
                    # Find which BMS the target user is connected to
                    target_bms_id = user_bms_mapping.get(target_user)

                    if target_bms_id and target_bms_id in bms_connections:
                        target_bms_websocket = bms_connections[target_bms_id]
                        # Forward the message to the correct BMS
                        await target_bms_websocket.send(json.dumps({
                            "type": "text",
                            "message": message,
                            "source_user": source_user,
                            "target_user": target_user
                        }))
                        await websocket.send(json.dumps({"status": "Message forwarded to BMS"}))
                    else:
                        await websocket.send(json.dumps({"error": "Target user not found or not connected"}))
                else:
                    await websocket.send(json.dumps({"error": "Target user not authenticated"}))

            else:
                print(f"Received an unsupported message: {msg}")
                await websocket.send(json.dumps({"error": "Unsupported message type"}))

    except websockets.exceptions.ConnectionClosed as e:
        print(f"WebSocket connection closed: {e}")
    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")
    except Exception as e:
        print(f"Error handling BMS connection: {e}")
    finally:
        # Clean up when connection is closed
        print("BMS connection closed.")
        # Remove BMS from connections after disconnect
        for bms_id, connection in list(bms_connections.items()):
            if connection == websocket:
                del bms_connections[bms_id]
                break

        # Clean up any user mappings associated with this BMS
        for user_id, bms_id in list(user_bms_mapping.items()):
            if bms_id == websocket:
                del user_bms_mapping[user_id]

        for user_id in list(user_authenticated):
            if user_bms_mapping.get(user_id) == websocket:
                del user_authenticated[user_id]

# Start the MSC WebSocket server to listen for BMS connections
async def start_msc_server():
    # Bind to port 6789 to accept connections from the BMS
    server = await websockets.serve(handle_bms_connection, "localhost", 6789)
    print("MSC server started on ws://localhost:6789 (waiting for BMS connections)")

    # Keep the server running
    await server.wait_closed()

# Run the MSC server
asyncio.run(start_msc_server())
