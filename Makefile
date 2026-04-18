PYTHON ?= python3
VENV ?= .venv

.PHONY: setup run dry-run ptt text-chat eyes audio-devices

setup:
	$(PYTHON) -m venv $(VENV)
	. $(VENV)/bin/activate && pip install --upgrade pip wheel setuptools && pip install -r requirements.txt

run:
	. $(VENV)/bin/activate && python assistant.py

dry-run:
	. $(VENV)/bin/activate && python assistant.py --dry-run --disable-eyes

ptt:
	. $(VENV)/bin/activate && python assistant.py --push-to-talk

text-chat:
	. $(VENV)/bin/activate && python assistant.py --text-chat --disable-eyes

eyes:
	. $(VENV)/bin/activate && python test_eyes.py --windowed

audio-devices:
	. $(VENV)/bin/activate && python test_audio_devices.py --play-tone
