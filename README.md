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
- Fullscreen desktop mirror on the Pi display
- Spoken replies through the Pi speaker output

## Architecture

1. `assistant.py` runs a simple terminal REPL.
2. `config.py` loads environment variables.
3. `llm.py` sends conversation history to OpenAI and returns the reply.
4. `assistant.py` mirrors the conversation into a simple fullscreen Tk window on the Pi desktop.
5. `tts.py` sends the reply to OpenAI TTS and plays it with `aplay`.

## Raspberry Pi setup

### 1. Clone the project

```bash
git clone https://github.com/Janjs/ameego.git
cd ~/ameego
```

### 2. Create a virtualenv and install dependencies

```bash
sudo apt install -y alsa-utils
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
- Confirm `AUDIO_OUTPUT_DEVICE=plughw:1,0` for the Pi headphone jack

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

If the Pi is logged into its desktop session, the same conversation will also appear in a fullscreen window on the attached display. While a reply is loading, the Pi screen shows `thinking...`. Press `Esc` on the Pi keyboard to leave fullscreen.
By default, the app assumes `DISPLAY=:0` and `~/.Xauthority`, which matches the common Raspberry Pi desktop setup.

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
- This version does not use the microphone, wake word, or eyes.
- If your Pi uses a different desktop display or Xauthority path, override `APP_UI_DISPLAY` or `APP_UI_XAUTHORITY` in `.env`.
- The included `deploy/ameego.service` file is left in the repo from the earlier voice-oriented version, but it is not useful for an interactive SSH-only workflow.
