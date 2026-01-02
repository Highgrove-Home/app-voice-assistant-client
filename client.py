import os
import json
import asyncio
import platform
import aiohttp

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer
from audio_linux import FFmpegAlsaTrack

ROOM = os.environ.get("ROOM", "bedroom")
SERVER = os.environ.get("PIPECAT_SERVER", "http://pi-voice.local:7860").rstrip("/")
OFFER_URL = f"{SERVER}/api/offer"

def build_mic_track():
    sys = platform.system().lower()

    if sys == "darwin":
        audio_index = os.environ.get("MAC_AUDIO_INDEX", "0")
        player = MediaPlayer(
            f":{audio_index}",
            format="avfoundation",
            options={"sample_rate": "16000", "channels": "1"},
        )
        if not player.audio:
            raise RuntimeError("No audio track from macOS microphone")
        return player.audio

    # Linux
    alsa_dev = os.environ.get("ALSA_DEVICE", "hw:1,0")
    return FFmpegAlsaTrack(
        device=alsa_dev,
        sample_rate=16000,
        channels=1,
    )

async def main():
    pc = RTCPeerConnection()

    # Data channel for metadata (room, etc.)
    dc = pc.createDataChannel("meta")

    @dc.on("open")
    def on_open():
        dc.send(json.dumps({"room": ROOM, "client": "python-room-client"}))

    audio_track = build_mic_track()
    if not audio_track:
        raise RuntimeError("No audio track from microphone capture")

    pc.addTrack(audio_track)

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