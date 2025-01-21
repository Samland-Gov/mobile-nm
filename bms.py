import asyncio
import json
import websockets
import logging
from asyncio import Queue

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UserStationHandler:
    def __init__(self, bms_id, message_queue, response_queue):
        self.bms_id = bms_id
        self.message_queue = message_queue
        self.response_queue = response_queue
        self.connected_users = {}

    async def keepalive(self, websocket):
        """Send periodic ping messages to keep the connection alive."""
        try:
            while True:
                await websocket.ping()
                await asyncio.sleep(30)  # Send a ping every 30 seconds
        except Exception as e:
            logging.error(f"Keepalive error: {e}")

    async def handle_connection(self, websocket, path):
        try:
            user_id = None  # Track user_id for cleanup
            asyncio.create_task(self.keepalive(websocket))  # Start the keepalive task

            async def receive_user_messages():
                nonlocal user_id
                while True:
                    msg = await websocket.recv()
                    message_data = json.loads(msg)

                    if message_data["type"] == "auth":
                        user_id = message_data["user_id"]
                        self.connected_users[user_id] = websocket  # Map user_id to WebSocket
                        auth_request = {"type": "auth", "user_id": user_id, "bms_id": self.bms_id}
                        await self.message_queue.put(auth_request)

                    elif message_data["type"] == "auth_response":
                        await self.message_queue.put(message_data)

                    elif message_data["type"] == "auth_logout":
                        user_id = message_data["user_id"]
                        if user_id in self.connected_users:
                            logout_message = {
                                "type": "auth_logout",
                                "user_id": user_id,
                                "bms_id": self.bms_id
                            }
                            await self.message_queue.put(logout_message)
                            del self.connected_users[user_id]
                            await websocket.send(json.dumps({"status": "Logged out"}))
                        else:
                            await websocket.send(json.dumps({"error": "User not found"}))

                    # Forward other message types to the MSC
                    elif message_data["type"] == "text":
                        await self.message_queue.put(message_data)

                    else:
                        await websocket.send(json.dumps({"error": "Unsupported message type"}))

            async def send_responses():
                while True:
                    response = await self.response_queue.get()
                    if response.get("user_id") == user_id or response.get("target_user") == user_id:
                        await websocket.send(json.dumps(response))

            await asyncio.gather(receive_user_messages(), send_responses())

        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"WebSocket connection closed: {e}")
        except Exception as e:
            logging.error(f"Error handling User Station connection: {e}")
        finally:
            if user_id:
                self.cleanup_user(user_id)

    def cleanup_user(self, websocket):
        user_to_remove = None
        for user_id, user_ws in self.connected_users.items():
            if user_ws == websocket:
                user_to_remove = user_id
                break
        if user_to_remove:
            logout_message = {
                "type": "auth_logout",
                "user_id": user_to_remove,
                "bms_id": self.bms_id
            }
            # Since this is not an async function, create a task to handle the async operation
            asyncio.create_task(self.message_queue.put(logout_message))
            del self.connected_users[user_to_remove]
            logging.info(f"User {user_to_remove} disconnected and logged out.")

class MSCHandler:
    def __init__(self, bms_id, message_queue, response_queue):
        self.bms_id = bms_id
        self.message_queue = message_queue
        self.response_queue = response_queue

    async def handle_connection(self):
        try:
            msc_uri = "ws://localhost:6789"
            async with websockets.connect(msc_uri) as msc_connection:
                registration_message = {
                    "type": "bms_register",
                    "bms_id": self.bms_id
                }
                await msc_connection.send(json.dumps(registration_message))

                response = await msc_connection.recv()
                logging.info(f"Registered BMS {self.bms_id} with MSC: {response}")

                async def send_requests():
                    while True:
                        message = await self.message_queue.get()
                        await msc_connection.send(json.dumps(message))

                async def receive_responses():
                    while True:
                        try:
                            msc_response = await msc_connection.recv()
                            logging.info(f"Received response from MSC: {msc_response}")  # Log the response

                            # Attempt to parse the response
                            try:
                                response_data = json.loads(msc_response)
                                logging.info(f"Parsed response: {response_data}")
                                await self.response_queue.put(response_data)
                            except json.JSONDecodeError:
                                logging.error(f"Error decoding MSC response: {msc_response}")
                                
                        except websockets.exceptions.ConnectionClosedOK:
                            logging.info("MSC connection closed gracefully (code 1000)")
                            break
                        except websockets.exceptions.ConnectionClosed as e:
                            logging.error(f"MSC connection closed with error: {e}")
                            break
                        except Exception as e:
                            logging.error(f"Error receiving MSC response: {e}")
                            break  # Break to avoid an infinite loop on error

                await asyncio.gather(send_requests(), receive_responses())
        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"MSC WebSocket connection closed: {e}")
        except Exception as e:
            logging.error(f"Error connecting to MSC: {e}")

class BMS:
    def __init__(self, bms_id):
        self.bms_id = bms_id
        self.message_queue = Queue()
        self.response_queue = Queue()
        self.user_station_handler = UserStationHandler(bms_id, self.message_queue, self.response_queue)
        self.msc_handler = MSCHandler(bms_id, self.message_queue, self.response_queue)

    async def start_user_station_server(self):
        server = await websockets.serve(
            self.user_station_handler.handle_connection,
            "localhost", 6790
        )
        logging.info(f"BMS {self.bms_id} started on ws://localhost:6790 (waiting for User Stations)")
        await server.wait_closed()

    async def start(self):
        msc_task = asyncio.create_task(self.msc_handler.handle_connection())
        user_station_server_task = asyncio.create_task(self.start_user_station_server())
        await asyncio.gather(msc_task, user_station_server_task)

if __name__ == "__main__":
    bms_id = "bms_001"
    bms = BMS(bms_id)
    asyncio.run(bms.start())