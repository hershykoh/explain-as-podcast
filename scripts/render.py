"""Render an SSML file or "S1: ... / S2: ..." script with Chatterbox Turbo.
Supports SSML <speak>, <voice name="...">, <break time="...">, and inline tags like [laugh], [chuckle], [cough].

Each speaker voice is cloned from $DATA/voices/<speaker>.wav (s1.wav, s2.wav; made by setup.sh), then concatenated.
Usage: render.py <script.ssml|script.txt> <out.mp3>
"""
import fcntl, os, re, subprocess, sys, tempfile, time, xml.etree.ElementTree as ET
from pathlib import Path

if len(sys.argv) != 3:
    sys.exit("usage: render.py <script.ssml|script.txt> <out.mp3>")
src, dst = sys.argv[1:3]
DATA = Path(os.environ.get("EXPLAIN_PODCAST_HOME", Path.home() / ".local/share/explain-as-podcast"))

# One render at a time: each loads the model (several GB), and parallel renders can freeze a 16 GB machine.
# Taken before the heavy imports; the OS releases it if this process dies.
DATA.mkdir(parents=True, exist_ok=True)
_lock = open(DATA / "render.lock", "w")
try:
    fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("Another podcast is rendering; waiting for it to finish...", flush=True)
    fcntl.flock(_lock, fcntl.LOCK_EX)

import numpy as np
import soundfile as sf
import torch
from chatterbox.tts_turbo import ChatterboxTurboTTS

device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Loading Chatterbox Turbo on {device}...")
model = ChatterboxTurboTTS.from_pretrained(device=device)

voices = {}
def resolve_voice(name):
    n = name.lower().strip()
    if "andrew" in n or n in ("s1", "speaker1"):
        return "s1"
    if "brian" in n or n in ("s2", "speaker2"):
        return "s2"
    return n

def use_voice(speaker):
    v = resolve_voice(speaker)
    if v not in voices:
        model.prepare_conditionals(str(DATA / "voices" / f"{v}.wav"), norm_loudness=False)  # loudnorm returns float64, which MPS rejects
        voices[v] = model.conds
    model.conds = voices[v]

def parse_items(src_path):
    content = Path(src_path).read_text().strip()
    items = []
    if content.startswith("<") or "<speak" in content:
        NS = "{http://www.w3.org/2001/10/synthesis}"
        root = ET.fromstring(content)
        def walk(el, cur_voice):
            tag = el.tag.replace(NS, "")
            if tag == "voice":
                cur_voice = el.get("name", cur_voice)
            elif tag == "break":
                t = el.get("time", "300ms")
                sec = float(t[:-2]) / 1000.0 if t.endswith("ms") else float(t.rstrip("s"))
                items.append(("break", sec))
            if el.text and el.text.strip():
                items.append(("speech", cur_voice, el.text.strip()))
            for child in el:
                walk(child, cur_voice)
                if child.tail and child.tail.strip():
                    items.append(("speech", cur_voice, child.tail.strip()))
        walk(root, "s1")
    else:
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("<break") or line.upper().startswith("BREAK:") or line.upper().startswith("PAUSE:"):
                m = re.search(r"(\d+(?:\.\d+)?)\s*(ms|s)?", line)
                if m:
                    val = float(m.group(1))
                    unit = m.group(2) or "s"
                    sec = val / 1000.0 if unit == "ms" else val
                    items.append(("break", sec))
            elif ":" in line:
                spk, text = line.split(":", 1)
                items.append(("speech", spk.strip(), text.strip()))
    return items

items = parse_items(src)
tmp = Path(tempfile.mkdtemp())
parts, start = [], time.time()
speech_count = sum(1 for item in items if item[0] == "speech")
idx = 0

last_speaker = None
for item in items:
    if item[0] == "break":
        sec = item[1]
        f = tmp / f"{len(parts):03}_break.wav"
        silence = np.zeros(int(model.sr * sec), dtype=np.float32)
        sf.write(f, silence, model.sr)
        parts.append(f)
    elif item[0] == "speech":
        speaker, text = item[1], item[2]
        # Insert a natural short pause between speaker turns if there was no explicit break
        if last_speaker is not None and last_speaker != speaker and (not parts or not str(parts[-1]).endswith("_break.wav")):
            f_pause = tmp / f"{len(parts):03}_break.wav"
            silence = np.zeros(int(model.sr * 0.25), dtype=np.float32)
            sf.write(f_pause, silence, model.sr)
            parts.append(f_pause)
        
        idx += 1
        use_voice(speaker)
        wav = model.generate(text)
        f = tmp / f"{len(parts):03}.wav"
        sf.write(f, wav.squeeze().cpu().numpy(), model.sr)
        parts.append(f)
        last_speaker = speaker
        print(f"line {idx}/{speech_count} ({speaker}: {text[:30]}...) [{time.time() - start:.0f}s]", flush=True)

lines_to_write = [f"file '{p}'\n" for p in parts]
(tmp / "list.txt").write_text("".join(lines_to_write))
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
                "-b:a", "128k", dst], check=True)
print(f"wrote {dst} ({len(parts)} segments in {time.time() - start:.1f}s)")
