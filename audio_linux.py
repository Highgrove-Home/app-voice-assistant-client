import asyncio
import subprocess
from typing import Optional

import numpy as np
from aiortc import MediaStreamTrack
from av import AudioFrame
import av
from fractions import Fraction

class FFmpegAlsaTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, device: str, sample_rate: int = 16000, channels: int = 1):
        super().__init__()
        self.sample_rate = sample_rate
        self.channels = channels

        # 16-bit little-endian PCM
        self.bytes_per_sample = 2
        self.frame_samples = 320  # 20ms @ 16k (safe). We can tune later.
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
        print(f"🎤 Starting FFmpeg ALSA capture from {device}")
        print(f"   Command: {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
        self._pts = 0

    async def recv(self):
        if self._pts == 0:
            print(f"🎤 Starting audio capture: {self.frame_samples} samples/frame, mono, {self.sample_rate}Hz")

        # Check if FFmpeg process has died
        if self.proc.poll() is not None:
            stderr_output = self.proc.stderr.read().decode() if self.proc.stderr else "No error output"
            raise RuntimeError(f"FFmpeg process died. stderr: {stderr_output}")

        assert self.proc.stdout is not None
        data = await asyncio.get_event_loop().run_in_executor(None, self.proc.stdout.read, self.frame_bytes)
        if not data or len(data) < self.frame_bytes:
            stderr_output = self.proc.stderr.read().decode() if self.proc.stderr else "No error output"
            raise asyncio.CancelledError(f"Audio capture ended. stderr: {stderr_output}")

        # int16 mono samples, shape (samples,)
        samples = np.frombuffer(data, dtype=np.int16)

        # IMPORTANT: shape must be (samples, channels) for from_ndarray
        if self.channels == 1:
            arr = samples.reshape(-1, 1)
            layout = "mono"
        else:
            arr = samples.reshape(-1, self.channels)
            layout = "stereo"

        frame = av.AudioFrame.from_ndarray(arr, format="s16", layout=layout)
        frame.sample_rate = self.sample_rate

        frame.pts = self._pts
        frame.time_base = Fraction(1, self.sample_rate)
        self._pts += arr.shape[0]  # number of samples

        # Debug: log every 50 frames (~1 second)
        if self._pts % (self.sample_rate) < self.frame_samples:
            avg_amplitude = np.abs(samples).mean()
            print(f"🎤 Audio frame sent: pts={self._pts}, avg_amplitude={avg_amplitude:.1f}")

        return frame

    def stop(self):
        super().stop()
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()