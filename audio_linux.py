import asyncio
import subprocess
from typing import Optional

import numpy as np
from aiortc import MediaStreamTrack
from av import AudioFrame


class FFmpegAlsaTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, device: str, sample_rate: int = 16000, channels: int = 1):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels

        # 16-bit little-endian PCM
        self.bytes_per_sample = 2
        self.frame_samples = 960  # 60ms @ 16k (safe). We can tune later.
        self.frame_bytes = self.frame_samples * self.channels * self.bytes_per_sample

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "alsa",
            "-i", device,
            "-ac", str(channels),
            "-ar", str(sample_rate),
            "-f", "s16le",
            "pipe:1",
        ]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, bufsize=0)
        self._pts = 0

    async def recv(self) -> AudioFrame:
        assert self.proc.stdout is not None
        data = await asyncio.get_event_loop().run_in_executor(None, self.proc.stdout.read, self.frame_bytes)
        if not data or len(data) < self.frame_bytes:
            raise asyncio.CancelledError("Audio capture ended")

        # Convert bytes -> numpy int16
        samples = np.frombuffer(data, dtype=np.int16)

        frame = AudioFrame(format="s16", layout="mono" if self.channels == 1 else "stereo", samples=self.frame_samples)
        frame.planes[0].update(samples.tobytes())

        frame.sample_rate = self.sample_rate
        frame.pts = self._pts
        frame.time_base = (1, self.sample_rate)
        self._pts += self.frame_samples
        return frame

    def stop(self):
        super().stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()