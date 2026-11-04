"""Run: python3 scripts/test_ssml.py"""
from pathlib import Path
from ssml import parse

NS = 'xmlns="http://www.w3.org/2001/10/synthesis"'

# inline markup must not split a sentence into separate takes
items = parse(f'<speak {NS}><voice name="s1">I mean <emphasis>this</emphasis> one, the <sub alias="Application Programming Interface">API</sub>.</voice></speak>')
assert items == [("speech", "s1", "I mean this one, the Application Programming Interface.", {}, {})], items

# say-as characters, tags kept/dropped, break strength and time, paragraph pause
items = parse(f'<speak {NS}><p><voice name="S2">[Sigh] call <say-as interpret-as="characters">AWS</say-as> [breath] now</voice></p>'
              f'<break strength="strong"/><break time="250ms"/></speak>')
assert items == [("speech", "s2", "[sigh] call A W S now", {}, {}), ("break", 0.5), ("break", 0.6), ("break", 0.25)], items

# prosody nests (rate multiplies, pitch/volume add) and splits the text it changes
items = parse(f'<speak {NS}><voice name="s1">Normal <prosody rate="slow" pitch="+2st" volume="+6dB">slower '
              f'<prosody rate="+50%" pitch="+1st">faster</prosody></prosody> normal.</voice></speak>')
assert [i[2] for i in items] == ["Normal", "slower", "faster", "normal."], items
assert items[1][4] == {"rate": 0.8, "pitch": 2.0, "volume": 6.0}, items[1]
assert abs(items[2][4]["rate"] - 1.2) < 1e-9 and items[2][4]["pitch"] == 3.0, items[2]

# engine sampling on <speak>/<voice>, voice by library name or .wav path, <audio> clips
items = parse(f'<speak {NS} seed="7" temperature="0.6"><voice name="hifi-92" top_p="0.9">One.</voice>'
              f'<audio src="sfx/ding.wav">ding</audio><voice name="my/host.wav">Two.</voice></speak>', Path("/eps"))
assert items[0] == ("speech", "hifi-92", "One.", {"seed": 7, "temperature": 0.6, "top_p": 0.9}, {}), items[0]
assert items[1] == ("audio", "/eps/sfx/ding.wav"), items[1]
assert items[2][1] == "/eps/my/host.wav" and items[2][3] == {"seed": 7, "temperature": 0.6}, items[2]

# plain "S1:" lines still work
items = parse("S1: Hi there [chuckle]\nPAUSE: 500ms\nS2: Hello")
assert items == [("speech", "s1", "Hi there [chuckle]", {}, {}), ("break", 0.5), ("speech", "s2", "Hello", {}, {})], items

print("ssml ok")
