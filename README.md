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

```bash
uv sync
```

## Usage

```bash
python client.py
```

### Environment Variables

- `ALSA_DEVICE`: ALSA audio device (default: `hw:1,0`)
- `ROOM`: Room identifier (default: `bedroom`)
- `PIPECAT_SERVER`: Pipecat server URL (default: `http://pi-voice.local:7860`)

Example:
```bash
ALSA_DEVICE=hw:2,0 ROOM=kitchen python client.py
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
