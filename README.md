# explain-as-podcast

A Claude Code plugin that explains any topic, code change, error, or answer as a two-host audio podcast — with laughs, chuckles, and natural pauses — rendered **locally** with [Chatterbox Turbo](https://huggingface.co/ResembleAI/chatterbox-turbo).

https://github.com/user-attachments/assets/d565382b-b580-4437-9de1-dd42505afc45

*49-second demo with the default hosts, rendered on a MacBook with no cloud and no API key ([mp3](https://github.com/hershykoh/explain-as-podcast/raw/main/assets/demo.mp3) · [script](assets/demo.ssml)).*

- Ask Claude *"explain this as a podcast"* — about a bug, a PR, a concept, or its own last answer
- Two hosts: a curious one who asks your questions, and an expert who answers with analogies
- Real laughs, sighs, gasps and whispers (19 sound and mood tags), natural pauses, and the MP3 plays right in your chat
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
- Apple Silicon tip: `brew install python@3.12` before the first run. Setup then uses [chatterbox-mlx](https://pypi.org/project/chatterbox-mlx/), the same model on Apple's MLX, which renders about 1.5x faster end to end. Set `EXPLAIN_PODCAST_QUANT_BITS=8` for a little more speed (listen first).

The first run creates a virtualenv in `~/.local/share/explain-as-podcast` (override with `EXPLAIN_PODCAST_HOME`), installs Chatterbox Turbo, and copies in the two default host voices from `voices/`. Episodes are saved in `episodes/` there.

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

Inline tags (all 19 that Chatterbox Turbo knows; anything else is dropped):

- Sounds: `[laugh]` `[chuckle]` `[sigh]` `[gasp]` `[groan]` `[clear throat]` `[cough]` `[sniff]` `[shush]` `[crying]`
- Delivery: `[happy]` `[surprised]` `[sarcastic]` `[angry]` `[fear]` `[whispering]` `[dramatic]` `[narration]` `[advertisement]`

## Voices

[`voices/`](voices/) has eleven narrator voices from the CC BY 4.0 Hi-Fi TTS and LibriTTS-R datasets, recorded from public-domain LibriVox audiobooks, with natural breathing. The defaults are `libritts-8455` and `hifi-9017`. Copy any of them over a host's sample to use it.

## Custom voices

Replace `~/.local/share/explain-as-podcast/voices/s1.wav` / `s2.wav` with any clean 5–15 second recording (only use voices you have the right to use). 

## Notes

- Audio from Chatterbox carries Resemble AI's inaudible Perth watermark.
- License: Apache-2.0.
