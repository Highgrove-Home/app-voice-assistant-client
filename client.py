import os
import json
import asyncio
import platform
import aiohttp

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

ROOM = os.environ.get("ROOM", "bedroom")
SERVER = os.environ.get("PIPECAT_SERVER", "http://pi-voice.local:7860").rstrip("/")
OFFER_URL = f"{SERVER}/api/offer"

def build_mic_player():
    """
    Mic capture:
      - macOS: avfoundation "default"
      - Linux: ALSA device from env ALSA_DEVICE (e.g. "hw:1,0" or "default")
    """
    sys = platform.system().lower()

    if sys == "darwin":
        audio_index = os.environ.get("MAC_AUDIO_INDEX", "0")
        return MediaPlayer(
            f":{audio_index}",
            format="avfoundation",
            options={"sample_rate": "16000", "channels": "1"},
        )

    # Linux: PulseAudio device from env PULSE_DEVICE (e.g. "default" or "hw:1,0")
    pulse_dev = os.environ.get("PULSE_DEVICE", "default")
    return MediaPlayer(
        pulse_dev,
        format="pulse",
        options={"sample_rate": "16000", "channels": "1"},
    )

async def main():
    pc = RTCPeerConnection()

    # Data channel for metadata (room, etc.)
    dc = pc.createDataChannel("meta")

    @dc.on("open")
    def on_open():
        dc.send(json.dumps({"room": ROOM, "client": "python-room-client"}))

    player = build_mic_player()
    if not player.audio:
        raise RuntimeError("No audio track from microphone capture")

    pc.addTrack(player.audio)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async with aiohttp.ClientSession() as session:
        async with session.post(OFFER_URL, json=payload) as resp:
            # If server returns non-JSON errors, we want to see them clearly
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Offer failed ({resp.status}): {text}")
            answer = json.loads(text)

    await pc.setRemoteDescription(RTCSessionDescription(answer["sdp"], answer["type"]))
    print(f"✅ Connected via WebRTC to {OFFER_URL} (room={ROOM})")

    # Keep alive forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())