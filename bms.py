import threading
import queue
import logging
import json
import websockets
import asyncio

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MSCConnection(threading.Thread):
    def __init__(self, outgoing_queue, user_queues, msc_url, base_message_station):
        super().__init__(daemon=True)
        self.outgoing_queue = outgoing_queue
        self.user_queues = user_queues
        self.msc_url = msc_url
        self.base_message_station = base_message_station
        self.running = True

    def process_message(self, message):
        if "type" not in message:
            logging.warning("Received message without type field")
            return

        message_type = message["type"]

        if message_type == "bms_register_response":
            logging.info(f"Received BMS registration response: {message}")

        elif message_type == "challenge":
            user_id = message.get("user_id")
            if user_id in self.user_queues:
                self.user_queues[user_id].put(message)
            else:
                logging.warning(f"No queue for user_id: {user_id}")

        elif message_type in {"auth_result", "logout_result", "text"}:
            target_user = message.get("user_id") or message.get("target_user")
            if target_user in self.user_queues:
                self.user_queues[target_user].put(message)
            else:
                logging.warning(f"No queue for target_user: {target_user}")

        else:
            logging.warning(f"Unhandled message type from MSC: {message_type}")

    async def send_bms_register(self, websocket):
        packet_id = self.base_message_station.generate_packet_id()
        registration_message = {
            "type": "bms_register",
            "packet_id": packet_id,
            "bms_id": self.base_message_station.bms_id
        }
        await websocket.send(json.dumps(registration_message))
        logging.info(f"Sent BMS registration: {registration_message}")

    async def handle_outgoing_messages(self, websocket):
        while self.running:
            try:
                if not self.outgoing_queue.empty():
                    message = self.outgoing_queue.get()
                    message["bms_id"] = self.base_message_station.bms_id
                    await websocket.send(json.dumps(message))
                    logging.info(f"Sent to MSC: {message}")
                await asyncio.sleep(0.1)  # Prevent tight looping
            except Exception as e:
                logging.error(f"Error in outgoing message handler: {e}")

    async def handle_incoming_messages(self, websocket):
        while self.running:
            try:
                incoming = await websocket.recv()
                message = json.loads(incoming)
                logging.info(f"Received from MSC: {message}")
                self.process_message(message)
            except Exception as e:
                logging.error(f"Error in incoming message handler: {e}")
                break

    async def connect_to_msc(self):
        async with websockets.connect(self.msc_url) as websocket:
            logging.info("Connected to MSC.")
            
            # Send BMS registration
            await self.send_bms_register(websocket)

            # Run incoming and outgoing handlers concurrently
            await asyncio.gather(
                self.handle_outgoing_messages(websocket),
                self.handle_incoming_messages(websocket)
            )

    def run(self):
        asyncio.run(self.connect_to_msc())

class UserStationConnection(threading.Thread):
    def __init__(self, websocket, user_id, outgoing_queue, msc_outgoing_queue, base_message_station):
        super().__init__(daemon=True)
        self.websocket = websocket
        self.user_id = user_id
        self.outgoing_queue = outgoing_queue
        self.msc_outgoing_queue = msc_outgoing_queue
        self.base_message_station = base_message_station
        self.running = True

    def process_message(self, message):
        if "type" not in message:
            logger.warning("Received message without type field")
            return

        message_type = message["type"]

        if message_type == "auth_response":
            message["bms_id"] = self.base_message_station.bms_id
            self.msc_outgoing_queue.put(message)

        elif message_type == "auth_logout":
            message["bms_id"] = self.base_message_station.bms_id
            self.msc_outgoing_queue.put(message)
            self.websocket.close()

        elif message_type == "text":
            message["source_user"] = self.user_id
            message["bms_id"] = self.base_message_station.bms_id
            self.msc_outgoing_queue.put(message)

        else:
            logger.warning(f"Unhandled message type from User Station: {message_type}")

    async def send_outgoing_messages(self):
        while self.running:
            if not self.outgoing_queue.empty():
                message = self.outgoing_queue.get()
                await self.websocket.send(json.dumps(message))
                logger.info(f"Sent to User Station {self.user_id}: {message}")
            await asyncio.sleep(0.1)  # Add a small sleep to yield control and avoid busy waiting

    async def receive_incoming_messages(self):
        while self.running:
            try:
                incoming = await self.websocket.recv()
                message = json.loads(incoming)
                logger.info(f"Received from User Station {self.user_id}: {message}")
                self.process_message(message)
            except Exception as e:
                logger.error(f"Error receiving message for UserStationConnection {self.user_id}: {e}")

    async def handle_user_station(self):
        try:
            # Start tasks to handle both sending and receiving messages concurrently
            send_task = asyncio.create_task(self.send_outgoing_messages())
            receive_task = asyncio.create_task(self.receive_incoming_messages())
            
            # Await both tasks
            await asyncio.gather(send_task, receive_task)
        except Exception as e:
            logger.error(f"Error in UserStationConnection for {self.user_id}: {e}")

    def run(self):
        asyncio.run(self.handle_user_station())

