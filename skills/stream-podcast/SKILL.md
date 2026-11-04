---
name: stream-podcast
description: Play a two-host audio podcast explaining a topic, code, error, PR, or the last answer on the user's speakers as it renders, starting within seconds, with pause / resume / stop, and embed the finished MP3 when done. Use when the user wants to listen right away ("play it as a podcast", "stream it", "read it to me", "start listening now"), or asks to pause, resume, or stop a podcast that is playing. For a file only, use explain-as-podcast.
argument-hint: "[topic or text to explain]"
---

# Stream a Podcast

Same episode as explain-as-podcast, but it starts playing on this machine's speakers about 3 seconds after the model loads (about 15 s on Apple Silicon), and still produces the MP3 at the end.

Only use this when the user can hear this machine. In a remote or headless session, use explain-as-podcast instead.

## 1. Write the script
Read `../explain-as-podcast/SKILL.md` next to this skill's real directory (`realpath "<this skill's base directory>"/../explain-as-podcast/SKILL.md`) and follow its sections 1 and 2: the topic, the two hosts, the tags and the SSML. Don't change those rules here. Save the script as `~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml`.

## 2. Start it playing
Run in the background, never in the foreground: playback takes as long as the episode.

```bash
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" --play \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.mp3
```

Tell the user right away that it will start playing in about 15 seconds, and that they can say "pause", "resume" or "stop". Don't wait for it to finish before replying.

Lines render in script order, about 3x faster than they play, so playback never waits for the next line. The first run installs Chatterbox Turbo (a few GB) and takes several minutes; say so. Run one render at a time.

## 3. Pause, resume, stop
When the user asks, run the same script with one word. Each takes effect within about a second:

```bash
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" pause   # hold playback; rendering continues
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" play    # resume
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" stop    # end playback; the MP3 is still written
```

If it prints "nothing is streaming right now", the episode already finished. Point the user to the embedded MP3, which has its own play and pause controls.

## 4. Deliver the file
When the background render reports `wrote <path>`, the MP3 is complete, even if the last lines are still playing. Then:
- Embed the audio: `![podcast](<absolute path to the .mp3>)`
- Add 3–4 bullets summarizing the key points.
- Link the script file.
