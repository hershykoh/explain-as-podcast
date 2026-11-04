"""Render a podcast script with Chatterbox Turbo. Usage: render.py [--play] <script.ssml|script.txt> <out.mp3>

--play streams the episode to the speakers while it renders (through ffplay, which ships with ffmpeg):
the first line plays as soon as it is ready instead of after the whole episode. The MP3 is still written.

Script format and every supported tag are in ssml.py and the skill's SKILL.md. In short:
  <voice name>   s1/s2, any file in the voice library (voices/), or a path to a .wav to clone
  [laugh] ...    the 19 paralinguistic tags Chatterbox Turbo knows
  temperature / top_p / top_k / repetition_penalty / seed   engine sampling, on <speak>, <voice> or <prosody>
  <prosody rate pitch volume>, <break>, <p>, <sub>, <say-as interpret-as="characters">, <audio src>
"""
import fcntl, os, queue, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path

args = [a for a in sys.argv[1:] if a != "--play"]
PLAY = "--play" in sys.argv[1:]
if len(args) != 2:
    sys.exit("usage: render.py [--play] <script.ssml|script.txt> <out.mp3>")
src, dst = Path(args[0]), args[1]
HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("EXPLAIN_PODCAST_HOME", Path.home() / ".local/share/explain-as-podcast"))
STATE, PID = DATA / "player.state", DATA / "player.pid"  # live-stream controls, see player()

sys.path.insert(0, str(HERE))
from ssml import parse  # parse before loading the model, so a bad script fails fast

items = parse(src.read_text(), src.resolve().parent)

ALIASES = {"andrew": "s1", "speaker1": "s1", "brian": "s2", "speaker2": "s2"}
voices = {}


def voice_file(name):
    """s1/s2 and saved hosts in $DATA/voices, then the bundled voice library, then a .wav path."""
    name = ALIASES.get(name, name)
    for path in (DATA / "voices" / f"{name}.wav", HERE.parent / "voices" / f"{name}.wav", Path(name)):
        if path.suffix == ".wav" and path.exists():
            return path
    library = sorted(p.stem for p in (HERE.parent / "voices").glob("*.wav"))
    sys.exit(f"unknown voice {name!r}: use s1, s2, a .wav path, or one of: {', '.join(library)}")


for _, voice, _, _, _ in (i for i in items if i[0] == "speech"):
    voice_file(voice)  # an unknown voice fails here, before the model loads


