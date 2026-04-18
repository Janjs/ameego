# Ameego

A local-first Raspberry Pi voice assistant built in Python. It listens for a wake word with `openWakeWord`, sends recorded speech to OpenAI for transcription and response generation, speaks replies through your AUX speakers, and can render animated robot eyes on a Pi-connected display.

## Proposed file tree

```text
ameego/
├── .env.example
├── Makefile
├── README.md
├── assistant.py
├── audio.py
├── config.py
├── eyes.py
├── llm.py
├── requirements.txt
├── stt.py
├── test_audio_devices.py
├── test_eyes.py
├── tts.py
├── wakeword.py
├── deploy/
│   └── ameego.service
└── scripts/
    └── start_ameego.sh
```

## Features

- Wake-word pipeline with `openWakeWord`
- Push-to-talk fallback mode for debugging over SSH
- Dry-run diagnostics mode for mic, speaker, and OpenAI connectivity
- Pi-native animated robot eyes using `pygame`
- Environment-driven configuration
- Systemd service for long-lived operation
- ALSA-friendly device configuration and troubleshooting commands

## Architecture

1. `wakeword.py` monitors the microphone for a wake-word score.
2. `audio.py` records the user query until silence.
3. `stt.py` sends the WAV recording to OpenAI transcription.
4. `llm.py` asks an OpenAI chat/reasoning model for a short spoken answer.
5. `tts.py` synthesizes a WAV reply with OpenAI TTS.
6. `audio.py` plays the response through the configured AUX output.
7. `eyes.py` animates visual states alongside the voice pipeline.

## Raspberry Pi setup

The commands below assume:

- Pi hostname or IP is reachable over SSH
- Python 3.11+ is installed
- Your USB mic should be `card 2, device 0`
- Your AUX output should be `card 1, device 0`

### 1. Copy the project to the Pi

From this computer:

```bash
rsync -av --delete /Users/jan/Developer/ameego/ pi@YOUR_PI_HOST:~/ameego/
```

Or with plain `scp`:

```bash
scp -r /Users/jan/Developer/ameego pi@YOUR_PI_HOST:~/
```

### 2. SSH into the Pi

```bash
ssh pi@YOUR_PI_HOST
cd ~/ameego
```

### 3. Install system packages

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip \
  portaudio19-dev libportaudio2 libsndfile1 \
  libsdl2-2.0-0 libsdl2-dev ffmpeg \
  libatlas-base-dev libopenblas-dev \
  alsa-utils
```

If `openWakeWord` or ONNX wheels are troublesome on your Pi image, install `tflite-runtime` manually inside the virtualenv after the main dependency install.

### 4. Create a virtualenv and install Python dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

If needed for Raspberry Pi:

```bash
pip install tflite-runtime
```

### 5. Configure environment variables

```bash
cp .env.example .env
nano .env
```

Minimum `.env` changes:

- Set `OPENAI_API_KEY`
- Confirm `AUDIO_INPUT_DEVICE=plughw:2,0`
- Confirm `AUDIO_OUTPUT_DEVICE=plughw:1,0`
- Decide whether `EYES_ENABLED=true`

### 6. Inspect devices

```bash
source .venv/bin/activate
python assistant.py --list-devices
arecord -l
aplay -l
```

### 7. Run dry-run diagnostics

```bash
source .venv/bin/activate
python assistant.py --dry-run --disable-eyes
```

This should:

- list audio devices
- record a short mic sample
- transcribe it with OpenAI
- synthesize a short spoken confirmation
- play the result through the configured speaker device

### 8. Test eyes

Windowed on desktop:

```bash
source .venv/bin/activate
python test_eyes.py --windowed
```

Fullscreen on Pi display:

```bash
source .venv/bin/activate
python test_eyes.py
```

### 9. Run assistant in push-to-talk mode first

```bash
source .venv/bin/activate
python assistant.py --push-to-talk --disable-eyes
```

Press Enter, ask a question, wait for the reply, then type `q` to quit.

### 10. Run the full wake-word loop

```bash
source .venv/bin/activate
python assistant.py
```

If you do not yet have a custom `"Hey Nomi"` model, the app falls back to the built-in `openWakeWord` model named in `WAKEWORD_BUILTIN_MODEL` (default: `hey_jarvis`). Later, place your custom model file on the Pi and set:

```env
WAKEWORD_MODEL_PATH=/home/pi/ameego/models/hey_nomi.onnx
```

## Smoke test checklist

1. Verify mic:

```bash
python test_audio_devices.py --record-seconds 3
```

2. Verify playback:

```bash
python test_audio_devices.py --play-tone
```

3. Verify STT:

```bash
python assistant.py --dry-run --disable-eyes
```

4. Verify TTS:

`--dry-run` also checks TTS and playback.

5. Verify eyes:

```bash
python test_eyes.py --windowed
```

6. Verify full cycle:

```bash
python assistant.py --push-to-talk
python assistant.py
```

## Systemd

Install the bundled service file:

```bash
sudo cp deploy/ameego.service /etc/systemd/system/ameego.service
sudo systemctl daemon-reload
sudo systemctl enable ameego.service
sudo systemctl start ameego.service
sudo systemctl status ameego.service
```

Logs:

```bash
journalctl -u ameego.service -f
```

## Start script

The provided start script activates the virtualenv, loads `.env`, and launches the assistant:

```bash
./scripts/start_ameego.sh --disable-eyes
```

## ALSA troubleshooting

- If playback is silent, confirm `aplay -l` still shows the analog output at `card 1, device 0`.
- If recording fails, confirm `arecord -l` still shows the USB microphone at `card 2, device 0`.
- Try `plughw:2,0` and `plughw:1,0` before raw `hw:` devices to reduce format mismatch problems.
- If `sounddevice` lists a different device name than expected, copy that exact name into `.env`.
- If the assistant hears itself, increase `PLAYBACK_COOLDOWN_SECONDS` to `1.5` or `2.0`.
- If wake-word detection feels too eager or too sluggish, tune `WAKEWORD_THRESHOLD` up or down by `0.05`.
- If `pygame` fails over SSH without a display, run with `--disable-eyes` or export `SDL_VIDEODRIVER=dummy`.
- If your Pi uses PipeWire or PulseAudio on top of ALSA, double-check which backend `sounddevice` resolves to when you list devices.

## Notes on the eye renderer

The Pi implementation is native Python and only visually inspired by FluxGarage RoboEyes. It does not depend on the Arduino library. The renderer is intentionally separated so you can later swap it for an SPI OLED/TFT or microcontroller-driven display path.
