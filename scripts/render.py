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

try:  # Apple Silicon: the MLX port of the same model (chatterbox-mlx) renders ~1.5x faster end to end
    from chatterbox.tts_turbo_mlx import ChatterboxTurboMLX
except ImportError:
    ChatterboxTurboMLX = None

def fresh(cache, wav):
    return cache.exists() and cache.stat().st_mtime >= wav.stat().st_mtime

if ChatterboxTurboMLX:
    # Internals below are from chatterbox-mlx 1.3.1 (pinned in podcast.sh).
    from chatterbox.tts_turbo_mlx import MAX_GEN_LEN, chunk_speech_cap, crossfade_chunks, plan_chunks, postprocess_speech_tokens

    quant = int(os.environ.get("EXPLAIN_PODCAST_QUANT_BITS") or 0) or None  # 8 = ~15% faster; listen first
    print(f"Loading Chatterbox Turbo on MLX{f' ({quant}-bit)' if quant else ''}...")
    model = ChatterboxTurboMLX.from_pretrained(quantize_bits=quant)

    def load_voice(wav, cache):
        if fresh(cache, wav):
            model.set_conditionals_from_dict(torch.load(cache))
        else:  # embed the clip once and save it in upstream's conds.pt layout; rebuilt if the .wav changes
            saved = {}
            def capture(speaker_emb, prompt_tokens, ref_dict, _orig=model._set_conditionals):
                saved.update(t3={"speaker_emb": torch.from_numpy(np.asarray(speaker_emb)),
                                 "cond_prompt_speech_tokens": None if prompt_tokens is None else torch.from_numpy(np.asarray(prompt_tokens))},
                             gen=ref_dict)
                _orig(speaker_emb, prompt_tokens, ref_dict)
            model._set_conditionals = capture
            try:
                model.prepare_conditionals(str(wav), norm_loudness=False)
            finally:
                del model._set_conditionals
            torch.save(saved, cache)
        return model._t3_cond_emb, model._ref_dict

    def set_voice(conds):
        model._t3_cond_emb, model._ref_dict = conds

    def speak_all(texts):
        """All of one host's lines at once: their sentence chunks decode together, up to 8 per T3 batch,
        instead of one generate() per line. Each line is then rebuilt and watermarked as generate() would."""
        pieces = [(n, piece) for n, text in enumerate(texts) for piece in plan_chunks(text)]
        groups = model._groups(len(pieces), 8)
        chunks = [[] for _ in texts]
        for group in groups:
            tokens = model.t3.generate_batch(
                model._t3_cond_emb, [model._encode_text(pieces[i][1]) for i in group],
                seeds=[None] * len(group), max_gen_lens=[chunk_speech_cap(pieces[i][1], MAX_GEN_LEN) for i in group],
                n_slots=len(groups[0]), stats={}, temperature=0.8, top_k=1000, top_p=0.95,
                repetition_penalty=1.2, max_gen_len=MAX_GEN_LEN)
            for i, toks in zip(group, tokens):
                chunks[pieces[i][0]].append(model._vocode(postprocess_speech_tokens(toks), 2, None))
        out = []
        for parts in chunks:
            min_len = int(model.sr * 0.12) + 1  # generate() drops chunks too short to crossfade
            parts = [w for w in parts if len(w) >= min_len] or parts[:1]
            wav = crossfade_chunks(parts, model.sr, 0.05) if len(parts) > 1 else parts[0]
            wav = np.asarray(wav.numpy() if hasattr(wav, "numpy") else wav, dtype=np.float32).reshape(-1)
            out.append(np.asarray(model._watermark(wav), dtype=np.float32).reshape(-1) if len(wav) else wav)
        return out
else:
    from chatterbox.tts_turbo import ChatterboxTurboTTS, Conditionals
    from transformers.initialization import no_init_weights

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Loading Chatterbox Turbo on {device}...")
    with no_init_weights():  # skip random init of weights the checkpoint overwrites anyway: ~2x faster load, identical output
        model = ChatterboxTurboTTS.from_pretrained(device=device)

    def load_voice(wav, cache):
        if fresh(cache, wav):
            return Conditionals.load(cache).to(device)
        model.prepare_conditionals(str(wav), norm_loudness=False)  # loudnorm returns float64, which MPS rejects
        model.conds.save(cache)  # embed each voice clip once; rebuilt if the .wav changes
        return model.conds

    def set_voice(conds):
        model.conds = conds

    def speak_all(texts):
        return [model.generate(t).squeeze().cpu().numpy() for t in texts]

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
        voices[v] = load_voice(DATA / "voices" / f"{v}.wav", DATA / "voices" / f"{v}.conds.pt")
    set_voice(voices[v])

# The 19 paralinguistic tags in Chatterbox Turbo's tokenizer; any other [tag] would be read aloud.
TAGS = {"laugh", "chuckle", "sigh", "gasp", "groan", "clear throat", "cough", "sniff", "shush", "crying",
        "happy", "surprised", "sarcastic", "angry", "fear", "whispering", "dramatic", "narration", "advertisement"}

def clean_tags(text):
    def fix(m):
        tag = m.group(1).strip().lower()
        if tag in TAGS:
            return f"[{tag}]"
        print(f"note: dropped unknown tag [{m.group(1)}]", file=sys.stderr)
        return ""
    return re.sub(r"\s+", " ", re.sub(r"\[([^\]]*)\]", fix, text)).strip()

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

items = [(i[0], i[1], clean_tags(i[2])) if i[0] == "speech" else i for i in parse_items(src)]
items = [i for i in items if i[0] == "break" or i[2]]  # a line that was only an unknown tag
start = time.time()
speech = [i for i, item in enumerate(items) if item[0] == "speech"]
audio = {}
for v in dict.fromkeys(resolve_voice(items[i][1]) for i in speech):  # each host once, in order of appearance
    mine = [i for i in speech if resolve_voice(items[i][1]) == v]
    use_voice(v)
    for i, wav in zip(mine, speak_all([items[i][2] for i in mine])):
        audio[i] = wav
    print(f"{v}: {len(mine)} lines [{time.time() - start:.0f}s]", flush=True)

out, last_speaker = [], None
for i, item in enumerate(items):
    if item[0] == "break":
        out.append(np.zeros(int(model.sr * item[1]), dtype=np.float32))
        continue
    # a short natural pause between speaker turns, unless the script already has a break there
    if last_speaker not in (None, item[1]) and items[i - 1][0] != "break":
        out.append(np.zeros(int(model.sr * 0.25), dtype=np.float32))
    out.append(audio[i])
    last_speaker = item[1]

tmp = Path(tempfile.mkdtemp()) / "podcast.wav"
sf.write(tmp, np.concatenate(out) if out else np.zeros(1, np.float32), model.sr)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-b:a", "128k", dst], check=True)
print(f"wrote {dst} ({len(speech)} lines in {time.time() - start:.1f}s)")
