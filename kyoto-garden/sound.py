"""Synthesise the soundtrack from scratch: breeze, pond lapping, the koi's
splash, the stream and spout, birdsong, the leaf touching the water and a
temple bell. No recordings are used.

    python3 kyoto-garden/sound.py            # writes renders/soundtrack.wav
"""

import math
import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from garden import config  # noqa: E402

RATE = 48000
rng = np.random.default_rng(2026)


def film_start(shot):
    """Where shot `shot` (0-based) starts in the finished 20 second film."""
    frames = sum(config.SHOTS[i]["length"] for i in range(shot)) - shot * config.CROSSFADE
    return frames / config.FPS


DURATION = (sum(s["length"] for s in config.SHOTS) - (len(config.SHOTS) - 1) * config.CROSSFADE) / config.FPS
N = int(DURATION * RATE)
T = np.arange(N) / RATE


def shaped_noise(n, gain):
    """White noise filtered in the frequency domain by gain(freqs)."""
    spec = np.fft.rfft(rng.standard_normal(n))
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    spec *= gain(np.maximum(freqs, 1.0))
    out = np.fft.irfft(spec, n)
    return out / (np.abs(out).max() + 1e-9)


def band(lo, hi, slope=2.0):
    def gain(f):
        return 1.0 / (1 + (lo / f) ** (2 * slope)) / (1 + (f / hi) ** (2 * slope))
    return gain


def window(t0, t1, fade=0.8):
    """1 inside [t0, t1] with smooth fades, for sounds tied to one shot."""
    up = np.clip((T - t0) / fade, 0, 1)
    down = np.clip((t1 - T) / fade, 0, 1)
    return np.sin(np.minimum(up, down) * math.pi / 2) ** 2


def place(buf, start, sound, pan=0.0, gain=1.0):
    i = int(start * RATE)
    if i >= len(buf) or i + len(sound) <= 0:
        return
    j = min(len(buf), i + len(sound))
    left = math.cos((pan + 1) * math.pi / 4)
    right = math.sin((pan + 1) * math.pi / 4)
    buf[i:j, 0] += sound[:j - i] * gain * left
    buf[i:j, 1] += sound[:j - i] * gain * right


def envelope(n, attack, decay):
    t = np.arange(n) / RATE
    return np.minimum(t / max(attack, 1e-4), 1.0) * np.exp(-t / decay)


# ---------------------------------------------------------------- elements

def breeze(buf):
    for ch in range(2):
        bed = shaped_noise(N, lambda f: (1 / np.sqrt(f)) * band(40, 500)(f))
        swell = 0.6 + 0.4 * np.sin(T * 0.4 + ch) + 0.25 * np.sin(T * 1.1 + 2 * ch)
        gust = 1.0 + 1.6 * np.clip((T - (film_start(3) + 3.4)) / 2.2, 0, 1)
        buf[:, ch] += bed * swell * gust * 0.05


def lapping(buf, t0, t1):
    t = t0
    while t < t1:
        n = int(rng.uniform(0.25, 0.6) * RATE)
        s = shaped_noise(n, band(150, 900)) * envelope(n, 0.05, 0.12)
        place(buf, t, s, rng.uniform(-0.6, 0.6), 0.05 * window(t0, t1)[min(int(t * RATE), N - 1)])
        t += rng.uniform(0.5, 1.4)


def splash(buf, t, size=1.0, pan=0.0):
    n = int(0.6 * RATE)
    hiss = shaped_noise(n, band(700, 5000)) * envelope(n, 0.004, 0.09)
    k = np.arange(n) / RATE
    plop = np.sin(2 * math.pi * np.cumsum(np.interp(k, [0, 0.08], [380, 160])) / RATE) * envelope(n, 0.002, 0.05)
    place(buf, t, hiss * 0.5 + plop * 0.6, pan, 0.22 * size)


def stream(buf, t0, t1):
    n = int((t1 - t0 + 1.0) * RATE)
    w = window(t0, t1)[int(t0 * RATE):int(t0 * RATE) + n]
    w = np.pad(w, (0, n - len(w)))
    for ch, pan in ((0, -0.3), (1, 0.3)):
        rush = shaped_noise(n, band(300, 3500, 3.0))
        mod = 0.7 + 0.3 * shaped_noise(n, band(2, 12))
        bubbles = np.zeros(n)
        for _ in range(int((t1 - t0) * 70)):
            m = int(rng.uniform(0.006, 0.025) * RATE)
            f0 = rng.uniform(500, 2200)
            k = np.arange(m) / RATE
            chirp = np.sin(2 * math.pi * f0 * k * (1 + 8 * k)) * envelope(m, 0.001, 0.008)
            i = rng.integers(0, n - m)
            bubbles[i:i + m] += chirp * rng.uniform(0.2, 1.0)
        trickle = shaped_noise(n, band(1800, 5500, 3.0)) * (0.6 + 0.4 * shaped_noise(n, band(8, 40)))
        mix = rush * mod * 0.07 + bubbles * 0.045 + trickle * 0.03
        i = int(t0 * RATE)
        j = min(N, i + n)
        buf[i:j, ch] += (mix * w)[:j - i]


