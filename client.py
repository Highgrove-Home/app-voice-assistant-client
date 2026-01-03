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

    # Linux - try PulseAudio first, then fall back to custom ALSA track
    pulse_source = os.environ.get("PULSE_SOURCE", "default")
    try:
        print(f"🎤 Trying MediaPlayer with PulseAudio source: {pulse_source}")
        player = MediaPlayer(
            f"pulse:{pulse_source}",
            format="pulse",
            options={"sample_rate": "16000", "channels": "1"},
        )
        if player.audio:
            print("✅ Using PulseAudio via MediaPlayer")
            return player.audio
    except Exception as e:
        print(f"⚠️  PulseAudio not available: {e}")

    # Fallback to custom ALSA track
    print("🎤 Falling back to custom FFmpegAlsaTrack")
    from audio_linux import FFmpegAlsaTrack
    alsa_dev = os.environ.get("ALSA_DEVICE", "plughw:1,0")
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
        print(f"📡 Data channel opened, sending room={ROOM}")
        dc.send(json.dumps({"room": ROOM, "client": "python-room-client"}))

    audio_track = build_mic_track()
    if not audio_track:
        raise RuntimeError("No audio track from microphone capture")

    sender = pc.addTrack(audio_track)
    print(f"🎵 Audio track added to peer connection: {audio_track}")

    @pc.on("track")
    def on_track(track):
        print(f"📥 Received track from server: {track.kind}")

        @track.on("ended")
        async def on_ended():
            print(f"📥 Track ended: {track.kind}")

        # Start consuming the incoming audio track (bot voice)
        async def consume_audio():
            try:
                while True:
                    frame = await track.recv()
                    # For now, just discard (you could play this through speakers later)
                    if hasattr(frame, 'pts'):
                        pass  # Silently consume
            except Exception as e:
                print(f"📥 Incoming audio ended: {e}")

        asyncio.create_task(consume_audio())

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"🔗 Connection state: {pc.connectionState}")

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"🧊 ICE connection state: {pc.iceConnectionState}")

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Debug: check if audio is in the SDP
    if "m=audio" in pc.localDescription.sdp:
        print("✅ Audio media in SDP offer")
        # Check for PCMU/PCMA codecs
        for line in pc.localDescription.sdp.split('\n'):
            if 'a=rtpmap' in line and 'audio' in pc.localDescription.sdp[:pc.localDescription.sdp.index(line)]:
                print(f"   Codec: {line.strip()}")
    else:
        print("⚠️  WARNING: No audio media in SDP offer!")

    payload = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

    async with aiohttp.ClientSession() as session:
        async with session.post(OFFER_URL, json=payload) as resp:
            # If server returns non-JSON errors, we want to see them clearly
            text = await resp.text()
            if resp.status >= 400:
                raise RuntimeError(f"Offer failed ({resp.status}): {text}")
            answer = json.loads(text)

    await pc.setRemoteDescription(RTCSessionDescription(answer["sdp"], answer["type"]))

    # Check negotiated codec
    print("🔍 Checking negotiated transceivers...")
    for transceiver in pc.getTransceivers():
        if transceiver.sender and transceiver.sender.track:
            print(f"   Sender track: {transceiver.sender.track.kind}")
            if hasattr(transceiver, '_sender') and hasattr(transceiver._sender, '_codec'):
                print(f"   Negotiated codec: {transceiver._sender._codec}")

    print(f"✅ Connected via WebRTC to {OFFER_URL} (room={ROOM})")

    # Monitor connection and RTP stats
    async def monitor():
        await asyncio.sleep(5)
        print(f"\n🔍 5s check - Connection: {pc.connectionState}, ICE: {pc.iceConnectionState}")
        # Check if the track is still active
        if hasattr(audio_track, '_pts'):
            print(f"🔍 Audio track pts: {audio_track._pts} (frames generated: {audio_track._pts // 320})")

        # Check RTP stats
        stats = await pc.getStats()
        for stat in stats.values():
            if stat.type == 'outbound-rtp' and stat.kind == 'audio':
                print(f"🔍 RTP packets sent: {stat.packetsSent}, bytes: {stat.bytesSent}")

        await asyncio.sleep(5)
        print(f"\n🔍 10s check - Connection: {pc.connectionState}, ICE: {pc.iceConnectionState}")
        if hasattr(audio_track, '_pts'):
            print(f"🔍 Audio track pts: {audio_track._pts} (frames generated: {audio_track._pts // 320})")

        stats = await pc.getStats()
        for stat in stats.values():
            if stat.type == 'outbound-rtp' and stat.kind == 'audio':
                print(f"🔍 RTP packets sent: {stat.packetsSent}, bytes: {stat.bytesSent}")

    asyncio.create_task(monitor())

    # Keep alive forever
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())