"""Gera a narração (Kokoro, voz pm_alex) frase a frase e monta a linha do tempo.

Saída: build/voice.wav e build/timeline.json (início/fim de cada cena e frase).
"""
import json, os, sys
import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro
from script import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
SR = 24000
VOICE = os.environ.get("VOICE", "pm_alex")
SPEED = float(os.environ.get("SPEED", "1.15"))
GAP = 0.14          # pausa entre frases
LEAD = 0.30         # respiro no início de cada cena
TAIL = 0.40         # respiro no fim de cada cena
END_HOLD = 2.2      # segura o cartão final depois da última fala


def trim(x, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x
    a = max(idx[0] - int(0.02 * SR), 0)
    b = min(idx[-1] + int(0.06 * SR), len(x))
    return x[a:b]


def main():
    k = Kokoro(os.path.join(B, "models/kokoro-v1.0.onnx"), os.path.join(B, "models/voices-v1.0.bin"))
    timeline, clips = [], []
    t = 0.0
    for sc in SCENES:
        start = t
        cur = start + (0.12 if sc["id"] == 1 else LEAD)
        lines = []
        for i, (disp, spoken) in enumerate(sc["lines"]):
            cache = os.path.join(B, f"line_{sc['id']}_{i}.wav")
            s, sr = k.create(spoken, voice=VOICE, speed=SPEED, lang="pt-br")
            s = trim(np.asarray(s, dtype=np.float32))
            sf.write(cache, s, SR)
            d = len(s) / SR
            lines.append({"text": disp, "start": round(cur, 3), "end": round(cur + d, 3)})
            clips.append((cur, s))
            cur += d + GAP
        speech_end = lines[-1]["end"]
        dur = max(sc["target"] * 0.8, speech_end - start + TAIL)
        if sc["id"] == len(SCENES):
            dur = max(dur, speech_end - start + END_HOLD)
        timeline.append({"id": sc["id"], "start": round(start, 3), "end": round(start + dur, 3), "lines": lines})
        print(f"cena {sc['id']}: {start:6.2f} -> {start+dur:6.2f}  (fala {speech_end-start:5.2f}s, alvo {sc['target']}s)")
        t = start + dur
    total = t
    out = np.zeros(int(total * SR) + SR, dtype=np.float32)
    for st, s in clips:
        a = int(st * SR)
        out[a:a + len(s)] += s
    out = out[: int(total * SR)]
    out = out / max(1e-6, np.abs(out).max()) * 0.89
    sf.write(os.path.join(B, "voice.wav"), out, SR)
    json.dump({"duration": round(total, 3), "scenes": timeline}, open(os.path.join(B, "timeline.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"total: {total:.2f}s")


if __name__ == "__main__":
    main()
