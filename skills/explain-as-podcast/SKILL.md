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
- `s1` (Andrew): curious host who asks what the listener is thinking.
- `s2` (Brian): expert who explains with everyday analogies and plain English.

Rules:
- No code blocks, URLs, or long identifiers read aloud; describe them instead.
- Add `[laugh]`, `[chuckle]`, or `[cough]` inline where they'd happen naturally (a few, not every line).
- Use `<break time="300ms"/>` to `<break time="600ms"/>` for timing.

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="en-US">
  <voice name="s1">Welcome back! So what are we untangling today?</voice>
  <voice name="s2">[chuckle] Something that sounds scary but really isn't.</voice>
  <break time="400ms"/>
</speak>
```

Only `<voice>`, `<break>` and inline `[tags]` are honored; other SSML tags are read as plain text.

## 3. Render
Save the script as `~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml`, then run (from this skill's base directory):

```bash
../../scripts/podcast.sh ~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml ~/.local/share/explain-as-podcast/episodes/<short-slug>.mp3
```

The first run installs Chatterbox Turbo (a few GB) and can take several minutes; run it in the background and tell the user. Later runs take about a minute per minute of audio on Apple Silicon.

## 4. Deliver
- Embed the audio: `![podcast](<absolute path to the .mp3>)`
- Add 3–4 bullets summarizing the key points.
- Link the script file.
