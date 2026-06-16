"""audio.py — pure-numpy soundtrack synth with sectioned arrangement.

No samples. Stereo, 44100 Hz, written via the stdlib wave module.
The arrangement evolves by section and pivots minor->major at the climax.
"""
import math
import wave
import numpy as np

SR = 44100
BAR = 2.0          # seconds per bar (120 BPM)
BEAT = BAR / 4     # 0.5s


# ----------------------------------------------------------------------------
# mixer + envelope
# ----------------------------------------------------------------------------
def make_buffers(dur):
    n = int(dur * SR)
    return np.zeros(n), np.zeros(n)


def add(L, R, sig, start, gain=1.0, pan=0.0):
    s0 = int(start * SR)
    s1 = min(len(L), s0 + len(sig))
    if s1 <= s0:
        return
    seg = sig[:s1 - s0] * gain
    L[s0:s1] += seg * math.cos((pan + 1) * math.pi / 4)
    R[s0:s1] += seg * math.sin((pan + 1) * math.pi / 4)


def env(n, a, r, sl=1.0):
    e = np.ones(n) * sl
    a, r = int(a * SR), int(r * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r and n - r > 0:
        e[-r:] = np.linspace(sl, 0, r)
    return e


def _t(n):
    return np.arange(n) / SR


# ----------------------------------------------------------------------------
# instruments
# ----------------------------------------------------------------------------
def kick(dur=0.4):
    n = int(dur * SR)
    t = _t(n)
    f = 150 * np.exp(-t * 28) + 44
    phase = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t * 7)
    click = (np.random.rand(n) * 2 - 1) * np.exp(-t * 120) * 0.3
    return (body + click) * 0.9


def hat(dur=0.06):
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    # band-limit: smooth then high-pass via difference, so it's a softer "tss" not harsh hiss
    k = 3
    noise = np.convolve(noise, np.ones(k) / k, mode="same")
    noise = np.diff(noise, prepend=0)
    return noise * np.exp(-t * 110) * 0.28


def clap(dur=0.3):
    n = int(dur * SR)
    t = _t(n)
    out = np.zeros(n)
    for d in [0.0, 0.012, 0.024]:
        s = int(d * SR)
        e = np.exp(-(t) * 50)
        raw = np.random.rand(n) * 2 - 1
        raw = np.convolve(raw, np.ones(4)/4, mode="same")
        burst = raw * e
        out[s:] += burst[:n - s]
    return out * 0.26


def tom(freq=110, dur=0.35):
    n = int(dur * SR)
    t = _t(n)
    f = freq * np.exp(-t * 6) + freq * 0.6
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * np.exp(-t * 6) * 0.6


def padnote(freqs, dur):
    n = int(dur * SR)
    t = _t(n)
    sig = np.zeros(n)
    for f in freqs:
        for det in (-0.4, 0.0, 0.4):
            ff = f * (2 ** (det / 1200.0))
            # triangle-ish via sum
            sig += np.sin(2 * np.pi * ff * t) * 0.5
            sig += (2 * np.abs(2 * ((ff * t) % 1) - 1) - 1) * 0.18
    sig /= (len(freqs) * 2.2)
    e = env(n, 0.4, min(0.8, dur * 0.4), 0.8)
    return sig * e * 0.5


def subbass(freq, dur):
    n = int(dur * SR)
    t = _t(n)
    sig = np.sin(2 * np.pi * freq * t)
    sig += np.sin(2 * np.pi * freq * 2 * t) * 0.1
    e = env(n, 0.01, 0.06, 1.0)
    return sig * e * 0.7


def pluck(freq, dur=0.25):
    n = int(dur * SR)
    t = _t(n)
    saw = 2 * ((freq * t) % 1) - 1
    tri = 2 * np.abs(saw) - 1
    sig = (saw * 0.5 + tri * 0.5) * np.exp(-t * 12)
    return sig * 0.4


def bell(freq, dur=1.2):
    n = int(dur * SR)
    t = _t(n)
    sig = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)
    return sig * np.exp(-t * 3.5) * 0.4


