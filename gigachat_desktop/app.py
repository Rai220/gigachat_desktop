import os
import threading
import base64
import io
import sqlite3
import tkinter as tk
from tkinter import scrolledtext, simpledialog
from pathlib import Path

from dotenv import load_dotenv
from PIL import ImageGrab

from langgraph.prebuilt import create_react_agent
from langchain_gigachat import GigaChat
from gigachat.utils.credentials import GigaChatCredentials
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool


class ChatDB:
    """Simple SQLite-based storage for chats and messages."""

    def __init__(self, path: Path):
        self.conn = sqlite3.connect(path)
        self._create_tables()

    def _create_tables(self) -> None:
        with self.conn:
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS chats (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, role TEXT, content TEXT, attachment BLOB, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
            )
            self.conn.execute(
                "CREATE TABLE IF NOT EXISTS mcp_servers (id INTEGER PRIMARY KEY AUTOINCREMENT, address TEXT)"
            )

    def create_chat(self, title: str) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO chats (title) VALUES (?)", (title,))
            return cur.lastrowid

    def add_message(
        self, chat_id: int, role: str, content: str, attachment: bytes | None = None
    ) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO messages (chat_id, role, content, attachment) VALUES (?, ?, ?, ?)",
                (chat_id, role, content, attachment),
            )

    def get_chats(self):
        with self.conn:
            return self.conn.execute(
                "SELECT id, title FROM chats ORDER BY id DESC"
            ).fetchall()

    def get_messages(self, chat_id: int):
        with self.conn:
            return self.conn.execute(
                "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY id",
                (chat_id,),
            ).fetchall()

    def add_server(self, address: str) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO mcp_servers (address) VALUES (?)", (address,)
            )

    def get_servers(self):
        with self.conn:
            return [
                row[0]
                for row in self.conn.execute(
                    "SELECT address FROM mcp_servers"
                ).fetchall()
            ]


def build_agent(prompt_credentials: bool = True) -> "langgraph.Graph":
    """Create a simple ReAct agent using GigaChat and a search tool."""
    load_dotenv()
    creds = os.environ.get("GIGACHAT_CREDENTIALS")
    if not creds and prompt_credentials:
        root = tk.Tk()
        root.withdraw()
        creds = simpledialog.askstring(
            "Credentials",
            "Enter GIGACHAT_CREDENTIALS (client_id:client_secret)",
        )
        root.destroy()
        if creds:
            with open(Path(".env"), "a", encoding="utf-8") as f:
                f.write(f"GIGACHAT_CREDENTIALS={creds}\n")
            os.environ["GIGACHAT_CREDENTIALS"] = creds

    if not creds:
        raise RuntimeError("GIGACHAT_CREDENTIALS must be set")

    if ":" not in creds:
        raise RuntimeError(
            "GIGACHAT_CREDENTIALS must be in 'client_id:client_secret' format"
        )
    client_id, client_secret = creds.split(":", 1)

    credentials = GigaChatCredentials(
        client_id=client_id,
        client_secret=client_secret,
        scope="GIGACHAT_API_PERS",
    )

    llm = GigaChat(credentials=credentials, verify_ssl_certs=False)
    search = DuckDuckGoSearchRun()
    tools = [
        Tool(
            name="search",
            func=search.run,
            description="Search the web using DuckDuckGo",
        )
    ]

    agent_graph = create_react_agent(llm, tools)
    return agent_graph.compile()


