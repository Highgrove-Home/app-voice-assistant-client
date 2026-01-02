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

## Hardware Setup

The client is designed to work with ReSpeaker devices, which provide:
- Multi-channel microphone array
- Echo cancellation
- Beam forming for voice detection
- Audio output capabilities