# One render at a time: each loads the model (several GB), and parallel renders can freeze a 16 GB machine.
# Taken before the heavy imports; the OS releases it if this process dies.
DATA.mkdir(parents=True, exist_ok=True)
_lock = open(DATA / "render.lock", "w")
try:
    fcntl.flock(_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    print("Another podcast is rendering; waiting for it to finish...", flush=True)
    fcntl.flock(_lock, fcntl.LOCK_EX)

import librosa
import numpy as np
import soundfile as sf
import torch

try:  # Apple Silicon: the MLX port of the same model (chatterbox-mlx) renders ~2x faster end to end
    from chatterbox.tts_turbo_mlx import ChatterboxTurboMLX
except ImportError:
    ChatterboxTurboMLX = None

DEFAULTS = {"temperature": 0.8, "top_p": 0.95, "top_k": 1000, "repetition_penalty": 1.2, "seed": None}


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

    def watermark(wav):
        return np.asarray(model._watermark(wav), dtype=np.float32).reshape(-1) if len(wav) else wav

    def speak_all(texts, sampling):
        """All lines for one voice + sampling at once: their sentence chunks decode together, up to 8 per T3
        batch, instead of one generate() per line. Each line is then crossfaded as generate() would."""
        seed = sampling["seed"]
        pieces = [(n, piece) for n, text in enumerate(texts) for piece in plan_chunks(text)]
        groups = model._groups(len(pieces), 8)
        chunks = [[] for _ in texts]
        for group in groups:
            tokens = model.t3.generate_batch(
                model._t3_cond_emb, [model._encode_text(pieces[i][1]) for i in group],
                seeds=[None if seed is None else seed + i for i in group],
                max_gen_lens=[chunk_speech_cap(pieces[i][1], MAX_GEN_LEN) for i in group],
                n_slots=len(groups[0]), stats={}, max_gen_len=MAX_GEN_LEN, temperature=sampling["temperature"],
                top_k=sampling["top_k"], top_p=sampling["top_p"], repetition_penalty=sampling["repetition_penalty"])
            for i, toks in zip(group, tokens):
                chunks[pieces[i][0]].append(model._vocode(postprocess_speech_tokens(toks), 2, None if seed is None else seed + i))
        out = []
        for parts in chunks:
            min_len = int(model.sr * 0.12) + 1  # generate() drops chunks too short to crossfade
            parts = [w for w in parts if len(w) >= min_len] or parts[:1]
            wav = crossfade_chunks(parts, model.sr, 0.05) if len(parts) > 1 else parts[0]
            out.append(np.asarray(wav.numpy() if hasattr(wav, "numpy") else wav, dtype=np.float32).reshape(-1))
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

    def watermark(wav):
        return np.asarray(model.watermarker.apply_watermark(wav, sample_rate=model.sr), dtype=np.float32)

    def speak_all(texts, sampling):
        out = []
        for n, text in enumerate(texts):
            if sampling["seed"] is not None:
                torch.manual_seed(sampling["seed"] + n)
            out.append(model.generate(text, temperature=sampling["temperature"], top_p=sampling["top_p"],
                                      top_k=sampling["top_k"], repetition_penalty=sampling["repetition_penalty"]).squeeze().cpu().numpy())
        return out

def use_voice(name):
    wav = voice_file(name)
    if wav not in voices:
        voices[wav] = load_voice(wav, DATA / "voices" / f"{wav.stem}.conds.pt")
    set_voice(voices[wav])


def apply_prosody(wav, prosody):
    """The engine has no rate/pitch/volume controls, so <prosody> is applied to the generated audio."""
    if not prosody or not len(wav):
        return wav
    if prosody.get("rate", 1.0) != 1.0:
        wav = librosa.effects.time_stretch(wav, rate=prosody["rate"])
    if prosody.get("pitch", 0.0):
        wav = librosa.effects.pitch_shift(wav, sr=model.sr, n_steps=prosody["pitch"])
    if prosody.get("volume", 0.0):
        wav = wav * 10 ** (prosody["volume"] / 20)
    return np.clip(wav, -1.0, 1.0).astype(np.float32)


def finish(n, wav):
    wav = apply_prosody(wav, items[n][4])
    # watermark the final take: MLX lines arrive unmarked, and prosody changes a PyTorch line after its mark
    return watermark(wav) if ChatterboxTurboMLX or items[n][4] else wav


def episode(line_audio):
    """The episode's pieces in script order: lines, breaks, inserted audio and turn-taking pauses."""
    last_voice = None
    for n, item in enumerate(items):
        if item[0] == "break":
            yield np.zeros(int(model.sr * item[1]), dtype=np.float32)
        elif item[0] == "audio":
            if Path(item[1]).exists():
                yield librosa.load(item[1], sr=model.sr, mono=True)[0].astype(np.float32)
            else:
                print(f"note: skipped missing audio {item[1]}", file=sys.stderr)
        else:
            # a short natural pause between speaker turns, unless the script already has a break there
            if last_voice not in (None, item[1]) and items[n - 1][0] == "speech":
                yield np.zeros(int(model.sr * 0.25), dtype=np.float32)
            yield line_audio(n)
            last_voice = item[1]


def player():
    """Stream to ffplay from a thread, so generation (which stays on this thread) never waits on playback.

    Audio is fed in 0.2 s blocks at most LEAD seconds ahead of real time, so pausing takes effect within
    about a second. `podcast.sh pause|play|stop` writes the wanted state to $DATA/player.state.
    """
    if not shutil.which("ffplay"):
        print("note: --play needs ffplay (it comes with ffmpeg); rendering without playback", file=sys.stderr)
        return None, None
    env = dict(os.environ)
    if sys.platform == "darwin":
        # Homebrew's ffplay runs on sdl2-compat (SDL3), which can open a silent audio driver when started
        # from a background process; forcing CoreAudio makes it play on the Mac's default output.
        env.setdefault("SDL_AUDIO_DRIVER", "coreaudio")  # SDL3
        env.setdefault("SDL_AUDIODRIVER", "coreaudio")   # SDL2
    proc = subprocess.Popen(["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-f", "f32le",
                             "-ar", str(model.sr), "-ch_layout", "mono", "-i", "-"], stdin=subprocess.PIPE, env=env)
    STATE.write_text("playing")
    PID.write_text(str(os.getpid()))
    sr = model.sr  # the main thread drops `model` once generation ends, while this thread is still playing
    q, block, LEAD = queue.Queue(), int(sr * 0.2), 0.5

    def feed():
        # Write one 0.2 s block every 0.2 s, never more than LEAD ahead. ffplay goes silent for good if its
        # input stalls (seen on macOS), so whenever there is no speech to send (before the first line, while
        # paused, or if generation falls behind) it gets silence instead of nothing.
        silence = np.zeros(block, dtype=np.float32)
        sent, t0, cur, pos = 0.0, time.monotonic(), np.zeros(0, np.float32), 0
        try:
            while True:
                state = STATE.read_text().strip() if STATE.exists() else "stopped"
                if state == "stopped":
                    proc.terminate()
                    return
                ahead = sent - (time.monotonic() - t0)
                if ahead > LEAD:
                    time.sleep(ahead - LEAD)
                if state != "paused" and pos >= len(cur):
                    try:
                        cur, pos = q.get_nowait(), 0
                    except queue.Empty:
                        cur, pos = np.zeros(0, np.float32), 0
                    if cur is None:  # end of the episode
                        proc.stdin.close()
                        return
                if state == "paused" or pos >= len(cur):
                    data = silence
                else:
                    data, pos = cur[pos:pos + block], pos + block
                proc.stdin.write(data.tobytes())
                sent += len(data) / sr
        except BrokenPipeError:  # the player was closed; keep rendering the file
            pass

    threading.Thread(target=feed, daemon=True).start()
    print(f"streaming: pause / resume / stop with `podcast.sh pause|play|stop`", flush=True)
    return proc, q


start = time.time()
speech = [n for n, item in enumerate(items) if item[0] == "speech"]
proc, q = player() if PLAY else (None, None)

if q:
    # Streaming: one line at a time in script order. Each line renders ~3x faster than it plays,
    # so after the first line the player stays ahead of the listener.
    def line_audio(n):
        use_voice(items[n][1])
        wav = finish(n, speak_all([items[n][2]], {**DEFAULTS, **items[n][3]})[0])
        print(f"line {speech.index(n) + 1}/{len(speech)} [{time.time() - start:.1f}s]", flush=True)
        return wav
else:
    # File only: batch each voice's lines into one decode (about 2x faster in total, but nothing plays early).
    batches = {}
    for n in speech:
        sampling = {**DEFAULTS, **items[n][3]}
        batches.setdefault((items[n][1], tuple(sorted(sampling.items()))), []).append(n)
    audio = {}
    for (voice, sampling), mine in batches.items():  # each voice + sampling once, in order of appearance
        use_voice(voice)
        for n, wav in zip(mine, speak_all([items[n][2] for n in mine], dict(sampling))):
            audio[n] = finish(n, wav)
        print(f"{voice}: {len(mine)} lines [{time.time() - start:.0f}s]", flush=True)
    line_audio = audio.__getitem__

out = []
for wav in episode(line_audio):
    if q:
        if not out:
            print(f"playing after {time.time() - start:.1f}s", flush=True)
        q.put(wav)
    out.append(wav)

tmp = Path(tempfile.mkdtemp()) / "podcast.wav"
sf.write(tmp, np.concatenate(out) if out else np.zeros(1, np.float32), model.sr)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(tmp), "-b:a", "128k", dst], check=True)
print(f"wrote {dst} ({len(speech)} lines in {time.time() - start:.1f}s)", flush=True)

if proc:
    # Free the model and the render lock now; only the player is left, finishing the last lines.
    del model
    _lock.close()
    q.put(None)
    proc.wait()
    STATE.unlink(missing_ok=True)
    PID.unlink(missing_ok=True)