def lead(freq, dur=0.5):
    n = int(dur * SR)
    t = _t(n)
    vib = np.sin(2 * np.pi * 5 * t) * 0.006
    sig = np.sin(2 * np.pi * freq * t * (1 + vib))
    e = env(n, 0.03, 0.1, 0.9)
    return sig * e * 0.45


def riser(dur=2.0):
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    noise = np.convolve(noise, np.ones(6)/6, mode="same")
    sweep = np.sin(2 * np.pi * (200 + 800 * (t / dur) ** 2) * t)
    e = (t / dur) ** 2
    return (noise * 0.25 + sweep * 0.6) * e * 0.42


def whoosh(dur=0.6):
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    noise = np.convolve(noise, np.ones(8)/8, mode="same")
    e = np.exp(-((t - dur / 2) ** 2) / (2 * (dur / 5) ** 2))
    return noise * e * 0.3


def boom(dur=1.5):
    n = int(dur * SR)
    t = _t(n)
    f = 90 * np.exp(-t * 2) + 30
    phase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(phase) * np.exp(-t * 1.8) * 0.9


# ----------------------------------------------------------------------------
# musical material
# ----------------------------------------------------------------------------
def note(name):
    """note name -> freq, e.g. A2, C4, Bb3, F#4."""
    names = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5,
             "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}
    n = name[:-1].upper()
    octave = int(name[-1])
    midi = 12 * (octave + 1) + names[n]
    return 440.0 * 2 ** ((midi - 69) / 12)


# progression = list of 4 chords: (pad_freqs, bass_root, lead_freqs)
def chord(root_notes, bass, lead_notes):
    return ([note(x) for x in root_notes], note(bass), [note(x) for x in lead_notes])


