# explain-as-podcast

A Claude Code plugin that explains any topic, code change, error, or answer as a two-host audio podcast — with laughs, chuckles, and natural pauses — rendered **locally** with [Chatterbox Turbo](https://huggingface.co/ResembleAI/chatterbox-turbo).

**▶ [Hear the 35-second demo](https://github.com/hershykoh/explain-as-podcast/raw/main/assets/demo.mp4)** ([mp3](https://github.com/hershykoh/explain-as-podcast/raw/main/assets/demo.mp3), [script](assets/demo.ssml)) — rendered on a MacBook in 24 seconds, no cloud, no API key.

- Ask Claude *"explain this as a podcast"* — about a bug, a PR, a concept, or its own last answer
- Two hosts: a curious one who asks your questions, and an expert who answers with analogies
- Real laughs and chuckles (`[laugh]`, `[chuckle]`), natural pauses, and the MP3 plays right in your chat
- 100% local and free: runs on Apple Silicon, NVIDIA, or CPU

## Install

```text
/plugin marketplace add hershykoh/explain-as-podcast
/plugin install explain-as-podcast@hershykoh
```

Then ask *"explain this as a podcast"* or run `/explain-as-podcast [topic]`.

## Requirements

- Python 3.10+ and `ffmpeg` (`brew install ffmpeg` on macOS)
- ~4 GB free disk for the model
- Apple Silicon (MPS), an NVIDIA GPU, or patience on CPU

The first run creates a virtualenv in `~/.local/share/explain-as-podcast` (override with `EXPLAIN_PODCAST_HOME`), installs Chatterbox Turbo, and makes the two host voice samples. Episodes are saved in `episodes/` there.

## Use the renderer directly

```bash
scripts/podcast.sh my-script.ssml out.mp3
```

Script format — SSML with `<voice name="s1|s2">` and `<break time="...">`, or plain lines:

```text
S1: Wait, so the computer laughs now? [laugh]
S2: [chuckle] It does.
PAUSE: 500ms
```

Inline tags: `[laugh]`, `[chuckle]`, `[cough]`.

## Custom voices

Replace `~/.local/share/explain-as-podcast/voices/s1.wav` / `s2.wav` with any clean 5–15 second recording (only use voices you have the right to use). The defaults are generated on your machine with Microsoft Edge TTS voices.

## Notes

- Audio from Chatterbox carries Resemble AI's inaudible Perth watermark.
- License: Apache-2.0.
