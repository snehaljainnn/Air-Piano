import numpy as np
import wave
from pathlib import Path

# Save the sounds inside your project's sounds folder
OUT = Path("sounds")
OUT.mkdir(exist_ok=True)

RATE = 44100
rng = np.random.default_rng(7)


def save_wav(filename, signal):
    signal = np.clip(signal, -1, 1)
    pcm = (signal * 32767).astype(np.int16)

    with wave.open(str(OUT / filename), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())


# 1. Kick drum — low, punchy thump
t = np.arange(int(RATE * 0.65)) / RATE
kick = np.sin(2 * np.pi * (85 * t - 42 * t**2)) * np.exp(-7 * t)
save_wav("Drum_Kick.wav", kick * 0.9)

# 2. Snare — noisy drum hit
noise = rng.normal(0, 1, len(t))
snare = (
    0.72 * noise + 0.28 * np.sin(2 * np.pi * 180 * t)
) * np.exp(-12 * t)
save_wav("Drum_Snare.wav", snare * 0.65)

# 3. Hi-hat — short, sharp cymbal-like sound
ht = np.arange(int(RATE * 0.22)) / RATE
hat = rng.normal(0, 1, len(ht)) * np.exp(-32 * ht)
save_wav("Drum_Hihat.wav", hat * 0.38)

print("All 3 drum sounds created successfully!")