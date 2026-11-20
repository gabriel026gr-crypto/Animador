#!/usr/bin/env bash
# Mixa narração + trilha (com ducking sob a voz) e normaliza para -14 LUFS.
set -euo pipefail
cd "$(dirname "$0")/build"
ffmpeg -y -loglevel error -i voice.wav -i music.wav -filter_complex "
 [0:a]aresample=48000,aformat=channel_layouts=stereo,highpass=f=70,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,volume=1.0,asplit=2[v][vsc];
 [1:a]aresample=48000,volume=0.20[m];
 [m][vsc]sidechaincompress=threshold=0.02:ratio=6:attack=20:release=350:makeup=1[md];
 [v][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95,loudnorm=I=-14:TP=-1.5:LRA=11[out]" \
 -map "[out]" -ar 48000 mix.wav
echo "mix ok"
