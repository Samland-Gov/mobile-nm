import asyncio
import websockets
import json
import hashlib

def generate_response(challenge, secret_key):
    """Generate a response to the challenge using SHA256."""
    return hashlib.sha256(f"{secret_key}{challenge}".encode()).hexdigest()

async def user_station(user_id, secret_key, bms_uri):
    """
    Represents a single User Station.

    Parameters:
    - user_id: The unique MSISDN of the user (e.g., a phone number-like ID).
    - secret_key: The user's secret key used for authentication.
    - bms_uri: The WebSocket URI of the Base Message Station (BMS).
    """
    try:
        async with websockets.connect(bms_uri) as websocket:
            print(f"[User {user_id}] Authenticating...")

            # Step 1: Send authentication request
            auth_request = {"type": "auth", "user_id": user_id}
            print(f"[User {user_id}] Sending auth request: {auth_request}")
            await websocket.send(json.dumps(auth_request))

            # Step 2: Receive the challenge
            challenge_response = await websocket.recv()
            print(f"[User {user_id}] Received challenge response: {challenge_response}")
            challenge_data = json.loads(challenge_response)

            if "challenge" in challenge_data:
                challenge = challenge_data["challenge"]
                print(f"[User {user_id}] Received challenge: {challenge}")

                # Generate response to the challenge
                response = {
                    "type": "auth_response",
                    "user_id": user_id,
                    "challenge": challenge,
                    "response": generate_response(challenge, secret_key)
                }
                print(f"[User {user_id}] Sending response: {response}")
                await websocket.send(json.dumps(response))

                # Step 3: Receive authentication result
                auth_result = await websocket.recv()
                print(f"[User {user_id}] Received auth result: {auth_result}")
                result_data = json.loads(auth_result)

                if result_data.get("status") == "Authenticated":
                    print(f"[User {user_id}] Authentication successful!")
                else:
                    print(f"[User {user_id}] Authentication failed: {result_data.get('error')}")
                    return
            else:
                print(f"[User {user_id}] Authentication failed: {challenge_data.get('error')}")
                return
            
            # Step 2: Main interaction loop
            while True:
                print("\nOptions:")
                print("1. Send a text message")
                print("2. Log out")
                choice = input("Enter your choice: ").strip()

                if choice == "1":
                    # Sending a text message
                    target_user = input("Enter the target user ID: ").strip()
                    message = input("Enter your message: ").strip()
                    
                    text_message = {
                        "type": "text",
                        "user_id": user_id,
                        "target_user": target_user,
                        "message": message
                    }
                    await websocket.send(json.dumps(text_message))
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    if response_data.get("status") == "Message sent":
                        print(f"[User {user_id}] Message sent successfully.")
                    else:
                        print(f"[User {user_id}] Failed to send message: {response_data.get('error')}")
                
                elif choice == "2":
                    # Logging out
                    logout_request = {
                        "type": "auth_logout",
                        "user_id": user_id
                    }
                    await websocket.send(json.dumps(logout_request))
                    response = await websocket.recv()
                    response_data = json.loads(response)
                    
                    if response_data.get("status") == "Logged out":
                        print(f"[User {user_id}] Successfully logged out.")
                    else:
                        print(f"[User {user_id}] Logout failed: {response_data.get('error')}")
                    break

                else:
                    print("Invalid choice. Please select 1 or 2.")
                    
    except Exception as e:
        print(f"[User {user_id}] Error: {e}")

# Example usage
if __name__ == "__main__":
    user_id = input("Enter your MSISDN (User ID): ").strip()
    secret_key = input("Enter your Secret Key: ").strip()
    bms_uri = "ws://localhost:6790"  # Base Message Station URI
    asyncio.run(user_station(user_id, secret_key, bms_uri))