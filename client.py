import os
import json
import asyncio
import platform
import aiohttp
import time

from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaPlayer

ROOM = os.environ.get("ROOM", "bedroom")
SERVER = os.environ.get("PIPECAT_SERVER", "http://pi-voice.local:7860").rstrip("/")
OFFER_URL = f"{SERVER}/api/offer"
HEALTHCHECK_INTERVAL = int(os.environ.get("HEALTHCHECK_INTERVAL", "5"))
HEALTHCHECK_TIMEOUT = int(os.environ.get("HEALTHCHECK_TIMEOUT", "30"))

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

    # Linux - fall back to custom ALSA track with proper timing
    print("🎤 Using custom FFmpegAlsaTrack with real-time pacing")
    from audio_linux import FFmpegAlsaTrack
    alsa_dev = os.environ.get("ALSA_DEVICE", "plughw:1,0")
    return FFmpegAlsaTrack(
        device=alsa_dev,
        sample_rate=16000,
        channels=1,
    )

async def connect_to_server():
    """Attempt to connect to the server and maintain the connection"""
    pc = RTCPeerConnection()
    connection_closed = asyncio.Event()
    last_pong_time = {"time": time.time()}

    # Data channel for metadata (room, etc.)
    dc = pc.createDataChannel("meta")

    @dc.on("open")
    def on_open():
        print(f"📡 Data channel opened, sending room={ROOM}")
        dc.send(json.dumps({"room": ROOM, "client": "python-room-client"}))
        # Reset pong timer on channel open
        last_pong_time["time"] = time.time()

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
                    # Update last activity time on incoming audio
                    last_activity["time"] = time.time()
                    # For now, just discard (you could play this through speakers later)
                    if hasattr(frame, 'pts'):
                        pass  # Silently consume
            except Exception as e:
                print(f"📥 Incoming audio ended: {e}")

        asyncio.create_task(consume_audio())

    last_activity = {"time": time.time()}

    @dc.on("message")
    def on_dc_message(message):
        # Update last activity time on any message
        last_activity["time"] = time.time()

        # Handle pong responses
        try:
            data = json.loads(message)
            if isinstance(data, dict) and data.get("type") == "pong":
                last_pong_time["time"] = time.time()
                print(f"🏓 Pong received")
        except (json.JSONDecodeError, TypeError):
            # Not JSON or not a pong, ignore
            pass

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"🔗 Connection state: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed", "disconnected"]:
            print("⚠️  Connection failed/closed/disconnected, will reconnect...")
            connection_closed.set()

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"🧊 ICE connection state: {pc.iceConnectionState}")
        if pc.iceConnectionState in ["failed", "closed", "disconnected"]:
            print("⚠️  ICE connection failed/closed/disconnected, will reconnect...")
            connection_closed.set()

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Debug: check if audio is in the SDP
    if "m=audio" in pc.localDescription.sdp:
        print("✅ Audio media in SDP offer")
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

    print(f"✅ Connected via WebRTC to {OFFER_URL} (room={ROOM})")

    # Ping task - send pings every HEALTHCHECK_INTERVAL seconds
    async def ping_task():
        print(f"🏓 Ping task started (interval: {HEALTHCHECK_INTERVAL}s)")
        await asyncio.sleep(2)  # Wait for data channel to be ready

        while not connection_closed.is_set():
            try:
                if dc.readyState == "open":
                    ping_msg = json.dumps({"type": "ping", "timestamp": time.time()})
                    dc.send(ping_msg)
                    print(f"🏓 Ping sent")
                else:
                    print(f"⚠️  Data channel not open (state: {dc.readyState})")
            except Exception as e:
                print(f"⚠️  Failed to send ping: {e}")

            await asyncio.sleep(HEALTHCHECK_INTERVAL)

    # Watchdog to detect dead connections
    async def watchdog():
        print(f"🐕 Watchdog started (checking every 5s, pong timeout: {HEALTHCHECK_TIMEOUT}s)")
        await asyncio.sleep(5)  # Initial delay

        while not connection_closed.is_set():
            await asyncio.sleep(5)

            if connection_closed.is_set():
                break

            time_since_pong = time.time() - last_pong_time["time"]

            # Check connection state
            if pc.connectionState in ["failed", "closed", "disconnected"]:
                print(f"⚠️  Watchdog: Connection state is {pc.connectionState}")
                connection_closed.set()
                break

            if pc.iceConnectionState in ["failed", "closed", "disconnected"]:
                print(f"⚠️  Watchdog: ICE state is {pc.iceConnectionState}")
                connection_closed.set()
                break

            # Check pong timeout
            if time_since_pong > HEALTHCHECK_TIMEOUT:
                print(f"⚠️  Watchdog: No pong for {time_since_pong:.1f}s (timeout: {HEALTHCHECK_TIMEOUT}s) - reconnecting")
                connection_closed.set()
                break

    ping_task_handle = asyncio.create_task(ping_task())
    watchdog_task = asyncio.create_task(watchdog())

    # Wait for connection to close
    await connection_closed.wait()

    # Cancel tasks
    ping_task_handle.cancel()
    watchdog_task.cancel()
    try:
        await ping_task_handle
    except asyncio.CancelledError:
        pass
    try:
        await watchdog_task
    except asyncio.CancelledError:
        pass

    # Clean up
    await pc.close()

    # Stop audio track
    if hasattr(audio_track, 'stop'):
        audio_track.stop()


async def main():
    retry_delay = 5  # seconds

    while True:
        try:
            print(f"🔌 Connecting to {SERVER}...")
            await connect_to_server()
        except Exception as e:
            print(f"❌ Connection error: {e}")
            import traceback
            traceback.print_exc()

        print(f"⏳ Waiting {retry_delay}s before reconnecting...")
        await asyncio.sleep(retry_delay)

if __name__ == "__main__":
    asyncio.run(main())