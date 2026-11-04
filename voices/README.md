# Voice library

Eleven narrator voices for the hosts. Each file is a 12–15 second clip of natural audiobook narration, with the narrator's breathing between phrases, which Chatterbox carries into the cloned voice.

The defaults are `libritts-8455.wav` (host 1) and `hifi-9017.wav` (host 2).

| File | Narrator |
|---|---|
| `libritts-8455.wav` | LibriVox reader 8455 (LibriTTS-R), **default host 1** |
| `hifi-92.wav` | LibriVox reader 92 |
| `hifi-6097.wav` | LibriVox reader 6097 |
| `hifi-9017.wav` | LibriVox reader 9017, **default host 2** |
| `hifi-6670.wav` | LibriVox reader 6670 |
| `hifi-6671.wav` | LibriVox reader 6671 |
| `hifi-8051.wav` | LibriVox reader 8051 |
| `hifi-9136.wav` | LibriVox reader 9136 |
| `hifi-11614.wav` | LibriVox reader 11614 |
| `hifi-11697.wav` | LibriVox reader 11697 |
| `hifi-12787.wav` | LibriVox reader 12787 |

## Use one

Copy a file over a host's sample. The cached voice rebuilds on the next render.

```bash
cp voices/hifi-92.wav   ~/.local/share/explain-as-podcast/voices/s1.wav
cp voices/hifi-9017.wav ~/.local/share/explain-as-podcast/voices/s2.wav
```

## Source and license

The `hifi-*` clips are excerpts from the **Hi-Fi Multi-Speaker English TTS Dataset (Hi-Fi TTS)** by Evelina Bakhturina, Vitaly Lavrukhin, Boris Ginsburg and Yang Zhang (NVIDIA), 2021 ([OpenSLR 109](https://www.openslr.org/109/), [Hugging Face mirror](https://huggingface.co/datasets/MikhailT/hifi-tts)). They are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

`libritts-8455.wav` is an excerpt from **LibriTTS-R: A Restored Multi-Speaker Text-to-Speech Corpus** by Yuma Koizumi, Heiga Zen, Shigeki Karita, Yifan Ding, Kohei Yatabe, Nobuyuki Morioka, Michiel Bacchiani, Yu Zhang, Wei Han and Ankur Bapna, 2023 ([OpenSLR 141](https://www.openslr.org/141/), [Hugging Face mirror](https://huggingface.co/datasets/mythicinfinity/libritts_r)), licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). It was built from test-clean utterances, joined and resampled the same way.

Both datasets are built from LibriVox audiobooks, which their volunteer readers released into the public domain.

Changes made here: a few test-set utterances per speaker were selected, joined with short silences, resampled to 24 kHz mono, and (for 11614 and 12787) trimmed to 15 seconds.

The voices belong to real volunteer readers. Don't use them to impersonate those people or to make them appear to say things they didn't.
