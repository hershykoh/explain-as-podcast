---
name: stream-podcast
description: Play a two-host audio podcast explaining a topic, code, error, PR, or the last answer on the user's speakers as it renders, starting within seconds, with pause / resume / stop, and embed the finished MP3 when done. Use when the user wants to listen right away ("play it as a podcast", "stream it", "read it to me", "start listening now"), or asks to pause, resume, or stop a podcast that is playing. For a file only, use explain-as-podcast.
argument-hint: "[topic or text to explain]"
---

# Stream a Podcast

Same episode as explain-as-podcast, but it starts playing on this machine's speakers about 3 seconds after the model loads (about 15 s on Apple Silicon), and still produces the MP3 at the end.

Only use this when the user can hear this machine. In a remote or headless session, use explain-as-podcast instead.

## 1. Start the renderer first
Pick a short slug, then start the renderer right away in the background, before you write anything. It loads and warms up the model (about 20 s) while you write the script, then waits for the file:

```bash
"$(realpath "<this skill's base directory>")/../../scripts/podcast.sh" --play \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml \
  ~/.local/share/explain-as-podcast/episodes/<short-slug>.mp3
```

Never run it in the foreground: playback takes as long as the episode. If it exits with "unknown voice" or a parse error, fix the script and start it again. If no script appears within 10 minutes, it exits on its own.

## 2. Write the script to that path
Read `../explain-as-podcast/SKILL.md` next to this skill's real directory (`realpath "<this skill's base directory>"/../explain-as-podcast/SKILL.md`) and follow its sections 1 and 2: the topic, the two hosts, the tags and the SSML. Don't change those rules here. Write the whole script in one go to `~/.local/share/explain-as-podcast/episodes/<short-slug>.ssml`.

Playback starts a second or two after the file is written. Tell the user it's starting and that they can say "pause", "resume" or "stop". Don't wait for it to finish before replying.

Lines render one sentence at a time in script order, about 3x faster than they play, so playback never waits. The first run installs Chatterbox Turbo (a few GB) and takes several minutes; say so. Run one render at a time.

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
