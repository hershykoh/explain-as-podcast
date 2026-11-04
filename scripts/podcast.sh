#!/usr/bin/env bash
# Usage: podcast.sh <script.ssml|script.txt> <out.mp3>
# First run installs Chatterbox Turbo into $EXPLAIN_PODCAST_HOME and makes the two host voice samples.
set -euo pipefail
HOME_DIR="${EXPLAIN_PODCAST_HOME:-$HOME/.local/share/explain-as-podcast}"
VENV="$HOME_DIR/venv"
HERE="$(cd "$(dirname "$0")" && pwd)"

command -v ffmpeg >/dev/null || { echo "ffmpeg is required (macOS: brew install ffmpeg)" >&2; exit 1; }

if [ ! -x "$VENV/bin/python" ]; then
  echo "First run: installing Chatterbox Turbo into $VENV (a few GB, one time)..." >&2
  mkdir -p "$HOME_DIR"
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q --upgrade pip
  # setuptools<81 still ships pkg_resources, which Chatterbox's watermarker imports
  "$VENV/bin/pip" install -q chatterbox-tts edge-tts "setuptools<81"
fi

if [ ! -f "$HOME_DIR/voices/s2.wav" ]; then
  echo "Making host voice samples..." >&2
  mkdir -p "$HOME_DIR/voices"
  "$VENV/bin/edge-tts" -v en-US-AndrewNeural --write-media "$HOME_DIR/voices/s1.mp3" \
    --text "Hey, thanks for tuning in. I've been looking forward to this one all week, because honestly, it's a topic I think about way more than I should."
  "$VENV/bin/edge-tts" -v en-US-BrianNeural --write-media "$HOME_DIR/voices/s2.mp3" \
    --text "Yeah, same here. So let's just jump right in, because there's a lot to cover today, and I promise it's going to be more fun than it sounds."
  for v in s1 s2; do ffmpeg -loglevel error -y -i "$HOME_DIR/voices/$v.mp3" -ar 24000 "$HOME_DIR/voices/$v.wav"; done
fi

EXPLAIN_PODCAST_HOME="$HOME_DIR" exec "$VENV/bin/python" "$HERE/render.py" "$@"
