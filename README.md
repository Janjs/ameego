# Ameego

Ameego is a simple SSH-first Raspberry Pi terminal assistant in Python. You type messages in the terminal, it sends them to OpenAI, and it prints back clear replies while keeping the current conversation in memory.

## File tree

```text
ameego/
├── .env.example
├── Makefile
├── README.md
├── assistant.py
├── config.py
├── llm.py
├── requirements.txt
├── deploy/
│   └── ameego.service
└── scripts/
    └── start_ameego.sh
```

## Features

- Interactive terminal chat over SSH
- One-shot prompt mode for scripting
- Conversation memory during the current session
- Environment-driven configuration
- Minimal Raspberry Pi setup with no audio or display dependencies

## Architecture

1. `assistant.py` runs a simple terminal REPL.
2. `config.py` loads environment variables.
3. `llm.py` sends conversation history to OpenAI and returns the reply.

## Raspberry Pi setup

### 1. Clone the project

```bash
git clone https://github.com/Janjs/ameego.git
cd ~/ameego
```

### 2. Create a virtualenv and install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Minimum `.env` changes:

- Set `OPENAI_API_KEY`
- Optionally change `ROBOT_NAME`
- Optionally change `OPENAI_CHAT_MODEL`

### 4. Run Ameego interactively over SSH

```bash
source .venv/bin/activate
python assistant.py
```

You will see a simple terminal UI:

```text
Ameego terminal chat
Type a message and press Enter.
Commands: /help, /clear, /quit
```

### 5. Run a single prompt

```bash
python assistant.py --text "Summarize why my Raspberry Pi setup kept failing earlier"
```

## Commands inside the terminal app

- `/help` shows commands
- `/clear` clears conversation history
- `/quit` exits the app

## Make targets

```bash
make setup
make run
make once
```

## Notes

- Conversation history is kept only for the current process.
- This version does not use the microphone, speakers, wake word, or eyes.
- The included `deploy/ameego.service` file is left in the repo from the earlier voice-oriented version, but it is not useful for an interactive SSH-only workflow.
