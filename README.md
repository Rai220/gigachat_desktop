# GigaChat Desktop

A minimal desktop chat application that connects to GigaChat using LangGraph's ReAct agent.

## Requirements
- Python 3.10+
- A valid `GIGACHAT_API_KEY` for [GigaChat](https://developers.sber.ru/gigachat/)

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Running
Set the `GIGACHAT_API_KEY` environment variable and run the application:

```bash
export GIGACHAT_API_KEY=your_token_here
python3 -m gigachat_desktop.app
```

The application launches a simple Tkinter window where you can chat with the agent. The agent is built using `langgraph.create_react_agent` with a web search tool.

## Notes
- Currently tested on macOS but it should work on any platform with Python and Tkinter installed.