class ChatUI:
    def __init__(self, runner: "langgraph.Graph") -> None:
        self.runner = runner
        self.db = ChatDB(Path(__file__).resolve().parent.parent / "chat.db")
        self.root = tk.Tk()
        self.root.title("GigaChat Desktop")

        self.left = tk.Frame(self.root)
        self.left.pack(side=tk.LEFT, fill=tk.Y)

        self.chat_list = tk.Listbox(self.left)
        self.chat_list.pack(fill=tk.BOTH, expand=True)
        self.chat_list.bind("<<ListboxSelect>>", self.on_chat_select)

        tk.Button(self.left, text="New Chat", command=self.new_chat).pack(fill=tk.X)
        tk.Button(self.left, text="Add MCP Server", command=self.add_server).pack(
            fill=tk.X
        )

        self.right = tk.Frame(self.root)
        self.right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.text = scrolledtext.ScrolledText(self.right, wrap=tk.WORD, height=20)
        self.text.pack(fill=tk.BOTH, expand=True)

        self.entry_frame = tk.Frame(self.right)
        self.entry_frame.pack(fill=tk.X)

        self.entry = tk.Entry(self.entry_frame)
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.entry.bind("<Return>", lambda event: self.send())

        self.attach_var = tk.BooleanVar()
        tk.Checkbutton(
            self.entry_frame, text="Attach Screenshot", variable=self.attach_var
        ).pack(side=tk.LEFT)

        self.send_button = tk.Button(self.entry_frame, text="Send", command=self.send)
        self.send_button.pack(side=tk.RIGHT)

        self.current_chat: int | None = None
        self.load_chats()

    def load_chats(self) -> None:
        self.chat_list.delete(0, tk.END)
        for chat_id, title in self.db.get_chats():
            self.chat_list.insert(tk.END, f"{chat_id}: {title}")

    def on_chat_select(self, event) -> None:
        if not self.chat_list.curselection():
            return
        value = self.chat_list.get(self.chat_list.curselection()[0])
        chat_id = int(value.split(":", 1)[0])
        self.current_chat = chat_id
        self.load_messages(chat_id)

    def load_messages(self, chat_id: int) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        for role, content in self.db.get_messages(chat_id):
            prefix = "You" if role == "user" else "Agent"
            self.text.insert(tk.END, f"{prefix}: {content}\n")
        self.text.configure(state=tk.DISABLED)
        self.text.yview(tk.END)

    def new_chat(self) -> None:
        title = simpledialog.askstring("New Chat", "Chat title:")
        if not title:
            return
        chat_id = self.db.create_chat(title)
        self.load_chats()
        # select the newly created chat
        for index, (cid, _) in enumerate(self.db.get_chats()):
            if cid == chat_id:
                self.chat_list.select_clear(0, tk.END)
                self.chat_list.select_set(index)
                self.on_chat_select(None)
                break

    def add_server(self) -> None:
        addr = simpledialog.askstring("MCP Server", "Server address:")
        if addr:
            self.db.add_server(addr)

    def send(self):
        message = self.entry.get().strip()
        if not message or self.current_chat is None:
            return
        self.entry.delete(0, tk.END)
        attachment = None
        if self.attach_var.get():
            try:
                img = ImageGrab.grab()
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                attachment = buf.getvalue()
                b64 = base64.b64encode(attachment).decode("utf-8")
                message += f"\n[Screenshot attached]"
                message += f"\n{b64}"
            except Exception as exc:
                message += f"\n[Failed to capture screenshot: {exc}]"

        self.append(f"You: {message}\n")
        self.db.add_message(self.current_chat, "user", message, attachment)
        threading.Thread(target=self.respond, args=(message,), daemon=True).start()

    def append(self, text):
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, text)
        self.text.configure(state=tk.DISABLED)
        self.text.yview(tk.END)

    def respond(self, message):
        servers = self.db.get_servers()
        if servers:
            message = message + "\nMCP Servers: " + ", ".join(servers)
        events = list(self.runner.stream({"input": message}))
        output = events[-1]["output"]
        self.db.add_message(self.current_chat, "agent", output)
        self.append(f"Agent: {output}\n")

    def run(self):
        self.root.mainloop()


def main() -> None:
    runner = build_agent()
    ui = ChatUI(runner)
    chats = ui.db.get_chats()
    if not chats:
        # create default chat on first run
        ui.db.create_chat("Chat 1")
        ui.load_chats()
        ui.chat_list.select_set(0)
        ui.on_chat_select(None)
    else:
        ui.chat_list.select_set(0)
        ui.on_chat_select(None)
    ui.run()


if __name__ == "__main__":
    main()
