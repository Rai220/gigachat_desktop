import os
import threading
import tkinter as tk
from tkinter import scrolledtext

from dotenv import load_dotenv

from langgraph.prebuilt import create_react_agent
from langchain_gigachat import GigaChat
from gigachat.utils.credentials import GigaChatCredentials
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.agents import Tool


def build_agent() -> "langgraph.Graph":
    """Create a simple ReAct agent using GigaChat and a search tool."""
    load_dotenv()
    client_id = os.environ.get("GIGACHAT_CLIENT_ID")
    client_secret = os.environ.get("GIGACHAT_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise RuntimeError(
            "GIGACHAT_CLIENT_ID and GIGACHAT_CLIENT_SECRET must be set"
        )

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
            description="Search the web using DuckDuckGo"
        )
    ]

    agent_graph = create_react_agent(llm, tools)
    return agent_graph.compile()


class ChatUI:
    def __init__(self, runner):
        self.runner = runner
        self.root = tk.Tk()
        self.root.title("GigaChat Desktop")

        self.text = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=20)
        self.text.pack(fill=tk.BOTH, expand=True)

        self.entry = tk.Entry(self.root)
        self.entry.pack(fill=tk.X, side=tk.LEFT, expand=True)
        self.entry.bind("<Return>", lambda event: self.send())

        self.send_button = tk.Button(self.root, text="Send", command=self.send)
        self.send_button.pack(side=tk.RIGHT)

    def send(self):
        message = self.entry.get().strip()
        if not message:
            return
        self.entry.delete(0, tk.END)
        self.append(f"You: {message}\n")
        threading.Thread(target=self.respond, args=(message,), daemon=True).start()

    def append(self, text):
        self.text.configure(state=tk.NORMAL)
        self.text.insert(tk.END, text)
        self.text.configure(state=tk.DISABLED)
        self.text.yview(tk.END)

    def respond(self, message):
        events = list(self.runner.stream({"input": message}))
        output = events[-1]["output"]
        self.append(f"Agent: {output}\n")

    def run(self):
        self.root.mainloop()


def main():
    runner = build_agent()
    ui = ChatUI(runner)
    ui.run()


if __name__ == "__main__":
    main()
