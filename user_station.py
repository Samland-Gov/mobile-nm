import asyncio
import websockets
import json
import queue
import hmac
import hashlib

# Helper function to generate challenge
def generate_challenge(user_id, secret_key):
    return hmac.new(secret_key.encode(), user_id.encode(), hashlib.sha256).hexdigest()

class UserStation:
    def __init__(self, user_id, secret_key, bms_uri):
        self.user_id = user_id
        self.secret_key = secret_key
        self.bms_uri = bms_uri
        self.packet_id_counter = 0
        self.websocket = None
        self.task_queue = queue.Queue()

    def generate_packet_id(self):
        self.packet_id_counter += 1
        return str(self.packet_id_counter)

    async def connect(self):
        self.websocket = await websockets.connect(self.bms_uri)
        print("Connected to BMS.")
        await self.authenticate()

    async def authenticate(self):
        packet_id = self.generate_packet_id()
        auth_message = {
            "type": "auth",
            "user_id": self.user_id,
            "packet_id": packet_id
        }
        await self.send_message(auth_message)

    async def respond_to_challenge(self, challenge, packet_id):
        response = generate_challenge(self.user_id, self.secret_key)
        auth_response = {
            "type": "auth_response",
            "user_id": self.user_id,
            "challenge": challenge,
            "response": response,
            "packet_id": packet_id
        }
        await self.send_message(auth_response)

    async def send_message(self, message):
        if self.websocket:
            await self.websocket.send(json.dumps(message))
            print("Sent:", message)

    async def handle_messages(self):
        while True:
            message = await self.websocket.recv()  # Use recv() for asynchronous message receiving
            data = json.loads(message)
            print("Received:", data)

            if data.get("type") == "challenge":
                await self.respond_to_challenge(data["challenge"], data["packet_id"])

    async def process_tasks(self):
        while True:
            task = await asyncio.to_thread(self.task_queue.get)  # Ensure thread-safe task processing
            if task["action"] == "logout":
                await self.logout()
            elif task["action"] == "text":
                await self.send_text_message(task["target_user"], task["message"])

    async def logout(self):
        packet_id = self.generate_packet_id()
        logout_message = {
            "type": "auth_logout",
            "user_id": self.user_id,
            "packet_id": packet_id
        }
        await self.send_message(logout_message)

    async def send_text_message(self, target_user, message):
        packet_id = self.generate_packet_id()
        text_message = {
            "type": "text",
            "source_user": self.user_id,
            "target_user": target_user,
            "message": message,
            "packet_id": packet_id
        }
        await self.send_message(text_message)

    async def run(self):
        await self.connect()
        consumer_task = asyncio.create_task(self.handle_messages())
        producer_task = asyncio.create_task(self.process_tasks())
        await asyncio.gather(consumer_task, producer_task)

    async def user_input(self):
        while True:
            command = await asyncio.to_thread(input, "Enter command (logout, text): ")
            if command == "logout":
                self.task_queue.put({"action": "logout"})
            elif command == "text":
                target_user = await asyncio.to_thread(input, "Target user ID: ")
                message = await asyncio.to_thread(input, "Message: ")
                self.task_queue.put({"action": "text", "target_user": target_user, "message": message})

async def start_user_station():
    user_id = input("Enter your user ID: ")
    secret_key = input("Enter your secret key: ")
    bms_uri = input("Enter BMS WebSocket URI: ")

    user_station = UserStation(user_id, secret_key, bms_uri)

    # Start handling user input asynchronously
    input_task = asyncio.create_task(user_station.user_input())

    # Start the WebSocket and message processing tasks
    await user_station.run()

if __name__ == "__main__":
    asyncio.run(start_user_station())
