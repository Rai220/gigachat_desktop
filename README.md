# GigaChat Desktop

A minimal desktop chat application that connects to GigaChat using LangGraph's ReAct agent.

## Requirements
- Python 3.10+
- A valid `GIGACHAT_CREDENTIALS` value for [GigaChat](https://developers.sber.ru/gigachat/)

Install dependencies using [uv](https://github.com/astral-sh/uv):

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Running
Create a `.env` file based on `.env.example` containing your `GIGACHAT_CREDENTIALS`, then run the application:

```bash
python3 -m gigachat_desktop.app
```

The application launches a simple Tkinter window where you can chat with the agent. The agent is built using `langgraph.create_react_agent` with a web search tool.

## Notes
- Currently tested on macOS but it should work on any platform with Python and Tkinter installed.
