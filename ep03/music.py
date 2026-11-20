"""Trilha instrumental sintetizada (tensa e animada), 125 BPM, Lá menor.

Gera build/music.wav com a duração da timeline. Marca as viradas de cena
com um "boom", e faz um riser antes da cena 5 (o dado que assusta).
"""
import json, os
import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
SR = 44100
BPM = 125.0
BEAT = 60.0 / BPM
rng = np.random.default_rng(7)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def lp_fast(x, cutoff):
    # filtro via FFT (rápido para sinais longos)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def hp_fast(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (cutoff / np.maximum(f, 1)) ** 4)
    return np.fft.irfft(X, len(x))


def saw(freq, n, detune=0.0):
    t = np.arange(n) / SR
    ph = (freq * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))


def env(n, a=0.002, d=0.15, s=0.0, r=0.0):
    t = np.arange(n) / SR
    e = np.minimum(t / max(a, 1e-4), 1.0)
    e *= s + (1 - s) * np.exp(-np.maximum(t - a, 0) / max(d, 1e-4))
    return e


def add(buf, x, t, g=1.0):
    a = int(t * SR)
    if a >= len(buf):
        return
    b = min(a + len(x), len(buf))
    buf[a:b] += g * x[: b - a]


def kick():
    n = int(0.42 * SR)
    t = np.arange(n) / SR
    f = 45 + 110 * np.exp(-t * 28)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) * np.exp(-t * 7.5)
    x += 0.25 * rng.standard_normal(n) * np.exp(-t * 160)
    return np.tanh(1.6 * x)


def hat(open_=False):
    n = int((0.22 if open_ else 0.06) * SR)
    x = hp_fast(rng.standard_normal(n), 7000)
    return x * env(n, 0.0005, 0.07 if open_ else 0.018) * 0.5


def clap():
    n = int(0.3 * SR)
    x = rng.standard_normal(n)
    x = hp_fast(lp_fast(x, 4000), 900)
    t = np.arange(n) / SR
    e = np.exp(-t * 22)
    for o in (0.0, 0.011, 0.022):
        e += 0.6 * np.exp(-np.maximum(t - o, 0) * 200) * (t >= o)
    return x * e * 0.5


def boom():
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    f = 32 + 60 * np.exp(-t * 6)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.8)
    nz = lp_fast(rng.standard_normal(n), 1200) * np.exp(-t * 5) * 0.4
    return np.tanh(1.4 * (x + nz))


def riser(d):
    n = int(d * SR)
    t = np.arange(n) / SR
    x = rng.standard_normal(n)
    # varredura: mistura de bandas cada vez mais agudas
    lo = lp_fast(x, 900)
    hi = hp_fast(x, 3000)
    p = t / d
    y = lo * (1 - p) + hi * p
    y *= p ** 2 * 0.6
    tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * p ** 2) / SR) * p ** 2 * 0.12
    return y + tone


# progressão (uma por compasso): Am  F  Dm  E
CHORDS = [(57, [57, 60, 64]), (53, [53, 57, 60]), (50, [50, 53, 57]), (52, [52, 56, 59])]


def main():
    tl = json.load(open(os.path.join(B, "timeline.json")))
    T = tl["duration"]
    N = int((T + 2.5) * SR)
    drums = np.zeros(N); bass = np.zeros(N); arp = np.zeros(N); pad = np.zeros(N); fx = np.zeros(N)
    K, H, HO, C = kick(), hat(), hat(True), clap()

    s5 = next(s["start"] for s in tl["scenes"] if s["id"] == 5)
    s8 = next(s["start"] for s in tl["scenes"] if s["id"] == 8)
    end = T
    # quebra: sem bumbo nos 2 tempos antes da cena 5
    brk = (s5 - 2 * BEAT, s5)

    nbeats = int(T / BEAT) + 4
    for b in range(nbeats):
        t = b * BEAT
        if t > end - 0.05:
            break
        bar, beat = divmod(b, 4)
        in_brk = brk[0] - 0.01 <= t < brk[1] - 0.01
        if not in_brk:
            add(drums, K, t, 0.9)
            if beat in (1, 3) and bar >= 1:
                add(drums, C, t, 0.55)
        add(drums, HO if beat == 3 and bar % 2 == 1 else H, t + BEAT / 2, 0.45)
        for q in (0.25, 0.75):
            add(drums, H, t + q * BEAT, 0.16)

        root, notes = CHORDS[bar % 4]
        # baixo: colcheias com oitava
        for e8 in range(2):
            tt = t + e8 * BEAT / 2
            n = int(BEAT / 2 * SR * 0.92)
            nn = root - 12 + (12 if (beat * 2 + e8) % 4 == 3 else 0)
            x = saw(midi(nn), n) + 0.5 * saw(midi(nn), n, 0.006)
            x *= env(n, 0.003, 0.16, 0.35)
            add(bass, x, tt, 0.5 if not in_brk else 0.25)
        # arpejo em semicolcheias
        seq = [0, 1, 2, 1]
        for s16 in range(4):
            tt = t + s16 * BEAT / 4
            idx = seq[s16] + (beat % 2)
            nn = notes[idx % 3] + 12 * (1 + idx // 3)
            n = int(BEAT / 4 * SR * 1.6)
            tq = np.arange(n) / SR
            x = np.sign(np.sin(2 * np.pi * midi(nn) * tq)) * 0.6 + saw(midi(nn), n, 0.004) * 0.4
            add(arp, x * env(n, 0.002, 0.07), tt, 0.22)
    # pad sustentado
    for bar in range(int(T / (4 * BEAT)) + 2):
        t = bar * 4 * BEAT
        root, notes = CHORDS[bar % 4]
        n = int(4 * BEAT * SR * 1.05)
        x = sum(saw(midi(nn), n, d) for nn in notes for d in (-0.004, 0.004))
        tq = np.arange(n) / SR
        e = np.minimum(tq / 0.25, 1) * np.minimum((4 * BEAT * 1.05 - tq) / 0.25, 1)
        add(pad, x * np.clip(e, 0, 1), t, 0.05)

    bass = np.tanh(1.5 * lp_fast(bass, 700))
    arp = lp_fast(arp, 3200)
    pad = lp_fast(pad, 1400)

    # viradas de cena
    BM = boom()
    for s in tl["scenes"]:
        if s["id"] in (1, 5, 8):
            add(fx, BM, s["start"], 0.55 if s["id"] != 1 else 0.45)
    add(fx, riser(2 * BEAT + 0.6), s5 - 2 * BEAT - 0.6, 0.6)

    mix = drums * 0.9 + bass * 0.55 + arp * 0.7 + pad + fx
    # fade de entrada curtinho e saída suave depois do fim
    t = np.arange(N) / SR
    mix *= np.clip(t / 0.05, 0, 1)
    fade0 = end - 1.6
    mix *= np.where(t > fade0, np.clip(1 - (t - fade0) / 1.6, 0, 1), 1.0)
    mix = mix[: int(T * SR)]
    mix = np.tanh(mix / np.abs(mix).max() * 1.3) * 0.9
    sf.write(os.path.join(B, "music.wav"), np.stack([mix, mix], 1).astype(np.float32), SR)
    print("music ok", T)


if __name__ == "__main__":
    main()
