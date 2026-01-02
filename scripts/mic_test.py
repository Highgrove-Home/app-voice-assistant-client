import sounddevice as sd
import numpy as np

DURATION = 3
SR = 16000

print("Recording…")
audio = sd.rec(int(DURATION * SR), samplerate=SR, channels=1, dtype="int16")
sd.wait()
print("Done. RMS:", float(np.sqrt(np.mean(audio.astype(np.float32) ** 2))))