def bird_phrase(buf, t, pan, gain=1.0, kind="chirps"):
    notes = []
    if kind == "warbler":   # a long rising whistle, then a quick flourish
        notes.append((0.0, 0.55, 1450, 1900, 0.9))
        for k in range(4):
            f = rng.uniform(2800, 3800)
            notes.append((0.62 + k * 0.09, 0.06, f, f * 0.7, 0.8))
    else:
        start = 0.0
        for _ in range(rng.integers(3, 7)):
            dur = rng.uniform(0.04, 0.11)
            f = rng.uniform(3200, 6200)
            notes.append((start, dur, f, f * rng.uniform(0.6, 1.3), rng.uniform(0.5, 1.0)))
            start += dur + rng.uniform(0.03, 0.09)
    for start, dur, f0, f1, amp in notes:
        n = int(dur * RATE)
        k = np.arange(n) / RATE
        freq = np.interp(k, [0, dur], [f0, f1]) * (1 + 0.02 * np.sin(2 * math.pi * 38 * k))
        tone = np.sin(2 * math.pi * np.cumsum(freq) / RATE)
        env = np.sin(np.linspace(0, math.pi, n)) ** 1.5
        place(buf, t + start, tone * env * amp, pan, 0.06 * gain)


def bell(buf, t):
    n = int((DURATION - t + 0.1) * RATE)
    k = np.arange(n) / RATE
    tone = np.zeros(n)
    base = 259.0
    for ratio, amp, t60 in ((1.0, 1.0, 9.0), (2.01, 0.6, 6.0), (3.44, 0.45, 4.0), (5.02, 0.25, 2.5),
                            (7.16, 0.15, 1.5)):
        for detune in (-0.25, 0.25):
            f = base * ratio + detune
            tone += amp * 0.5 * np.sin(2 * math.pi * f * k + rng.uniform(0, 6.28)) * np.exp(-k * 6.9 / t60)
    strike = shaped_noise(n, band(800, 6000)) * envelope(n, 0.0005, 0.02)
    sound = (tone / np.abs(tone).max() + strike * 0.3) * np.minimum(k / 0.003, 1)
    place(buf, t, sound, 0.1, 0.32)


def reverb(buf, seconds=1.2, mix=0.12):
    n = int(seconds * RATE)
    out = buf.copy()
    for ch in range(2):
        ir = rng.standard_normal(n) * np.exp(-np.arange(n) / RATE * 6.9 / seconds)
        ir = np.fft.irfft(np.fft.rfft(ir) * band(200, 7000)(np.maximum(np.fft.rfftfreq(n, 1 / RATE), 1)), n)
        ir /= np.sqrt((ir ** 2).sum())
        size = 1 << int(math.ceil(math.log2(N + n)))
        wet = np.fft.irfft(np.fft.rfft(buf[:, ch], size) * np.fft.rfft(ir, size), size)[:N]
        out[:, ch] = buf[:, ch] * (1 - mix) + wet * mix
    return out


def build():
    buf = np.zeros((N, 2))
    s1, s2, s3, s4 = (film_start(i) for i in range(4))
    breeze(buf)
    lapping(buf, s1, s2 + 0.8)
    lapping(buf, s4, DURATION)
    splash(buf, s1 + 2.05, 1.0, 0.1)
    splash(buf, s1 + 2.45, 0.35, 0.05)
    splash(buf, s1 + 2.9, 0.2, 0.0)
    stream(buf, s2, s3 + 0.8)
    for t, pan, g, kind in ((s1 + 0.4, -0.5, 1.0, "chirps"), (s1 + 3.6, 0.6, 0.7, "chirps"),
                            (s2 + 0.8, 0.2, 1.2, "warbler"), (s2 + 2.4, -0.4, 0.8, "chirps"),
                            (s2 + 4.0, 0.3, 1.0, "chirps"), (s3 + 2.9, -0.7, 0.4, "warbler"),
                            (s4 + 1.6, 0.6, 0.6, "chirps"), (s4 + 3.9, -0.3, 0.5, "chirps")):
        bird_phrase(buf, t, pan, g, kind)
    n = int(0.08 * RATE)
    k = np.arange(n) / RATE
    tick = np.sin(2 * math.pi * np.cumsum(np.interp(k, [0, 0.03], [1900, 1100])) / RATE) * envelope(n, 0.001, 0.02)
    place(buf, s3 + 2.35, tick, -0.1, 0.08)
    bell(buf, s4 + 0.6)
    buf = reverb(buf)
    fade = np.minimum(np.clip(T / 0.6, 0, 1), np.clip((DURATION - T) / 1.2, 0, 1))
    buf *= fade[:, None]
    buf *= 10 ** (-3 / 20) / np.abs(buf).max()
    return buf


def write(path, buf):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data = (np.clip(buf, -1, 1) * 32767).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "renders", "soundtrack.wav")
    write(out, build())
    print(f"wrote {out} ({DURATION:.1f}s)")
