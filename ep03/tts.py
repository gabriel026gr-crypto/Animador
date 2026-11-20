"""Gera a narração e monta a linha do tempo.

Motor padrão: voz neural Microsoft pt-BR-AntonioNeural (via edge-tts), uma fala
contínua por cena; os tempos de cada frase vêm das marcas de palavra do serviço.
Alternativa local (sotaque estrangeiro): ENGINE=kokoro.

Saída: build/voice.wav e build/timeline.json (início/fim de cada cena e frase).
"""
import asyncio, json, os, re, subprocess, unicodedata
import numpy as np
import soundfile as sf
from script import SCENES

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "build")
SR = 24000
ENGINE = os.environ.get("ENGINE", "edge")
VOICE = os.environ.get("VOICE", "pt-BR-AntonioNeural" if ENGINE == "edge" else "pm_alex")
RATE = os.environ.get("RATE", "+18%")      # edge: velocidade
PITCH = os.environ.get("PITCH", "+0Hz")    # edge: tom
SPEED = float(os.environ.get("SPEED", "1.15"))  # kokoro
GAP = 0.14          # pausa entre frases (kokoro)
LEAD = 0.30         # respiro no início de cada cena
TAIL = 0.40         # respiro no fim de cada cena
END_HOLD = 2.2      # segura o cartão final depois da última fala
MAX_PAUSE = 0.32    # pausa máxima dentro de uma cena (edge)


def trim(x, thr=0.008):
    idx = np.where(np.abs(x) > thr)[0]
    if len(idx) == 0:
        return x, 0.0
    a = max(idx[0] - int(0.02 * SR), 0)
    b = min(idx[-1] + int(0.08 * SR), len(x))
    return x[a:b], a / SR


def norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in w if unicodedata.category(c) != "Mn"))


def squeeze_pauses(x, max_pause=MAX_PAUSE, thr=0.01, win=0.02):
    """Encurta silêncios internos maiores que max_pause. Retorna (áudio, mapa_de_tempo)."""
    hop = int(win * SR)
    n = len(x) // hop
    loud = np.array([np.abs(x[i * hop:(i + 1) * hop]).max() > thr for i in range(n)])
    cuts, i = [], 0  # (início, fim) em segundos dos trechos removidos
    while i < n:
        if not loud[i]:
            j = i
            while j < n and not loud[j]:
                j += 1
            if (j - i) * win > max_pause and i > 0 and j < n:
                keep = max_pause / 2
                cuts.append((i * win + keep, j * win - keep))
            i = j
        else:
            i += 1
    if not cuts:
        return x, lambda t: t
    parts, last = [], 0
    for a, b in cuts:
        parts.append(x[last:int(a * SR)])
        last = int(b * SR)
    parts.append(x[last:])
    def tmap(t):
        sh = 0.0
        for a, b in cuts:
            if t >= b:
                sh += b - a
            elif t > a:
                return a - sh
        return t - sh
    return np.concatenate(parts), tmap


# ------------------------------------------------------------------ edge
async def _edge(text, mp3):
    import edge_tts
    com = edge_tts.Communicate(text, VOICE, rate=RATE, pitch=PITCH, boundary="WordBoundary",
                               proxy=os.environ.get("HTTPS_PROXY"))
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                words.append((ch["offset"] / 1e7, (ch["offset"] + ch["duration"]) / 1e7, ch["text"]))
    return words


def synth_scene_edge(sc):
    """Uma fala por cena. Retorna (áudio, [(ini, fim) de cada frase])."""
    spoken = [s for _, s in sc["lines"]]
    mp3 = os.path.join(B, f"scene_{sc['id']}.mp3")
    words = asyncio.run(_edge(" ".join(spoken), mp3))
    wav = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", mp3, "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    x, off = trim(np.frombuffer(wav, dtype=np.float32).copy())
    words = [(a - off, b - off, w) for a, b, w in words]
    x, tmap = squeeze_pauses(x)
    # cada frase ocupa as próximas N marcas de palavra (N = palavras da frase)
    spans, wi = [], 0
    counts = [len([t for t in line.split() if norm(t)]) for line in spoken]
    if sum(counts) != len(words):
        print(f"  aviso cena {sc['id']}: {sum(counts)} palavras no texto x {len(words)} marcas")
    for n in counts:
        a = words[min(wi, len(words) - 1)][0]
        b = words[min(wi + n - 1, len(words) - 1)][1]
        spans.append((tmap(a), tmap(b)))
        wi += n
    return x, spans


# ------------------------------------------------------------------ kokoro
_K = None


def synth_line_kokoro(text):
    global _K
    if _K is None:
        from kokoro_onnx import Kokoro
        _K = Kokoro(os.path.join(B, "models/kokoro-v1.0.onnx"), os.path.join(B, "models/voices-v1.0.bin"))
    s, _ = _K.create(text, voice=VOICE, speed=SPEED, lang="pt-br")
    return trim(np.asarray(s, dtype=np.float32))[0]


def synth_scene_kokoro(sc):
    parts, spans, cur = [], [], 0.0
    for _, spoken in sc["lines"]:
        s = synth_line_kokoro(spoken)
        spans.append((cur, cur + len(s) / SR))
        parts += [s, np.zeros(int(GAP * SR), np.float32)]
        cur += len(s) / SR + GAP
    return np.concatenate(parts[:-1]), spans


# ------------------------------------------------------------------ main
def main():
    os.makedirs(B, exist_ok=True)
    timeline, clips = [], []
    t = 0.0
    for sc in SCENES:
        start = t
        cur = start + (0.12 if sc["id"] == 1 else LEAD)
        x, spans = synth_scene_edge(sc) if ENGINE == "edge" else synth_scene_kokoro(sc)
        clips.append((cur, x))
        lines = [{"text": disp, "start": round(cur + a, 3), "end": round(cur + b, 3)}
                 for (disp, _), (a, b) in zip(sc["lines"], spans)]
        speech_end = cur + len(x) / SR
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