# ----------------------------------------------------------------------------
# MOOD PALETTES — Fred again.. style: lush, emotional, harmonically rich.
# Each mood = {build, drop} progressions (build = pre-climax, drop = climax/major
# resolve). Chords use 7ths/9ths/sus for that warm, bittersweet pop-electronic feel.
# ----------------------------------------------------------------------------
PALETTES = {
    # bittersweet, garage-y, emotional (the signature Fred again.. feel)
    "emotional": {
        "tempo": 138,
        "build": [
            chord(["A3", "C4", "E4", "G4"], "A1", ["A4", "C5", "E5"]),   # Am7
            chord(["F3", "A3", "C4", "E4"], "F1", ["F4", "A4", "C5"]),   # Fmaj7
            chord(["C4", "E4", "G4", "B4"], "C2", ["C5", "E5", "G5"]),   # Cmaj7
            chord(["G3", "B3", "D4", "F4"], "G1", ["G4", "B4", "D5"]),   # G7
        ],
        "drop": [
            chord(["C4", "E4", "G4", "D5"], "C2", ["E5", "G5", "C6"]),   # Cadd9
            chord(["A3", "C4", "E4", "G4"], "A1", ["C5", "E5", "A5"]),   # Am7
            chord(["F3", "A3", "C4", "G4"], "F1", ["A4", "C5", "F5"]),   # Fadd9
            chord(["G3", "B3", "D4", "A4"], "G1", ["B4", "D5", "G5"]),   # Gadd9
        ],
    },
    # bright, hopeful, anthemic — for growth / success / launch
    "uplifting": {
        "tempo": 128,
        "build": [
            chord(["D4", "F#4", "A4"], "D2", ["D5", "F#5"]),
            chord(["A3", "C#4", "E4"], "A1", ["A4", "C#5"]),
            chord(["B3", "D4", "F#4"], "B1", ["B4", "D5"]),
            chord(["G3", "B3", "D4"], "G1", ["G4", "B4"]),
        ],
        "drop": [
            chord(["D4", "F#4", "A4", "E5"], "D2", ["F#5", "A5", "D6"]),
            chord(["G3", "B3", "D4", "A4"], "G1", ["B4", "D5", "G5"]),
            chord(["A3", "C#4", "E4", "B4"], "A1", ["C#5", "E5", "A5"]),
            chord(["B3", "D4", "F#4", "C#5"], "B1", ["D5", "F#5", "B5"]),
        ],
    },
    # vast, ambient, floating — for space / science / scale
    "cosmic": {
        "tempo": 115,
        "build": [
            chord(["D3", "A3", "D4", "E4"], "D1", ["F#4", "A4"]),        # Dsus
            chord(["B2", "F#3", "B3", "C#4"], "B0", ["D4", "F#4"]),
            chord(["G2", "D3", "G3", "A3"], "G0", ["B3", "D4"]),
            chord(["A2", "E3", "A3", "B3"], "A0", ["C#4", "E4"]),
        ],
        "drop": [
            chord(["D3", "A3", "D4", "F#4"], "D1", ["A4", "D5", "F#5"]),
            chord(["A2", "E3", "A3", "C#4"], "A0", ["E4", "A4", "C#5"]),
            chord(["B2", "F#3", "B3", "D4"], "B0", ["F#4", "B4", "D5"]),
            chord(["G2", "D3", "G3", "B3"], "G0", ["D4", "G4", "B4"]),
        ],
    },
    # dark, propulsive, urgent — for problems / danger / intensity
    "driving": {
        "tempo": 140,
        "build": [
            chord(["E3", "G3", "B3"], "E1", ["E4", "G4"]),
            chord(["C3", "E3", "G3"], "C1", ["C4", "E4"]),
            chord(["D3", "F3", "A3"], "D1", ["D4", "F4"]),
            chord(["B2", "D3", "F#3"], "B0", ["B3", "D4"]),
        ],
        "drop": [
            chord(["E3", "G3", "B3", "D4"], "E1", ["G4", "B4", "E5"]),
            chord(["G3", "B3", "D4", "F4"], "G1", ["B4", "D5", "G5"]),
            chord(["A3", "C4", "E4", "G4"], "A1", ["C5", "E5", "A5"]),
            chord(["B2", "D3", "F#3", "A3"], "B0", ["D4", "F#4", "B4"]),
        ],
    },
    # suspenseful, minor, sparse — for mystery / questions / tension
    "tense": {
        "tempo": 100,
        "build": [
            chord(["D3", "F3", "A3"], "D1", ["D4", "F4"]),
            chord(["A2", "C3", "E3"], "A0", ["A3", "C4"]),
            chord(["Bb2", "D3", "F3"], "A#0", ["Bb3", "D4"]),
            chord(["A2", "C#3", "E3"], "A0", ["A3", "C#4"]),
        ],
        "drop": [
            chord(["D3", "F3", "A3", "C4"], "D1", ["F4", "A4", "D5"]),
            chord(["Bb2", "D3", "F3", "A3"], "A#0", ["D4", "F4", "Bb4"]),
            chord(["C3", "E3", "G3", "B3"], "C1", ["E4", "G4", "C5"]),
            chord(["A2", "C#3", "E3", "G3"], "A0", ["C#4", "E4", "A4"]),
        ],
    },
    # light, bouncy, major — for fun / casual / kids
    "playful": {
        "tempo": 124,
        "build": [
            chord(["C4", "E4", "G4"], "C2", ["C5", "E5"]),
            chord(["A3", "C4", "E4"], "A1", ["A4", "C5"]),
            chord(["F3", "A3", "C4"], "F1", ["F4", "A4"]),
            chord(["G3", "B3", "D4"], "G1", ["G4", "B4"]),
        ],
        "drop": [
            chord(["C4", "E4", "G4", "A4"], "C2", ["E5", "G5", "C6"]),
            chord(["F3", "A3", "C4", "D4"], "F1", ["A4", "C5", "F5"]),
            chord(["G3", "B3", "D4", "E4"], "G1", ["B4", "D5", "G5"]),
            chord(["A3", "C4", "E4", "B4"], "A1", ["C5", "E5", "A5"]),
        ],
    },
}

# keyword -> mood, for auto-detecting a fitting palette from the title
_MOOD_HINTS = {
    "emotional": ["story", "journey", "dream", "love", "lonely", "feel", "heart", "memory", "english", "ielts", "learn", "vocabulary"],
    "uplifting": ["growth", "success", "win", "launch", "free", "future", "rise", "achieve", "band", "score", "best"],
    "cosmic": ["universe", "space", "galaxy", "star", "planet", "cosmos", "infinite", "scale", "big", "science", "atom", "ocean"],
    "driving": ["fast", "power", "speed", "energy", "machine", "tech", "code", "crisis", "race", "now", "urgent"],
    "tense": ["why", "mystery", "danger", "warning", "problem", "threat", "secret", "dark", "risk", "fear"],
    "playful": ["fun", "easy", "simple", "game", "kids", "happy", "quirky", "cat", "joke", "play"],
}

