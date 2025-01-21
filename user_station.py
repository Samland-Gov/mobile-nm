import asyncio
import websockets
import json
import hashlib
import logging
from queue import Queue
from threading import Thread

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UserInputHandler:
    def __init__(self, user_id, task_queue):
        self.user_id = user_id
        self.task_queue = task_queue
        self.keep_running = True

    def handle_user_input(self):
        """Handle user input in a separate thread."""
        while self.keep_running:
            print("\nOptions:")
            print("1. Send a text message")
            print("2. Log out")
            choice = input("Enter your choice: ").strip()

            if choice == "1":
                target_user = input("Enter the target user ID: ").strip()
                message = input("Enter your message: ").strip()
                self.task_queue.put(("send_message", target_user, message))
            elif choice == "2":
                self.task_queue.put(("logout",))
                self.keep_running = False
            else:
                print("Invalid choice. Please select 1 or 2.")

class MessageHandler:
    def __init__(self, user_id, secret_key, bms_uri, task_queue):
        self.user_id = user_id
        self.secret_key = secret_key
        self.bms_uri = bms_uri
        self.websocket = None
        self.task_queue = task_queue

    def generate_response(self, challenge):
        """Generate a response to the challenge using SHA256."""
        return hashlib.sha256(f"{self.secret_key}{challenge}".encode()).hexdigest()

    async def keepalive(self):
        """Send periodic ping messages to keep the connection alive."""
        try:
            while True:
                await self.websocket.ping()
                await asyncio.sleep(30)  # Send a ping every 30 seconds
        except Exception as e:
            logging.error(f"[User {self.user_id}] Keepalive error: {e}")

    async def connect(self):
        """Establish a WebSocket connection."""
        try:
            self.websocket = await websockets.connect(self.bms_uri)
            logging.info(f"[User {self.user_id}] Connected to BMS at {self.bms_uri}")
            asyncio.create_task(self.keepalive())  # Start the keepalive task
        except Exception as e:
            logging.error(f"[User {self.user_id}] Failed to connect to BMS: {e}")

    async def authenticate(self):
        """Perform authentication with the BMS."""
        try:
            logging.info(f"[User {self.user_id}] Authenticating...")

            # Step 1: Send authentication request
            auth_request = {"type": "auth", "user_id": self.user_id}
            logging.info(f"[User {self.user_id}] Sending auth request: {auth_request}")
            await self.websocket.send(json.dumps(auth_request))

            # Step 2: Receive the challenge
            challenge_response = await self.websocket.recv()
            logging.info(f"[User {self.user_id}] Received challenge response: {challenge_response}")
            challenge_data = json.loads(challenge_response)

            if "challenge" in challenge_data:
                challenge = challenge_data["challenge"]
                logging.info(f"[User {self.user_id}] Received challenge: {challenge}")

                # Generate response to the challenge
                response = {
                    "type": "auth_response",
                    "user_id": self.user_id,
                    "challenge": challenge,
                    "response": self.generate_response(challenge)
                }
                logging.info(f"[User {self.user_id}] Sending response: {response}")
                await self.websocket.send(json.dumps(response))

                # Step 3: Receive authentication result
                auth_result = await self.websocket.recv()
                logging.info(f"[User {self.user_id}] Received auth result: {auth_result}")
                result_data = json.loads(auth_result)

                if result_data.get("status") == "Authenticated":
                    logging.info(f"[User {self.user_id}] Authentication successful!")
                    return True
                else:
                    logging.error(f"[User {self.user_id}] Authentication failed: {result_data.get('error')}")
                    return False
            else:
                logging.error(f"[User {self.user_id}] Authentication failed: {challenge_data.get('error')}")
                return False
        except Exception as e:
            logging.error(f"[User {self.user_id}] Authentication error: {e}")
            return False

    async def listen_to_server(self):
        """Listen for messages from the server."""
        try:
            while True:
                message = await self.websocket.recv()
                logging.info(f"[User {self.user_id}] Received message: {message}")
        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"[User {self.user_id}] WebSocket connection closed: {e}")
        except Exception as e:
            logging.error(f"[User {self.user_id}] Error in listening: {e}")

    async def process_tasks(self):
        """Process tasks from the queue."""
        try:
            while True:
                task = await asyncio.get_event_loop().run_in_executor(None, self.task_queue.get)
                if task[0] == "send_message":
                    _, target_user, message = task
                    await self.send_message(target_user, message)
                elif task[0] == "logout":
                    await self.logout()
                    break
        except Exception as e:
            logging.error(f"[User {self.user_id}] Error processing tasks: {e}")

    async def send_message(self, target_user, message):
        """Send a text message to another user."""
        try:
            text_message = {
                "type": "text",
                "source_user": self.user_id,
                "target_user": target_user,
                "message": message
            }
            await self.websocket.send(json.dumps(text_message))
            response = await self.websocket.recv()
            response_data = json.loads(response)

            if response_data.get("status") == "Message sent":
                logging.info(f"[User {self.user_id}] Message sent successfully.")
            else:
                logging.error(f"[User {self.user_id}] Failed to send message: {response_data.get('error')}")
        except Exception as e:
            logging.error(f"[User {self.user_id}] Error sending message: {e}")

    async def logout(self):
        """Log out from the BMS."""
        try:
            logout_request = {
                "type": "auth_logout",
                "user_id": self.user_id
            }
            await self.websocket.send(json.dumps(logout_request))
            response = await self.websocket.recv()
            response_data = json.loads(response)

            if response_data.get("status") == "Logged out":
                logging.info(f"[User {self.user_id}] Successfully logged out.")
            else:
                logging.error(f"[User {self.user_id}] Logout failed: {response_data.get('error')}")
        except Exception as e:
            logging.error(f"[User {self.user_id}] Error during logout: {e}")

async def main():
    user_id = input("Enter your MSISDN (User ID): ").strip()
    secret_key = input("Enter your Secret Key: ").strip()
    bms_uri = "ws://localhost:6790"  # Base Message Station URI

    task_queue = Queue()
    message_handler = MessageHandler(user_id, secret_key, bms_uri, task_queue)
    await message_handler.connect()

    if await message_handler.authenticate():
        # Start listening to the server in a background task
        asyncio.create_task(message_handler.listen_to_server())

        # Start processing tasks from the queue in a background task
        asyncio.create_task(message_handler.process_tasks())

        # Handle user input in a separate thread
        user_input_handler = UserInputHandler(user_id, task_queue)
        input_thread = Thread(target=user_input_handler.handle_user_input)
        input_thread.start()

        # Wait for the input thread to finish
        input_thread.join()

if __name__ == "__main__":
    asyncio.run(main())