class BaseMessageStation:
    def __init__(self, host, port, msc_url, bms_id):
        self.host = host
        self.port = port
        self.msc_url = msc_url
        self.bms_id = bms_id
        self.user_queues = {}
        self.msc_outgoing_queue = queue.Queue()
        self.msc_connection = MSCConnection(self.msc_outgoing_queue, self.user_queues, self.msc_url, self)
        self.running = True
        self.packet_id_counter = 0  # Initialize packet ID counter

    def generate_packet_id(self):
        """Generate a unique incrementing packet ID."""
        self.packet_id_counter += 1
        return str(self.packet_id_counter)  # Ensure packet_id is a JSON string

    async def handle_new_user(self, websocket, path):
        try:
            user_id = None
            user_outgoing_queue = None

            while self.running:
                incoming = await websocket.recv()
                message = json.loads(incoming)
                logger.info(f"Received from User Station: {message}")

                if "type" not in message:
                    logger.warning("Received message without 'type' field")
                    continue

                message_type = message["type"]

                if message_type == "auth":
                    # Extract and validate user_id from the auth packet
                    user_id = message.get("user_id")
                    if not user_id:
                        logger.warning("Auth packet missing 'user_id'")
                        continue

                    if user_id in self.user_queues:
                        logger.warning(f"User ID {user_id} is already connected.")
                        break

                    # Create a queue for this user and store it
                    user_outgoing_queue = queue.Queue()
                    self.user_queues[user_id] = user_outgoing_queue

                    # Forward the auth packet to the MSC
                    message["bms_id"] = self.bms_id
                    self.msc_outgoing_queue.put(message)

                    # Start a UserStationConnection for this user
                    user_connection = UserStationConnection(
                        websocket, user_id, user_outgoing_queue, self.msc_outgoing_queue, self
                    )
                    user_connection.start()
                    logger.info(f"User {user_id} connected.")
                    break  # Exit the loop after authentication

                else:
                    logger.warning(f"Unhandled message type before authentication: {message_type}")

            # Keep connection alive for other messages (handled by UserStationConnection)
            while self.running:
                await asyncio.sleep(1)

        except websockets.ConnectionClosed:
            logger.info(f"Connection closed for user: {user_id if user_id else 'unknown'}")
        finally:
            if user_id:
                self.user_queues.pop(user_id, None)
                logger.info(f"User {user_id} disconnected.")

    async def start_server(self):
        self.msc_connection.start()

        async with websockets.serve(self.handle_new_user, self.host, self.port):
            logging.info(f"BMS {self.bms_id} running on {self.host}:{self.port}")
            await asyncio.Future()  # Keep server running

if __name__ == "__main__":
    HOST = "localhost"
    PORT = 9001
    MSC_URL = "ws://localhost:9000"
    BMS_ID = "BMS1"

    bms = BaseMessageStation(HOST, PORT, MSC_URL, BMS_ID)
    asyncio.run(bms.start_server())
