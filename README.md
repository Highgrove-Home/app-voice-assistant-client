# Voice Assistant Client

A thin WebRTC client designed to connect to the [Pipecat](https://github.com/pipecat-ai/pipecat) voice assistant server.

## Overview

This client is meant to run on mini PCs or Linux devices connected to ReSpeaker hardware, enabling voice assistant functionality in different rooms throughout the home.

## Architecture

- **Client**: Lightweight WebRTC client handling audio I/O
- **Server**: Pipecat-based voice assistant server
- **Hardware**: ReSpeaker microphone array for room audio

## Requirements

- Python 3.11+
- ReSpeaker hardware (USB microphone array)
- Network connection to Pipecat server

## Installation

### Quick Setup (New Device)

For setting up a new mini PC or Linux device:

```bash
curl -fsSL https://raw.githubusercontent.com/Highgrove-Home/app-voice-assistant-client/main/scripts/bootstrap.sh | bash
```

This will:
- Install system dependencies (ffmpeg, git)
- Install uv (Python package manager)
- Clone the repository to `/opt/voice-assistant-client`
- Install Python dependencies
- Create a systemd service that starts on boot
- Generate config file at `/etc/voice-assistant-client.env`
- **Optionally** register the device as a GitHub Actions self-hosted runner (prompted during setup)

After bootstrap completes:
1. Run the audio diagnostic to find the correct ALSA device:
   ```bash
   cd /opt/voice-assistant-client
   python scripts/audio_debug.py
   ```
2. Edit `/etc/voice-assistant-client.env` to set:
   - `ROOM`: The room name (e.g., `bedroom`, `kitchen`, `living_room`)
   - `ALSA_DEVICE`: The working device from step 1 (e.g., `plughw:1,0`)
3. Restart the service: `sudo systemctl restart voice-assistant-client`
4. Check logs: `sudo journalctl -u voice-assistant-client -f`

### Manual Installation

```bash
uv sync
```

## Usage

### Running Manually

```bash
python client.py
```

### Running as a Service

The bootstrap script automatically sets up a systemd service. Manage it with:

```bash
# Check status
sudo systemctl status voice-assistant-client

# View logs
sudo journalctl -u voice-assistant-client -f

# Restart
sudo systemctl restart voice-assistant-client

# Stop
sudo systemctl stop voice-assistant-client

# Disable autostart
sudo systemctl disable voice-assistant-client
```

### Environment Variables

- `ALSA_DEVICE`: ALSA audio device (default: `hw:1,0`)
- `ROOM`: Room identifier (default: `bedroom`)
- `PIPECAT_SERVER`: Pipecat server URL (default: `http://pi-voice.local:7860`)
- `HEALTHCHECK_INTERVAL`: Ping interval in seconds (default: `5`)
- `HEALTHCHECK_TIMEOUT`: Pong timeout in seconds (default: `10`)

Example:
```bash
ALSA_DEVICE=hw:2,0 ROOM=kitchen python client.py
```

## Connection Management

The client includes an active healthcheck mechanism to detect server failures:

- **Ping/Pong**: Client sends a ping every 5 seconds (configurable via `HEALTHCHECK_INTERVAL`)
- **Timeout Detection**: If no pong received within 10 seconds (configurable via `HEALTHCHECK_TIMEOUT`), client reconnects
- **Auto-Reconnect**: Client automatically reconnects every 5 seconds after disconnection
- **Connection Monitoring**: Logs show `🏓 Ping sent` and `🏓 Pong received` for visibility

When the server restarts, you'll see:
```
⚠️  Watchdog: No pong for 11.2s (timeout: 10s) - reconnecting
⏳ Waiting 5s before reconnecting...
🔌 Connecting to http://pi-voice.local:7860...
✅ Connected via WebRTC...
```

**Note**: The Pipecat server must respond to ping messages. Add this to your server's data channel handler:
```python
# In your Pipecat server
if message_data.get("type") == "ping":
    await data_channel.send(json.dumps({"type": "pong"}))
```

## Troubleshooting

### No Audio Being Sent

If the server reports no audio frames are being received, run the diagnostic script:

```bash
python scripts/audio_debug.py
```

This will:
1. List all available ALSA devices
2. Test FFmpeg audio capture
3. Provide recommendations

Common issues:
- **Wrong device**: ReSpeaker may not be at `hw:1,0` - check with `arecord -l`
- **Permissions**: User must be in the `audio` group: `sudo usermod -a -G audio $USER`
- **Device in use**: Another process may be using the microphone

## Hardware Setup

The client is designed to work with ReSpeaker devices, which provide:
- Multi-channel microphone array
- Echo cancellation
- Beam forming for voice detection
- Audio output capabilities
