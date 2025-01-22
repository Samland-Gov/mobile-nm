import logging
import websockets
import json
import asyncio
import hmac
from ..common.exchange import generate_challenge

# Configuring logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Class for managing users and authentication status
class UserManager:
    def __init__(self):
        self.users = {
            "1234567890": {
                "authenticated": False,
                "secret_key": "secretkey123"
            }
        }

    def make_challenge(self, user_id):
        """ Generate a challenge for a user based on the secret key. """
        if user_id in self.users:
            secret_key = self.users[user_id]['secret_key']
            return generate_challenge(user_id, secret_key)
        return None

    def authenticate_user(self, user_id, response, secret_key):
        """ Authenticate a user based on the challenge-response mechanism. """
        logger.info(f"Authenticating user: {user_id} with response: {response}")
        if user_id not in self.users:
            self.users[user_id] = {'authenticated': False, 'secret_key': secret_key}
        
        # Validate the response using HMAC
        expected_response = self.make_challenge(user_id)
        if hmac.compare_digest(expected_response, response):
            self.users[user_id]['authenticated'] = True
            return True
        return False

    def logout_user(self, user_id):
        """ Log out a user """
        logger.info(f"Logging out user: {user_id}")
        if user_id in self.users:
            self.users[user_id]['authenticated'] = False
            return True
        return False

    def get_user_status(self, user_id):
        """ Retrieve the authentication status of a user """
        if user_id in self.users:
            return self.users[user_id]['authenticated']
        return False

# Class for managing the BMS connections
class BMSConnectionManager:
    def __init__(self):
        self.bms_connections = {}

    def register_bms(self, bms_id, websocket):
        """ Register a BMS connection. """
        logger.info(f"Registering BMS: {bms_id}")
        self.bms_connections[bms_id] = websocket

    def get_bms_connection(self, bms_id):
        """ Retrieve the BMS connection. """
        return self.bms_connections.get(bms_id)

    def deregister_bms(self, bms_id):
        """ Deregister a BMS connection. """
        if bms_id in self.bms_connections:
            logger.info(f"Deregistering BMS: {bms_id}")
            del self.bms_connections[bms_id]

