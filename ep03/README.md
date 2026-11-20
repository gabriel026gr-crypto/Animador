# Simula Aí! · "Quem cai?" EP. 3 — Inter e Grêmio no Z4

Vídeo vertical 1080x1920, 30 fps, ~80 s, narração pt-BR + legenda queimada + trilha.

## Entregas (`out/`)
- `quem_cai_ep03_instagram_tiktok.mp4` — cartão final "Siga @simulaaibr"
- `quem_cai_ep03_youtube.mp4` — cartão final "Inscreva-se no Simula Aí!"
- `capa_ep03.png` — capa vertical

## Como gerar de novo
```
pip install kokoro-onnx soundfile skia-python numpy   # + ffmpeg, fontes Inter e Noto Color Emoji
# modelos do Kokoro em build/models/ (kokoro-v1.0.onnx, voices-v1.0.bin — releases do kokoro-onnx no GitHub)
./build.sh
```
- `script.py` — roteiro: texto da legenda e texto falado (normalizado p/ o TTS) por cena
- `tts.py` — narração (Kokoro, voz `pm_alex`) e linha do tempo `build/timeline.json`
- `music.py` — trilha instrumental sintetizada (125 BPM, Lá menor)
- `mix.sh` — ducking da trilha sob a voz, normalização −14 LUFS
- `render.py` — animação (Skia) → ffmpeg; `python3 render.py stills` gera PNGs de conferência
