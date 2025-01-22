import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
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
    def __init__(self, interface):
        self.interface = interface
        self.packet_id_counter = 0
        self.websocket = None
        self.task_queue = queue.Queue()

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
                    self.interface.ui_queue.put({"action": "authenticated"})
                else:
                    print("Authentication failed!")
            elif data.get("type") == "text":
                source_user = data["source_user"]
                message = data["message"]
                self.interface.ui_queue.put({"action": "message", "source_user": source_user, "message": message})

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

class Interface:
    def __init__(self, user_station):
        self.root = None  # Delay main window creation
        self.login_dialog = None
        self.username = None
        self.password = None
        self.server_url = None
        self.user_station = user_station
        self.messages = {}  # Dictionary to store messages for each user
        self.ui_queue = queue.Queue()  # Queue to receive messages from UserStation

    def init_login_dialog(self):
        # Create a custom dialog for username and password input
        self.login_dialog = tk.Tk()
        self.login_dialog.title("Login")
        self.login_dialog.geometry("150x250")
        self.login_dialog.resizable(False, False)

        tk.Label(self.login_dialog, text="Username:").pack(pady=(10, 0))
        username_entry = tk.Entry(self.login_dialog)
        username_entry.pack(pady=5)

        tk.Label(self.login_dialog, text="Password:").pack(pady=(10, 0))
        password_entry = tk.Entry(self.login_dialog, show="*")
        password_entry.pack(pady=5)

        tk.Label(self.login_dialog, text="Server URL:").pack(pady=(10, 0))
        server_entry = tk.Entry(self.login_dialog)
        server_entry.pack(pady=5)

        def submit_credentials():
            self.username = username_entry.get().strip()
            self.password = password_entry.get().strip()
            self.server_url = server_entry.get().strip()
            if self.username and self.password and self.server_url:
                self.user_station.task_queue.put({"action": "connect"})
            else:
                messagebox.showerror("Error", "All fields are required!")

        submit_button = tk.Button(self.login_dialog, text="Login", command=submit_credentials)
        submit_button.pack(pady=10)

        # Start checking the UI queue
        self.start_ui_queue_check(self.login_dialog)

        # Run the login dialog loop
        self.login_dialog.mainloop()

        # Exit if login is not completed successfully
        if not self.username or not self.password:
            exit()

    def start_ui_queue_check(self, window):
        def check_ui_queue():
            try:
                message = self.ui_queue.get_nowait()
                if message["action"] == "authenticated":
                    self.login_dialog.destroy()
                    self.create_main_window()
                elif message["action"] == "message":
                    source_user = message["source_user"]
                    message = message["message"]
                    formatted_message = f"{source_user}: {message}"
                    if source_user in self.messages:
                        self.messages[source_user].append(formatted_message)
                    else:
                        self.messages[source_user] = [formatted_message]
                    if self.selected_user == source_user:
                        self.display_message(formatted_message)
            except queue.Empty:
                pass
            window.after(100, check_ui_queue)  # Check the queue periodically

        check_ui_queue()

    def create_main_window(self):
        # Create the main application window
        self.root = tk.Tk()
        self.root.title("Chat App")
        self.create_main_ui()
        self.start_ui_queue_check(self.root)  # Start checking the UI queue in the main window
        self.root.mainloop()

    def create_main_ui(self):
        # Main Frame
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # Left pane (User list and New Chat button)
        self.left_pane = tk.Frame(self.main_frame, width=200, bg="lightgray")
        self.left_pane.grid(row=0, column=0, sticky="nsew")

        # Right pane (Message area)
        self.right_pane = tk.Frame(self.main_frame)
        self.right_pane.grid(row=0, column=1, sticky="nsew")

        # Configure grid weights
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)

        # New Chat button
        self.new_chat_button = tk.Button(
            self.left_pane,
            text="New Chat",
            command=self.on_new_chat
        )
        self.new_chat_button.pack(fill="x", padx=5, pady=5)

        # Listbox for users
        self.users_listbox = tk.Listbox(self.left_pane)
        self.users_listbox.pack(fill="both", expand=True)
        self.users_listbox.bind("<<ListboxSelect>>", self.on_user_select)

        # Right pane components (message display area)
        self.message_area = tk.Text(
            self.right_pane,
            state=tk.DISABLED,
            wrap=tk.WORD,
            height=20,
            width=50
        )
        self.message_area.pack(side="top", fill="both", expand=True)

        # Message input box
        self.message_input = tk.Entry(self.right_pane, width=50)
        self.message_input.pack(side="bottom", fill="x", padx=5, pady=5)
        self.message_input.bind("<Return>", self.on_send_message)

        self.selected_user = None

    def on_new_chat(self):
        # Prompt user for a new chat ID and add it to the listbox
        recipient = simpledialog.askstring("New Chat", "Enter User ID to chat with:")
        if recipient and recipient not in self.users_listbox.get(0, tk.END):
            self.users_listbox.insert(tk.END, recipient)
            self.messages[recipient] = []  # Initialise message list for the new user

    def on_user_select(self, event):
        # Handle user selection from the listbox
        selected_index = self.users_listbox.curselection()
        if selected_index:
            self.selected_user = self.users_listbox.get(selected_index[0])
            self.update_message_area()

    def update_message_area(self):
        # Clear the message area and populate with selected user's messages
        self.message_area.config(state=tk.NORMAL)
        self.message_area.delete(1.0, tk.END)
        if self.selected_user in self.messages:
            for message in self.messages[self.selected_user]:
                self.message_area.insert(tk.END, message + "\n")
        self.message_area.config(state=tk.DISABLED)
        self.message_area.yview(tk.END)

    def on_send_message(self, event=None):
        if self.selected_user:
            message = self.message_input.get().strip()
            if message:
                formatted_message = f"You: {message}"
                self.messages[self.selected_user].append(formatted_message)
                self.display_message(formatted_message)
                self.message_input.delete(0, tk.END)
                self.user_station.task_queue.put({"action": "text", "target_user": self.selected_user, "message": message})

    def display_message(self, message):
        self.message_area.config(state=tk.NORMAL)
        self.message_area.insert(tk.END, message + "\n")
        self.message_area.config(state=tk.DISABLED)
        self.message_area.yview(tk.END)

if __name__ == "__main__":
    user_station = UserStation(None)
    threading.Thread(target=user_station.start, daemon=True).start()
    interface = Interface(user_station)
    user_station.interface = interface
    interface.init_login_dialog()