# Class for message processing and routing
class MessageRouter:
    def __init__(self, user_manager: UserManager, bms_manager: BMSConnectionManager):
        self.user_manager = user_manager
        self.bms_manager = bms_manager

    async def handle_message(self, websocket, message):
        """ Handle incoming messages and route them accordingly. """
        try:
            msg = json.loads(message)
            packet_id = msg.get("packet_id")
            msg_type = msg.get("type")

            logger.info(f"Received message type: {msg_type} with packet_id: {packet_id}")

            if msg_type == "bms_register":
                await self.process_bms_register(msg, websocket)
            elif msg_type == "auth":
                await self.process_authentication(msg)
            elif msg_type == "auth_response":
                await self.process_auth_response(msg)
            elif msg_type == "auth_logout":
                await self.process_logout(msg)
            elif msg_type == "text":
                await self.process_text_message(msg)
            else:
                logger.error(f"Unknown message type: {msg_type}")

        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def process_bms_register(self, msg, websocket):
        """ Process BMS registration request. """
        bms_id = msg.get("bms_id")
        packet_id = msg.get("packet_id")
        
        logger.info(f"Processing BMS registration for BMS: {bms_id}")
        
        # Register the BMS connection
        self.bms_manager.register_bms(bms_id, websocket)
        
        # Send registration response
        registration_response = {
            "type": "bms_register_response",
            "status": "Registered",
            "bms_id": bms_id,
            "packet_id": packet_id
        }
        await websocket.send(json.dumps(registration_response))

    async def process_authentication(self, msg):
        """ Process authentication request. """
        user_id = msg.get("user_id")
        packet_id = msg.get("packet_id")
        
        logger.info(f"Processing authentication request for user: {user_id}")
        
        # Forward the request to the appropriate BMS
        bms_connection = self.bms_manager.get_bms_connection(msg.get("bms_id"))
        if bms_connection:
            # Generate challenge from user's secret key
            challenge = self.user_manager.make_challenge(user_id)
            auth_msg = {
                "type": "challenge",
                "challenge": challenge,
                "user_id": user_id,
                "packet_id": packet_id
            }
            await bms_connection.send(json.dumps(auth_msg))
        else:
            logger.error(f"BMS connection not found for {user_id}")

    async def process_auth_response(self, msg):
        """ Process authentication response from User Station. """
        user_id = msg.get("user_id")
        response = msg.get("response")
        packet_id = msg.get("packet_id")
        
        logger.info(f"Processing auth response for user: {user_id} with response: {response}")
        
        # Validate authentication
        secret_key = self.user_manager.users.get(user_id, {}).get("secret_key")
        if secret_key and self.user_manager.authenticate_user(user_id, response, secret_key):
            auth_result = {
                "type": "auth_result",
                "status": "Authenticated",
                "user_id": user_id,
                "packet_id": packet_id
            }
            logger.info(f"User {user_id} authenticated successfully")
        else:
            auth_result = {
                "type": "auth_result",
                "status": "Failed",
                "user_id": user_id,
                "packet_id": packet_id
            }
            logger.info(f"User {user_id} authentication failed")

        # Send result back to BMS
        bms_connection = self.bms_manager.get_bms_connection(msg.get("bms_id"))
        if bms_connection:
            await bms_connection.send(json.dumps(auth_result))
        else:
            logger.error(f"BMS connection not found for {user_id}")

    async def process_logout(self, msg):
        """ Process user logout. """
        user_id = msg.get("user_id")
        packet_id = msg.get("packet_id")
        
        if self.user_manager.logout_user(user_id):
            logout_result = {
                "type": "logout_result",
                "status": "Logged out",
                "user_id": user_id,
                "packet_id": packet_id
            }
            logger.info(f"User {user_id} logged out successfully")
        else:
            logout_result = {
                "type": "logout_result",
                "status": "Failed",
                "user_id": user_id,
                "packet_id": packet_id
            }
            logger.info(f"User {user_id} logout failed")

        # Send result back to BMS
        bms_connection = self.bms_manager.get_bms_connection(msg.get("bms_id"))
        if bms_connection:
            await bms_connection.send(json.dumps(logout_result))
        else:
            logger.error(f"BMS connection not found for {user_id}")

    async def process_text_message(self, msg):
        """ Process text messages between users. """
        source_user = msg.get("source_user")
        target_user = msg.get("target_user")
        message = msg.get("message")
        packet_id = msg.get("packet_id")
        
        logger.info(f"Processing text message from {source_user} to {target_user}")

        # Route message to the target BMS
        bms_connection = self.bms_manager.get_bms_connection(msg.get("bms_id"))
        if bms_connection:
            text_msg = {
                "type": "text",
                "source_user": source_user,
                "target_user": target_user,
                "message": message,
                "packet_id": packet_id
            }
            await bms_connection.send(json.dumps(text_msg))
        else:
            logger.error(f"BMS connection not found for {source_user}")

# Instantiate shared managers and router
user_manager = UserManager()
bms_manager = BMSConnectionManager()
message_router = MessageRouter(user_manager, bms_manager)

async def websocket_handler(websocket, path):
    """Handle WebSocket connections and messages."""
    logger.info(f"New connection from {websocket.remote_address}")
    try:
        async for message in websocket:
            await message_router.handle_message(websocket, message)
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Connection closed: {e}")
    finally:
        logger.info(f"Connection from {websocket.remote_address} closed.")

async def start_server(host: str, port: int):
    """Start the WebSocket server."""
    server = await websockets.serve(
        websocket_handler,
        host, port
    )
    logger.info(f"MSC WebSocket server started on ws://{host}:{port}")
    await server.wait_closed()

def main(host: str, port: int):
    asyncio.run(start_server(host, port))
