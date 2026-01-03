"""
Test if the issue is with our custom track by creating the simplest possible version
"""
import asyncio
import numpy as np
from aiortc import RTCPeerConnection, MediaStreamTrack
from aiortc.contrib.media import MediaRecorder
import av
from fractions import Fraction


class SimpleAudioTrack(MediaStreamTrack):
    """
    Simplest possible audio track - generates silence
    """
    kind = "audio"

    def __init__(self):
        super().__init__()
        self.sample_rate = 16000
        self.samples_per_frame = 320
        self._timestamp = 0

    async def recv(self):
        # Generate 320 samples of silence (20ms at 16kHz)
        samples = np.zeros((1, self.samples_per_frame), dtype=np.int16)

        frame = av.AudioFrame.from_ndarray(samples, format='s16', layout='mono')
        frame.sample_rate = self.sample_rate
        frame.pts = self._timestamp
        frame.time_base = Fraction(1, self.sample_rate)

        self._timestamp += self.samples_per_frame

        # Wait 20ms to maintain real-time
        await asyncio.sleep(0.02)

        if self._timestamp < 16000:  # First second only
            print(f"Generated frame: pts={frame.pts}, timestamp={self._timestamp}")

        return frame


async def test():
    track = SimpleAudioTrack()

    # Try to get a few frames
    for i in range(10):
        frame = await track.recv()
        print(f"Received frame {i}: pts={frame.pts}, samples={frame.samples}")

    print("✅ Track works!")


if __name__ == "__main__":
    asyncio.run(test())
