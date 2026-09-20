#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
REPO=iamrichmack111/textdoc-studio
SSH=git@github.com:${REPO}.git
command -v gh >/dev/null; gh auth status >/dev/null
[ -d .git ] || git init
git branch -M main
if git remote get-url origin >/dev/null 2>&1; then git remote set-url origin "$SSH"; else git remote add origin "$SSH"; fi
if ! gh repo view "$REPO" >/dev/null 2>&1; then gh repo create "$REPO" --public --description "Local-first documentary production studio powered by Flask, Piper and FFmpeg."; fi
git remote set-url origin "$SSH"
gh repo edit "$REPO" --description "Local-first documentary production studio powered by Flask, Piper and FFmpeg — semantic scenes instead of a traditional timeline."
for t in documentary ffmpeg flask piper text-to-speech local-first filmmaking video-generation python playwright docker youtube; do gh repo edit "$REPO" --add-topic "$t"; done
git add -A
if git diff --cached --name-only | grep -E '(^studio-data/|^voices/|youtube-token|client_secret|credentials.*json|^recovery/)'; then echo 'ERROR: private/runtime files staged'; exit 1; fi
if ! git diff --cached --quiet; then git commit -m "feat: publish TextDoc Studio"; fi
git push -u origin main
echo "SSH remote: $(git remote get-url origin)"
gh run list --repo "$REPO" --limit 5 || true
