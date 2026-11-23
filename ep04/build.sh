#!/usr/bin/env bash
# Pipeline completo do EP. 3: narração → trilha → mix → vídeos (IG/TikTok e YouTube) → capa.
set -euo pipefail
cd "$(dirname "$0")"
python3 tts.py
python3 music.py
./mix.sh
mkdir -p out
python3 render.py video --cta ig --out out/quem_cai_ep04_instagram_tiktok.mp4
python3 render.py video --cta yt --out out/quem_cai_ep04_youtube.mp4
python3 render.py cover --out out/capa_ep04.png
