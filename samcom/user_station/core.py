import asyncio
import websockets
import json
import queue
from ..common.exchange import generate_challenge


class StationInterface:
    def __init__(self):
        self.server_url: str = None
        self.username: str = None
        self.password: str = None
        self.incoming_queue = queue.Queue()
        self.user_station: 'UserStation' = None
        self.messages = {}  # Dictionary to store messages for each user

    def send_text_message(self, target_user, message):
        self.user_station.task_queue.put({"action": "text", "target_user": target_user, "message": message})

    def connect(self):
        self.user_station.task_queue.put({"action": "connect"})

    def logout(self):
        self.user_station.task_queue.put({"action": "logout"})

    def start(self):
        self.user_station = UserStation(self)
        self.user_station.start()

    def process_ui_queue(self):
        try:
            message = self.incoming_queue.get_nowait()
            if hasattr(self, f"process_{message['action']}"):
                getattr(self, f"process_{message["action"]}")(message)
            else:
                print(f"No handler found for interface task: {message['action']}")

        except queue.Empty:
            pass

    def process_message(self, message):
        if message["action"] == "message":
            source_user = message["source_user"]
            message = message["message"]
            formatted_message = f"{source_user}: {message}"
            if source_user in self.messages:
                self.messages[source_user].append(formatted_message)
            else:
                self.messages[source_user] = [formatted_message]


class UserStation:
    def __init__(self, interface: StationInterface):
        self.interface = interface
        self.packet_id_counter = 0
        self.websocket = None
        self.task_queue = queue.Queue()
        self.interface.user_station = self

    async def process(self):
        consumer_task = asyncio.create_task(self.handle_messages())
        producer_task = asyncio.create_task(self.process_tasks())
        await asyncio.gather(consumer_task, producer_task)

    def start(self):
        asyncio.run(self.process())

    def generate_packet_id(self):
        self.packet_id_counter += 1
        return str(self.packet_id_counter)

    async def connect(self):
        self.websocket = await websockets.connect(self.interface.server_url)
        print("Connected to BMS.")
        await self.authenticate()

    async def authenticate(self):
        packet_id = self.generate_packet_id()
        auth_message = {
            "type": "auth",
            "user_id": self.interface.username,
            "packet_id": packet_id
        }
        await self.send_message(auth_message)

    async def respond_to_challenge(self, challenge, packet_id):
        response = generate_challenge(self.interface.username, self.interface.password)
        auth_response = {
            "type": "auth_response",
            "user_id": self.interface.username,
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
            if self.websocket is None:
                await asyncio.sleep(0.1)
                continue
            message = await self.websocket.recv()  # Use recv() for asynchronous message receiving
            data = json.loads(message)
            print("Received:", data)

            if data.get("type") == "challenge":
                await self.respond_to_challenge(data["challenge"], data["packet_id"])
            elif data.get("type") == "auth_result":
                if data.get("status") == "Authenticated":
                    print("Authentication successful!")
                    self.interface.incoming_queue.put({"action": "authenticated"})
                else:
                    print("Authentication failed!")
            elif data.get("type") == "text":
                source_user = data["source_user"]
                message = data["message"]
                self.interface.incoming_queue.put({"action": "message", "source_user": source_user, "message": message})

    async def process_tasks(self):
        while True:
            if self.task_queue.empty():
                await asyncio.sleep(0.1)
                continue
            task = self.task_queue.get()
            if task["action"] == "connect":
                await self.connect()
            elif task["action"] == "logout":
                await self.logout()
            elif task["action"] == "text":
                await self.send_text_message(task["target_user"], task["message"])

    async def logout(self):
        packet_id = self.generate_packet_id()
        logout_message = {
            "type": "auth_logout",
            "user_id": self.interface.username,
            "packet_id": packet_id
        }
        await self.send_message(logout_message)

    async def send_text_message(self, target_user, message):
        packet_id = self.generate_packet_id()
        text_message = {
            "type": "text",
            "source_user": self.interface.username,
            "target_user": target_user,
            "message": message,
            "packet_id": packet_id
        }
        await self.send_message(text_message)
