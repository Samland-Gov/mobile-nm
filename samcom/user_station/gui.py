import tkinter as tk
from tkinter import simpledialog, messagebox
import threading
from .core import UserStation, StationInterface


class GuiInterface(StationInterface):
    def __init__(self,):
        super().__init__()
        self.root = None  # Delay main window creation
        self.login_dialog = None

    def process_message(self, message):
        if message["action"] == "message":
            source_user = message["source_user"]
            message = message["message"]
            formatted_message = f"{source_user}: {message}"
            if source_user in self.messages:
                self.messages[source_user].append(formatted_message)
            else:
                self.messages[source_user] = [formatted_message]
            if self.selected_user == source_user:
                self.display_message(formatted_message)

    def process_authenticated(self, message):
        if message["action"] == "authenticated":
            self.login_dialog.destroy()
            self.create_main_window()

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
            self.process_ui_queue()
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


def main():
    interface = GuiInterface()
    user_station = UserStation(interface)
    threading.Thread(target=user_station.start, daemon=True).start()
    interface.init_login_dialog()
