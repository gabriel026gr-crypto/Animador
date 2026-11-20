# Simula Aí! · "Quem cai?" EP. 3 — Inter e Grêmio no Z4

Vídeo vertical 1080x1920, 30 fps, ~80 s, narração pt-BR + legenda queimada + trilha.

## Entregas (`out/`)
- `quem_cai_ep03_instagram_tiktok.mp4` — cartão final "Siga @simulaaibr"
- `quem_cai_ep03_youtube.mp4` — cartão final "Inscreva-se no Simula Aí!"
- `capa_ep03.png` — capa vertical

## Como gerar de novo
```
pip install edge-tts soundfile skia-python numpy   # + ffmpeg, fontes Inter e Noto Color Emoji
# a rede precisa alcançar speech.platform.bing.com (voz neural pt-BR-AntonioNeural)
./build.sh
```
- `script.py` — roteiro: texto da legenda e texto falado (normalizado p/ o TTS) por cena
- `tts.py` — narração (Microsoft pt-BR-AntonioNeural, uma fala por cena; pausas longas encurtadas) e linha do tempo `build/timeline.json`.
  Ajustes: `RATE=+18%` (velocidade), `PITCH=+0Hz`; `ENGINE=kokoro` usa a voz local antiga.
- `music.py` — trilha instrumental sintetizada (125 BPM, Lá menor)
- `mix.sh` — ducking da trilha sob a voz, normalização −14 LUFS
- `render.py` — animação (Skia) → ffmpeg; `python3 render.py stills` gera PNGs de conferência