# rotation so back-to-back videos don't repeat even with the same mood
_PALETTE_ROTATION = ["emotional", "cosmic", "uplifting", "driving", "tense", "playful"]


def pick_mood(spec):
    """Choose a palette: explicit spec.audio.mood, else infer from title, else rotate."""
    m = getattr(spec.audio, "mood", None)
    if m and m in PALETTES:
        return m
    title = (spec.title or "").lower()
    scores = {}
    for mood, words in _MOOD_HINTS.items():
        scores[mood] = sum(1 for w in words if w in title)
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    # deterministic rotation by title hash (varied but reproducible)
    idx = abs(hash(spec.title or "x")) % len(_PALETTE_ROTATION)
    return _PALETTE_ROTATION[idx]


# ----------------------------------------------------------------------------
# arrangement
# ----------------------------------------------------------------------------
def render_audio(spec, out_path):
    dur = spec.total_duration() + 0.8
    L, R = make_buffers(dur)

    sections = sorted(spec.audio.sections, key=lambda s: s.start) if spec.audio.sections else []

    # pick a mood palette + tempo (Fred again.. style variety)
    mood = pick_mood(spec)
    palette = PALETTES[mood]
    # tempo: explicit bpm overrides palette default
    bpm = getattr(spec.audio, "tempo_bpm", None) or palette["tempo"]
    bar = 240.0 / bpm          # seconds per 4-beat bar
    beat = bar / 4
    BUILD = palette["build"]
    DROP = palette["drop"]

    def section_at(t):
        cur = "drive"
        for s in sections:
            if t >= s.start:
                cur = s.name
            else:
                break
        return cur

    def is_major(t):
        maj = False
        for s in sections:
            if t >= s.start and s.pivot_to_major:
                maj = True
        return maj

    n_bars = int(dur / bar) + 1
    for b in range(n_bars):
        bar_t = b * bar
        if bar_t >= dur:
            break
        sec = section_at(bar_t)
        prog = DROP if is_major(bar_t) else BUILD
        pads, bass, leads = prog[b % 4]
        BAR = bar          # local aliases so the rest of the body is unchanged
        BEAT = beat

        # pads every bar (except sparse intro keeps them quiet)
        pad_gain = {"intro": 0.5, "build": 0.7, "drive": 0.85, "climax": 0.95,
                    "warm": 0.75, "uplift": 0.85, "finale": 1.0}.get(sec, 0.8)
        add(L, R, padnote(pads, BAR), bar_t, gain=pad_gain * 0.5, pan=0.0)
        # sub bass per bar
        add(L, R, subbass(bass, BAR * 0.96), bar_t, gain=0.7)

        # per-beat percussion / arp gated by section
        for beat in range(4):
            bt = bar_t + beat * BEAT
            if bt >= dur:
                break
            if sec == "intro":
                if beat == 0:
                    add(L, R, kick(), bt, gain=0.5)
                add(L, R, hat(), bt + BEAT / 2, gain=0.3, pan=0.2)
            elif sec == "build":
                if beat in (0, 2):
                    add(L, R, kick(), bt, gain=0.8)
                add(L, R, hat(), bt, gain=0.3, pan=-0.2)
                if beat in (1, 3):
                    add(L, R, pluck(leads[0]), bt, gain=0.5, pan=0.3)
            elif sec == "drive":
                add(L, R, kick(), bt, gain=0.9)  # 4-on-floor
                if beat == 2:
                    add(L, R, clap(), bt, gain=0.7)
                add(L, R, hat(), bt + BEAT / 2, gain=0.35, pan=0.25)
                # 8th arps
                add(L, R, pluck(leads[beat % len(leads)]), bt, gain=0.4, pan=-0.3)
                add(L, R, pluck(leads[(beat + 1) % len(leads)]), bt + BEAT / 2, gain=0.35, pan=0.3)
            elif sec == "climax":
                add(L, R, kick(), bt, gain=1.0)
                if beat % 2 == 0:
                    add(L, R, clap(), bt, gain=0.6)
                # fast 16th arps
                for s16 in range(4):
                    st = bt + s16 * BEAT / 4
                    add(L, R, pluck(leads[s16 % len(leads)] * 2, 0.12), st, gain=0.3, pan=(s16 - 1.5) * 0.2)
                add(L, R, lead(leads[beat % len(leads)] * 2), bt, gain=0.4)
            elif sec == "warm":
                if beat == 0:
                    add(L, R, kick(), bt, gain=0.5)
                add(L, R, bell(leads[beat % len(leads)]), bt, gain=0.4, pan=(beat - 1.5) * 0.2)
            elif sec == "uplift":
                if beat in (0, 2):
                    add(L, R, kick(), bt, gain=0.8)
                add(L, R, hat(), bt + BEAT / 2, gain=0.3)
                add(L, R, lead(leads[beat % len(leads)]), bt, gain=0.5, pan=0.1)
            elif sec == "finale":
                add(L, R, kick(), bt, gain=1.0)
                add(L, R, clap(), bt, gain=0.5)
                add(L, R, hat(), bt + BEAT / 2, gain=0.35)
                add(L, R, lead(leads[beat % len(leads)] * 2), bt, gain=0.55, pan=0.0)
                add(L, R, pluck(leads[(beat + 1) % len(leads)]), bt + BEAT / 2, gain=0.4, pan=0.3)

    # place riser + boom right before a pivot section
    for s in sections:
        if s.pivot_to_major and s.start > 2:
            add(L, R, riser(2.0), s.start - 2.0, gain=0.7)
            add(L, R, boom(1.5), s.start, gain=0.9)

    # transition whooshes at each section boundary
    for s in sections:
        if s.start > 0.5:
            add(L, R, whoosh(0.6), s.start - 0.3, gain=0.4)

    # sustained resolve at the very end
    last_prog = DROP if (sections and any(x.pivot_to_major for x in sections)) else BUILD
    add(L, R, padnote(last_prog[0][0], 2.0), max(0, dur - 2.2), gain=0.6)
    # a soft bell flourish on the final chord (signature shimmer)
    for i, lf in enumerate(last_prog[0][2][:3]):
        add(L, R, bell(lf * 2, 1.6), max(0, dur - 2.0) + i * 0.12, gain=0.3, pan=(i - 1) * 0.3)

    # ---- master ----
    stack = np.stack([L, R]).astype(np.float64)

    # gentle one-pole low-pass to roll off harsh highs (kills the "hiss")
    def lowpass(x, cutoff_hz=11000.0):
        a = float(np.exp(-2 * np.pi * cutoff_hz / SR))
        try:
            from scipy.signal import lfilter
            return lfilter([1 - a], [1, -a], x)
        except Exception:
            # fast vectorized IIR via cumulative trick is not exact; use a
            # cheap FIR moving-average approximation when scipy is absent
            k = max(1, int(SR / cutoff_hz))
            return np.convolve(x, np.ones(k) / k, mode="same")

    # normalize input level BEFORE saturation so tanh doesn't over-distort
    pk = np.max(np.abs(stack)) or 1.0
    stack = stack / pk * 0.8
    for ch in range(2):
        stack[ch] = lowpass(stack[ch], 12000.0)
    # soft knee limiter (gentler than hard tanh)
    drive = 0.9
    mix = np.tanh(stack * drive) / np.tanh(drive)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.89          # headroom, avoid inter-sample clipping
    # short fade-in to avoid a click at the very start
    fin = int(0.05 * SR)
    if mix.shape[1] > fin:
        mix[:, :fin] *= np.linspace(0, 1, fin)
    # end fade
    fade_n = int(0.6 * SR)
    if mix.shape[1] > fade_n:
        fade = np.linspace(1, 0, fade_n)
        mix[:, -fade_n:] *= fade

    # write 16-bit PCM
    data = (np.clip(mix.T, -1, 1) * 32767).astype(np.int16)
    with wave.open(out_path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return out_path
