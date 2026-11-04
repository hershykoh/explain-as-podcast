---
name: explain-as-podcast
description: Explain a topic, code, error, PR, or the last answer as a natural two-host audio podcast (with laughs and pauses), rendered locally with Chatterbox Turbo, and embed the playable MP3. Use when the user asks to "explain this as a podcast", "give it to me as a podcast", or wants an audio explanation.
argument-hint: "[topic or text to explain]"
---

# Explain as Podcast

## 1. Pick the topic
- If the user gave arguments ($ARGUMENTS), explain that.
- Otherwise explain the last complex answer, code change, or topic in this conversation.

## 2. Write the script (SSML)
10–14 turns between two hosts:
- `s1`: curious host who asks what the listener is thinking.
- `s2`: expert who explains with everyday analogies and plain English.

Rules:
- No code blocks, URLs, or long identifiers read aloud; describe them instead.
- Use `<break time="300ms"/>` to `<break time="600ms"/>` for timing.
- Use the inline tags below where a real person would make that sound: about one every turn or two, varied, never stacked. They make the hosts sound human, but too many sound like a gag reel.

**Sounds**: put them where the sound happens, mid-sentence is fine:
| Tag | Use for |
|---|---|
| `[laugh]` / `[chuckle]` | a real joke / a light, amused moment |
| `[sigh]` | relief, frustration, "here we go", or a breath before a long explanation |
| `[gasp]` | surprise or a sudden realization |
| `[groan]` | a painful bug, a bad pun |
| `[clear throat]` | before a correction or "okay, seriously now" |
| `[cough]` / `[sniff]` | small human noises, rarely |
| `[shush]` | "hold on, listen to this" |
| `[crying]` | mock despair, as a joke only |

**Delivery**: put them at the start of the line they color:
| Tag | Use for |
|---|---|
| `[happy]` / `[surprised]` / `[sarcastic]` | the mood of the line |
| `[angry]` / `[fear]` | playful frustration or dread ("the deploy is Friday") |
| `[whispering]` | a secret, a gotcha, a lowered-voice aside |
| `[dramatic]` | a big reveal |
| `[narration]` | calm explanatory voice-over |
| `[advertisement]` | a mock sponsor read, as a joke |

These 19 are the only tags the model knows. Anything else, like `[breath]` or `[pause]`, is removed before rendering, so use `<break>` for pauses.

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="s1">[sigh] Okay. I've been staring at this bug for three hours.</voice>
  <voice name="s2">[gasp] Three hours? [clear throat] Alright, walk me through it.</voice>
  <break time="400ms"/>
  <voice name="s1">[whispering] I think it's the environment variables.</voice>
  <voice name="s2">[chuckle] It's always the environment variables.</voice>
</speak>
```

**Everything else the script can do.** Use these only when they help; most episodes need just `<voice>`, `<break>` and tags.

| Markup | Effect |
|---|---|
| `<voice name="s1">` / `"s2"` | the two hosts |
| `<voice name="hifi-92">` | a guest from the bundled voice library (`hifi-*`, `libritts-*`; an unknown name lists them) |
| `<voice name="guest.wav">` | clone any 10–15 s clean speech clip (path relative to the script) |
| `<break time="500ms"/>`, `<break strength="weak\|medium\|strong\|x-strong"/>` | silence |
| `<p>…</p>` | paragraph: adds a 0.5 s pause after it |
| `<prosody rate="slow\|fast\|80%\|+20%" pitch="+2st\|-10%\|high" volume="+6dB\|soft">` | speed, pitch and loudness, applied after generation (nests) |
| `<sub alias="Application Programming Interface">API</sub>` | say the alias instead of the text |
| `<say-as interpret-as="characters">AWS</say-as>` | spell it out letter by letter |
| `<audio src="sting.wav"/>` | insert a sound file (path relative to the script) |
| `seed="42"` on `<speak>`, `<voice>` or `<prosody>` | repeatable takes |
| `temperature`, `top_p`, `top_k`, `repetition_penalty` on the same elements | engine sampling (defaults 0.8, 0.95, 1000, 1.2); lower temperature is steadier, higher is livelier |

Other SSML elements (`<emphasis>`, `<s>`, `<mark>`, `<lang>`) are allowed, but only their text is read; the engine has no control for them. Inline markup never splits a sentence into separate takes.

## 3. Render
Save the script as `~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml`, then run the renderer two folders above this skill's real directory (`realpath` follows a symlinked skill folder back to the plugin):

```bash
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.mp3
```

The first run installs Chatterbox Turbo (a few GB) and can take several minutes; run it in the background and tell the user. Run one render at a time, never several in parallel: each loads the model, and extra renders just wait their turn. Later runs take about 20 seconds for 45 seconds of audio on Apple Silicon with MLX.

## 4. Deliver
- Embed the audio: `![podcast](<absolute path to the .mp3>)`
- Add 3–4 bullets summarizing the key points.
- Link the script file.
