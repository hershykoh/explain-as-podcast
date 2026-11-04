"""Parse a podcast script (SSML or "S1: ..." lines) into speech, break and audio items.

Stdlib only, so it can be tested without the model. render.py does the audio.

Each speech item carries everything that affects how it is rendered:
  voice     host name (s1, s2), a voice-library name, or a path to a .wav
  sampling  Chatterbox Turbo sampling: temperature, top_p, top_k, repetition_penalty, seed
  prosody   applied after generation: rate (speed factor), pitch (semitones), volume (dB)
"""
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# The 19 paralinguistic tags in Chatterbox Turbo's tokenizer; any other [tag] would be read aloud.
TAGS = {"laugh", "chuckle", "sigh", "gasp", "groan", "clear throat", "cough", "sniff", "shush", "crying",
        "happy", "surprised", "sarcastic", "angry", "fear", "whispering", "dramatic", "narration", "advertisement"}

SAMPLING = {"temperature": float, "top_p": float, "top_k": int, "repetition_penalty": float, "seed": int}
BREAK_STRENGTH = {"none": 0.0, "x-weak": 0.1, "weak": 0.2, "medium": 0.4, "strong": 0.6, "x-strong": 1.0}
RATE_WORDS = {"x-slow": 0.6, "slow": 0.8, "medium": 1.0, "default": 1.0, "fast": 1.25, "x-fast": 1.5}
PITCH_WORDS = {"x-low": -4.0, "low": -2.0, "medium": 0.0, "default": 0.0, "high": 2.0, "x-high": 4.0}
VOLUME_WORDS = {"silent": -60.0, "x-soft": -9.0, "soft": -4.5, "medium": 0.0, "default": 0.0, "loud": 4.5, "x-loud": 9.0}
PARAGRAPH_PAUSE = 0.5


def clean_tags(text):
    def fix(m):
        tag = m.group(1).strip().lower()
        if tag in TAGS:
            return f"[{tag}]"
        print(f"note: dropped unknown tag [{m.group(1)}]", file=sys.stderr)
        return ""
    return re.sub(r"\s+", " ", re.sub(r"\[([^\]]*)\]", fix, text)).strip()


def seconds(value, default=0.3):
    """'500ms' / '1.5s' / '2' (seconds) -> float seconds."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s)?\s*", value or "")
    if not m:
        return default
    return float(m.group(1)) / (1000 if m.group(2) == "ms" else 1)


def rate(value, current):
    """'slow', '80%', '+20%', '1.2' -> speed factor (1.0 = unchanged), relative to the enclosing rate."""
    v = value.strip().lower()
    if v in RATE_WORDS:
        return RATE_WORDS[v]
    m = re.fullmatch(r"([+-])?(\d+(?:\.\d+)?)%", v)
    if m:
        pct = float(m.group(2)) / 100
        return current * (1 + pct if m.group(1) == "+" else 1 - pct if m.group(1) == "-" else pct)
    return float(v)


def pitch(value, current):
    """'high', '+2st', '-3st', '+10%' -> semitones, added to the enclosing pitch."""
    v = value.strip().lower()
    if v in PITCH_WORDS:
        return PITCH_WORDS[v]
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)st", v)
    if m:
        return current + float(m.group(1))
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", v)
    if m:
        return current + 12 * math.log2(1 + float(m.group(1)) / 100)
    raise ValueError(f"unsupported pitch {value!r}; use x-low..x-high, +Nst or +N%")


def volume(value, current):
    """'loud', '+6dB', '-3dB', '+50%' -> gain in dB, added to the enclosing volume."""
    v = value.strip().lower()
    if v in VOLUME_WORDS:
        return VOLUME_WORDS[v]
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)db", v)
    if m:
        return current + float(m.group(1))
    m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)%", v)
    if m:
        return current + 20 * math.log10(max(1e-3, 1 + float(m.group(1)) / 100))
    raise ValueError(f"unsupported volume {value!r}; use silent..x-loud, +NdB or +N%")


def spell(text):
    return " ".join(ch for ch in text if not ch.isspace())


def parse(content, base_dir=Path(".")):
    """-> list of ("speech", voice, text, sampling, prosody) / ("break", seconds) / ("audio", path)."""
    content = content.strip()
    raw = _parse_ssml(content, base_dir) if content.startswith("<") else _parse_lines(content)
    items = []
    for item in raw:  # merge text runs that render identically, so inline markup never splits a sentence
        prev = items[-1] if items else None
        if item[0] == "speech" and prev and prev[0] == "speech" and (prev[1], prev[3], prev[4]) == (item[1], item[3], item[4]):
            items[-1] = ("speech", item[1], items[-1][2] + " " + item[2], item[3], item[4])
        else:
            items.append(item)
    out = []
    for item in items:
        if item[0] == "speech":
            text = re.sub(r"\s+([.,!?;:)])", r"\1", clean_tags(item[2]))  # "Interface ." from a merged run
            if text:
                out.append(("speech", item[1], text, item[3], item[4]))
        else:
            out.append(item)
    return out


def _parse_lines(content):
    items = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        head = line.split(":", 1)[0].strip().upper()
        if head in ("PAUSE", "BREAK"):
            items.append(("break", seconds(line.split(":", 1)[1])))
        elif ":" in line:
            spk, text = line.split(":", 1)
            items.append(("speech", spk.strip().lower(), text.strip(), {}, {}))
    return items


def _parse_ssml(content, base_dir):
    items = []

    def say(text, ctx):
        if text and text.strip():
            items.append(("speech", ctx["voice"], " ".join(text.split()), dict(ctx["sampling"]), dict(ctx["prosody"])))

    def walk(el, ctx):
        tag = el.tag.split("}")[-1]
        ctx = {"voice": ctx["voice"], "sampling": dict(ctx["sampling"]), "prosody": dict(ctx["prosody"])}
        for key, cast in SAMPLING.items():  # engine sampling can be set on <speak>, <voice> or <prosody>
            if el.get(key) is not None:
                ctx["sampling"][key] = cast(el.get(key))

        if tag == "voice":
            ctx["voice"] = (el.get("name") or ctx["voice"]).strip().lower() if not el.get("name", "").endswith(".wav") \
                else str((base_dir / el.get("name")).expanduser())
        elif tag == "prosody":
            p = ctx["prosody"]
            if el.get("rate"):
                p["rate"] = rate(el.get("rate"), p.get("rate", 1.0))
            if el.get("pitch"):
                p["pitch"] = pitch(el.get("pitch"), p.get("pitch", 0.0))
            if el.get("volume"):
                p["volume"] = volume(el.get("volume"), p.get("volume", 0.0))
        elif tag == "break":
            items.append(("break", seconds(el.get("time")) if el.get("time") else BREAK_STRENGTH.get(el.get("strength", "medium"), 0.4)))
        elif tag == "audio":
            items.append(("audio", str((base_dir / el.get("src", "")).expanduser())))
            return  # fallback text inside <audio> is not read
        elif tag == "sub":
            say(el.get("alias", el.text), ctx)
            return
        elif tag == "say-as" and el.get("interpret-as", "").lower() in ("characters", "spell-out", "letters"):
            say(spell("".join(el.itertext())), ctx)
            return

        say(el.text, ctx)
        for child in el:
            walk(child, ctx)
            say(child.tail, ctx)
        if tag == "p":
            items.append(("break", PARAGRAPH_PAUSE))

    walk(ET.fromstring(content), {"voice": "s1", "sampling": {}, "prosody": {}})
    return items
