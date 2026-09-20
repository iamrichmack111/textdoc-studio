#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
.venv/bin/pip install -q playwright
.venv/bin/playwright install chromium
.venv/bin/python scripts/demo.py
VOICE="${TEXTDOC_PIPER_VOICE:-voices/en_GB-alan-medium.onnx}"
PIPER="$(command -v piper || true)"; [ -n "$PIPER" ] || PIPER=.venv/bin/piper
[ -x "$PIPER" ] && [ -f "$VOICE" ] || { echo "Piper/voice missing"; exit 1; }
"$PIPER" --model "$VOICE" --output_file media/demo/narration.wav < media/demo/narration.txt
V=$(ffprobe -v error -show_entries format=duration -of csv=p=0 media/demo/browser-demo.webm); A=$(ffprobe -v error -show_entries format=duration -of csv=p=0 media/demo/narration.wav)
PAD=$(python3 -c "print(max(0,float('$A')-float('$V')+1))")
ffmpeg -y -i media/demo/browser-demo.webm -vf "tpad=stop_mode=clone:stop_duration=$PAD" -an -c:v libx264 -crf 18 media/demo/browser-padded.mp4
ffmpeg -y -i media/demo/browser-padded.mp4 -i media/demo/narration.wav -map 0:v -map 1:a -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k -af loudnorm=I=-16:TP=-1.5:LRA=11 -shortest -movflags +faststart media/demo/textdoc-studio-demo.mp4
