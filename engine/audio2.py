"""audio2.py — varied, organic soundtrack synth (Fred again.. flavour).

Pure numpy, no samples. Key upgrades over audio.py:
  - MOOD PALETTES: the spec picks a palette (or it's inferred from the topic),
    each with its own scale, chord movement, tempo feel, and instrument mix.
  - VOCAL CHOPS: formant-filtered synthetic "aah/ooh" stabs, pitched to the
    chord — the signature Fred again.. texture.
  - SIDECHAIN: everything ducks on the kick (the pumping bre-feel).
  - SWING: off-beats are nudged for groove.
  - FILTER SWEEPS + organic noise textures (vinyl crackle, tape hiss, rain).
  - Per-section arrangement that genuinely changes by palette, not one loop.
"""
import math
import wave
import hashlib
import numpy as np

SR = 44100


# ===========================================================================
# scales + chord helpers
# ===========================================================================
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
        "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

def midi(name):
    n, octv = name[:-1], int(name[-1])
    return 12 * (octv + 1) + NOTE[n]

def hz(name):
    return 440.0 * 2 ** ((midi(name) - 69) / 12)

def hz_midi(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# A chord = (root_midi, [interval semitones]) -> we build voicings on the fly
# Progressions are lists of (root_name, quality) per bar.
QUALITIES = {
    "min7":  [0, 3, 7, 10],
    "maj7":  [0, 4, 7, 11],
    "min9":  [0, 3, 7, 10, 14],
    "maj9":  [0, 4, 7, 11, 14],
    "sus2":  [0, 2, 7],
    "sus4":  [0, 5, 7],
    "min":   [0, 3, 7],
    "maj":   [0, 4, 7],
    "add9":  [0, 4, 7, 14],
    "6":     [0, 4, 7, 9],
    "min6":  [0, 3, 7, 9],
}


# ===========================================================================
# MOOD PALETTES — the heart of the variety
# ===========================================================================
# Each palette: tempo, swing, base octave, progressions per energy, drums,
# instrument switches, texture, and a "bright" flag for pivots.
PALETTES = {
    # introspective, emotional, garage-tinged (the classic Fred again.. feel)
    "emotional": {
        "bpm": 122, "swing": 0.14, "root": "F",
        "prog":  [("F", "maj9"), ("A", "min7"), ("D", "min9"), ("B", "maj7")],
        "prog_bright": [("F", "maj9"), ("C", "maj9"), ("D", "min7"), ("B", "maj9")],
        "chops": True, "chop_vowel": "aa", "texture": "vinyl",
        "drums": "garage", "bass": "sub_round", "pad": "warm",
    },
    # bright, uplifting, anthemic
    "uplifting": {
        "bpm": 126, "swing": 0.10, "root": "C",
        "prog":  [("C", "add9"), ("G", "maj9"), ("A", "min7"), ("F", "maj9")],
        "prog_bright": [("C", "maj9"), ("G", "maj9"), ("F", "maj9"), ("G", "6")],
        "chops": True, "chop_vowel": "oo", "texture": "air",
        "drums": "fourfloor", "bass": "sub_round", "pad": "bright",
    },
    # cosmic / awe / documentary (big, slow, wide)
    "cosmic": {
        "bpm": 110, "swing": 0.06, "root": "D",
        "prog":  [("D", "min9"), ("B", "maj7"), ("G", "maj9"), ("A", "sus4")],
        "prog_bright": [("D", "maj9"), ("G", "maj9"), ("A", "maj9"), ("B", "min7")],
        "chops": False, "chop_vowel": "oo", "texture": "space",
        "drums": "halftime", "bass": "deep", "pad": "wide",
    },
    # focused / techy / forward (driving, minimal, hypnotic)
    "driving": {
        "bpm": 128, "swing": 0.08, "root": "A",
        "prog":  [("A", "min7"), ("A", "min7"), ("F", "maj7"), ("G", "6")],
        "prog_bright": [("A", "min9"), ("C", "maj9"), ("F", "maj9"), ("G", "maj9")],
        "chops": True, "chop_vowel": "aa", "texture": "rain",
        "drums": "fourfloor", "bass": "reese", "pad": "warm",
    },
    # tense / serious / cautionary (darker, restrained)
    "tense": {
        "bpm": 118, "swing": 0.05, "root": "E",
        "prog":  [("E", "min"), ("C", "maj7"), ("G", "sus2"), ("D", "min7")],
        "prog_bright": [("E", "min9"), ("G", "maj9"), ("C", "maj9"), ("D", "maj9")],
        "chops": False, "chop_vowel": "aa", "texture": "vinyl",
        "drums": "halftime", "bass": "deep", "pad": "dark",
    },
    # playful / light / educational (bouncy, friendly)
    "playful": {
        "bpm": 124, "swing": 0.16, "root": "G",
        "prog":  [("G", "6"), ("E", "min7"), ("C", "maj9"), ("D", "sus4")],
        "prog_bright": [("G", "maj9"), ("C", "maj9"), ("D", "6"), ("E", "min7")],
        "chops": True, "chop_vowel": "oo", "texture": "air",
        "drums": "garage", "bass": "sub_round", "pad": "bright",
    },
}

# keyword -> palette inference (used when spec doesn't name a mood)
_KW = {
    "emotional": ["story", "journey", "dream", "memory", "feel", "heart", "alone", "love", "night"],
    "uplifting": ["free", "win", "success", "grow", "achieve", "celebrate", "best", "master", "ielts", "band"],
    "cosmic":    ["universe", "space", "star", "galaxy", "planet", "infinite", "cosmos", "earth", "sky", "ocean"],
    "driving":   ["build", "code", "engine", "fast", "data", "tech", "future", "power", "work", "focus"],
    "tense":     ["danger", "warning", "risk", "crisis", "problem", "threat", "why", "mistake", "fear"],
    "playful":   ["fun", "vocab", "word", "learn", "easy", "tip", "trick", "cat", "game", "quiz"],
}


def pick_palette(spec):
    # explicit override on the audio plan
    name = getattr(spec.audio, "mood", None)
    if name and name in PALETTES:
        return name, PALETTES[name]
    # infer from title + scene text
    text = (spec.title or "").lower()
    for sc in spec.scenes:
        for v in (sc.params or {}).values():
            if isinstance(v, str):
                text += " " + v.lower()
    scores = {k: 0 for k in PALETTES}
    for pal, words in _KW.items():
        for w in words:
            if w in text:
                scores[pal] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        # deterministic fallback from title hash, so it's varied but stable
        h = int(hashlib.md5(text.encode()).hexdigest(), 16)
        best = list(PALETTES.keys())[h % len(PALETTES)]
    return best, PALETTES[best]


# ===========================================================================
# low-level synths
# ===========================================================================
def _t(n):
    return np.arange(n) / SR

def env(n, a, r, sl=1.0):
    e = np.ones(n) * sl
    a, r = int(a * SR), int(r * SR)
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r and n - r > 0:
        e[-r:] = np.linspace(sl, 0, r)
    return e

def _lp_fast(sig, cutoff):
    """Vectorized one-pole low-pass (y[n] = b*x[n] + a*y[n-1]) via lfilter."""
    a = math.exp(-2 * math.pi * max(20, cutoff) / SR)
    b = 1 - a
    try:
        from scipy.signal import lfilter
        return lfilter([b], [1, -a], sig)
    except Exception:
        # numpy fallback: recurrence through cumulative trick is inexact;
        # use a short FIR approximation of the IIR instead (fast, good enough)
        taps = max(2, int(1.0 / (b + 1e-6)))
        taps = min(taps, 256)
        kernel = (1 - a) * (a ** np.arange(taps))
        kernel /= kernel.sum()
        return np.convolve(sig, kernel, mode="same")


# drums
def kick(dur=0.42, punch=1.0):
    n = int(dur * SR); t = _t(n)
    f = (150 * punch) * np.exp(-t * 30) + 45
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 6.5)
    click = (np.random.rand(n) * 2 - 1) * np.exp(-t * 130) * 0.45
    return (body + click) * 0.95

def hat(dur=0.05, open_=False):
    n = int(dur * SR); t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    noise = np.diff(noise, prepend=0)
    decay = 40 if open_ else 95
    return noise * np.exp(-t * decay) * (0.32 if open_ else 0.4)

def clap(dur=0.32):
    n = int(dur * SR); t = _t(n)
    out = np.zeros(n)
    for d in [0.0, 0.011, 0.022, 0.03]:
        s = int(d * SR)
        burst = (np.random.rand(n) * 2 - 1) * np.exp(-t * 55)
        out[s:] += burst[:n - s]
    return out * 0.3

def snare(dur=0.25):
    n = int(dur * SR); t = _t(n)
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 22) * 0.4
    noise = (np.random.rand(n) * 2 - 1) * np.exp(-t * 28) * 0.5
    return tone + noise

def rim(dur=0.06):
    n = int(dur * SR); t = _t(n)
    return np.sin(2 * np.pi * 420 * t) * np.exp(-t * 90) * 0.5


# bass voices
def bass_sub(freq, dur):
    n = int(dur * SR); t = _t(n)
    sig = np.sin(2 * np.pi * freq * t) + 0.12 * np.sin(2 * np.pi * 2 * freq * t)
    return sig * env(n, 0.012, 0.05) * 0.75

def bass_deep(freq, dur):
    n = int(dur * SR); t = _t(n)
    sig = np.sin(2 * np.pi * freq * t)
    sig += 0.3 * np.sin(2 * np.pi * freq * t + np.sin(2 * np.pi * 3 * t))  # slow FM warmth
    return sig * env(n, 0.02, 0.08) * 0.7

def bass_reese(freq, dur):
    n = int(dur * SR); t = _t(n)
    s = np.zeros(n)
    for det in (-0.18, 0, 0.18):
        f = freq * 2 ** (det / 12)
        s += (2 * ((f * t) % 1) - 1)
    s /= 3
    s = _lp_fast(s, 700)  # warm low-pass
    return s * env(n, 0.02, 0.06) * 0.5


# pads
def pad(freqs, dur, kind="warm"):
    n = int(dur * SR); t = _t(n)
    sig = np.zeros(n)
    detunes = {"warm": (-0.5, 0, 0.5), "bright": (-0.3, 0, 0.3, 0.6),
               "wide": (-0.7, -0.2, 0.2, 0.7), "dark": (-0.4, 0, 0.4),
               "default": (-0.4, 0, 0.4)}.get(kind, (-0.4, 0, 0.4))
    for f in freqs:
        for det in detunes:
            ff = f * 2 ** (det / 1200.0)
            sig += np.sin(2 * np.pi * ff * t)
            if kind in ("bright", "wide"):
                sig += 0.25 * (2 * np.abs(2 * ((ff * t) % 1) - 1) - 1)
    sig /= (len(freqs) * len(detunes) * 1.1)
    # tone shaping
    cut = {"warm": 2600, "bright": 5200, "wide": 3400, "dark": 1500}.get(kind, 3000)
    # cheap brightness: blend original with a softened copy
    soft = np.convolve(sig, np.ones(16) / 16, mode="same")
    mix = 0.5 if cut < 2500 else 0.25
    sig = sig * (1 - mix) + soft * mix
    return sig * env(n, 0.5, min(0.9, dur * 0.4), 0.8) * 0.5


# melodic
def pluck(freq, dur=0.22):
    n = int(dur * SR); t = _t(n)
    saw = 2 * ((freq * t) % 1) - 1
    sig = saw * np.exp(-t * 13)
    return sig * 0.4

def bell(freq, dur=1.1):
    n = int(dur * SR); t = _t(n)
    sig = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * 2 * freq * t)
    sig += 0.15 * np.sin(2 * np.pi * 3 * freq * t)
    return sig * np.exp(-t * 3.6) * 0.4

def lead(freq, dur=0.5):
    n = int(dur * SR); t = _t(n)
    vib = np.sin(2 * np.pi * 5.5 * t) * 0.007
    sig = np.sin(2 * np.pi * freq * t * (1 + vib))
    sig += 0.2 * np.sin(2 * np.pi * 2 * freq * t)
    return sig * env(n, 0.02, 0.1, 0.9) * 0.42

def arp(freq, dur=0.16):
    n = int(dur * SR); t = _t(n)
    sig = (2 * ((freq * t) % 1) - 1) * 0.5 + np.sin(2 * np.pi * freq * t) * 0.5
    return sig * np.exp(-t * 18) * 0.35


# ===========================================================================
# VOCAL CHOPS — formant-filtered synthetic vowels, the signature texture
# ===========================================================================
# formant frequencies for vowels (F1, F2, F3)
FORMANTS = {
    "aa": [(800, 1.0), (1150, 0.6), (2900, 0.3)],
    "oo": [(350, 1.0), (640, 0.5), (2400, 0.2)],
    "ee": [(300, 1.0), (2300, 0.7), (3000, 0.3)],
    "eh": [(550, 1.0), (1800, 0.6), (2700, 0.3)],
}

def vocal_chop(freq, dur, vowel="aa", glide=0.0):
    """Synthetic pitched vowel via additive harmonics shaped by formants."""
    n = int(dur * SR); t = _t(n)
    # pitch with optional upward glide (Fred again.. vocal swells)
    pitch = freq * (1 + glide * (t / dur))
    # glottal-ish source: sum of harmonics with 1/k rolloff
    src = np.zeros(n)
    k = 1
    while k * freq < 6000 and k <= 24:
        src += np.sin(2 * np.pi * k * pitch * t) / k
        k += 1
    src *= 0.5
    # apply formant resonances (sum of band-passy sines weighting)
    out = np.zeros(n)
    for (ff, amp) in FORMANTS.get(vowel, FORMANTS["aa"]):
        # cheap resonator: modulate source amplitude by a windowed cos near formant
        band = src * np.cos(2 * np.pi * ff * t) * amp
        out += band
    out = out / (np.max(np.abs(out)) + 1e-9)
    # vocal-ish envelope: soft attack, plateau, soft release + slight tremolo
    trem = 1 + 0.06 * np.sin(2 * np.pi * 5 * t)
    e = env(n, 0.04, min(0.25, dur * 0.4), 0.9) * trem
    return out * e * 0.4


# ===========================================================================
# textures
# ===========================================================================
def texture_bed(kind, dur):
    n = int(dur * SR)
    if kind == "vinyl":
        base = (np.random.rand(n) * 2 - 1) * 0.012
        # random crackles
        crack = np.zeros(n)
        for _ in range(int(dur * 8)):
            i = np.random.randint(0, n)
            crack[i] = (np.random.rand() * 2 - 1) * 0.4
        return base + crack * 0.5
    if kind == "air":
        noise = np.random.rand(n) * 2 - 1
        return _hp_air(noise) * 0.02
    if kind == "rain":
        noise = (np.random.rand(n) * 2 - 1)
        return noise * 0.018
    if kind == "space":
        # slow filtered noise swells
        noise = np.random.rand(n) * 2 - 1
        swell = 0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * _t(n))
        return noise * 0.015 * swell
    return np.zeros(n)

def _hp_air(sig):
    return np.diff(sig, prepend=0)


def riser(dur=2.0):
    n = int(dur * SR); t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    sweep = np.sin(2 * np.pi * (200 + 1000 * (t / dur) ** 2) * t)
    return (noise * 0.4 + sweep * 0.6) * (t / dur) ** 2 * 0.5

def downsweep(dur=1.2):
    n = int(dur * SR); t = _t(n)
    f = 1200 * np.exp(-t * 3) + 60
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 1.6) * 0.5

def impact(dur=1.6):
    n = int(dur * SR); t = _t(n)
    f = 95 * np.exp(-t * 2) + 32
    ph = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(ph) * np.exp(-t * 1.7)
    noise = (np.random.rand(n) * 2 - 1) * np.exp(-t * 9) * 0.3
    return (sub + noise) * 0.9

def whoosh(dur=0.6):
    n = int(dur * SR); t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    e = np.exp(-((t - dur / 2) ** 2) / (2 * (dur / 5) ** 2))
    return noise * e * 0.4


# ===========================================================================
# mixer with stereo pan + sidechain bus
# ===========================================================================
class Mix:
    def __init__(self, dur):
        self.n = int(dur * SR)
        self.L = np.zeros(self.n)
        self.R = np.zeros(self.n)
        self.kick_times = []   # for sidechain

    def add(self, sig, start, gain=1.0, pan=0.0, duck=True):
        s0 = int(start * SR)
        s1 = min(self.n, s0 + len(sig))
        if s1 <= s0:
            return
        seg = sig[:s1 - s0] * gain
        self.L[s0:s1] += seg * math.cos((pan + 1) * math.pi / 4)
        self.R[s0:s1] += seg * math.sin((pan + 1) * math.pi / 4)

    def mark_kick(self, t):
        self.kick_times.append(t)

    def apply_sidechain(self, amount=0.55, length=0.18):
        """Duck the whole mix briefly after each kick (pumping)."""
        if not self.kick_times:
            return
        gain = np.ones(self.n)
        L = int(length * SR)
        shape = 1 - (1 - np.linspace(0, 1, L) ** 0.5) * amount  # dip then recover
        for t in self.kick_times:
            i = int(t * SR)
            j = min(self.n, i + L)
            gain[i:j] = np.minimum(gain[i:j], shape[:j - i])
        # smooth the gain a touch
        gain = np.convolve(gain, np.ones(64) / 64, mode="same")
        self.L *= gain
        self.R *= gain


# ===========================================================================
# arrangement
# ===========================================================================
def _voicing(root_name, quality, octave=3):
    root = midi(root_name + str(octave))
    return [hz_midi(root + iv) for iv in QUALITIES.get(quality, QUALITIES["min7"])]

def _bass_note(root_name, octave=1):
    return hz_midi(midi(root_name + str(octave)))


def render_audio(spec, out_path):
    pal_name, P = pick_palette(spec)
    bpm = P["bpm"]
    bar = 4 * 60.0 / bpm
    beat = bar / 4
    swing = P["swing"]

    dur = spec.total_duration() + 1.0
    mix = Mix(dur)

    sections = sorted(spec.audio.sections, key=lambda s: s.start) if spec.audio.sections else []

    def section_at(t):
        cur = "drive"
        for s in sections:
            if t >= s.start:
                cur = s.name
            else:
                break
        return cur

    def is_bright(t):
        b = False
        for s in sections:
            if t >= s.start and getattr(s, "pivot_to_major", False):
                b = True
        return b

    def swung(bt, idx):
        # push odd 8ths late
        return bt + (swing * beat * 0.5 if idx % 2 == 1 else 0)

    n_bars = int(dur / bar) + 1
    chop_vowel = P["chop_vowel"]

    for b in range(n_bars):
        bt = b * bar
        if bt >= dur:
            break
        sec = section_at(bt)
        prog = P["prog_bright"] if is_bright(bt) else P["prog"]
        root_name, quality = prog[b % len(prog)]
        chord = _voicing(root_name, quality, octave=3)
        bass_root = _bass_note(root_name, octave=1)

        energy = {"intro": .35, "build": .6, "drive": .9, "climax": 1.0,
                  "warm": .6, "uplift": .85, "finale": 1.0}.get(sec, .8)

        # ---- pad every bar ----
        mix.add(pad(chord, bar, P["pad"]), bt, gain=0.5 * (0.6 + 0.4 * energy))

        # ---- bass ----
        bfn = {"sub_round": bass_sub, "deep": bass_deep, "reese": bass_reese}.get(P["bass"], bass_sub)
        if sec in ("intro",):
            mix.add(bfn(bass_root, bar * 0.95), bt, gain=0.6)
        else:
            # rhythmic bass on beats
            for bi in range(4):
                if sec == "climax" or P["drums"] == "fourfloor":
                    mix.add(bfn(bass_root, beat * 0.9), bt + bi * beat, gain=0.6)
                elif bi in (0, 2):
                    mix.add(bfn(bass_root, beat * 1.8), bt + bi * beat, gain=0.6)

        # ---- drums by palette ----
        drums = P["drums"]
        for bi in range(4):
            beat_t = bt + bi * beat
            if beat_t >= dur:
                break
            if drums == "fourfloor" and sec not in ("intro",):
                mix.add(kick(), beat_t, gain=0.95); mix.mark_kick(beat_t)
                if bi == 2:
                    mix.add(clap(), beat_t, gain=0.6)
                mix.add(hat(), swung(beat_t + beat / 2, 1), gain=0.32, pan=0.2)
            elif drums == "garage":
                # 2-step garage: kick on 1 (+ syncopated), snare on 2 & 4
                if bi == 0:
                    mix.add(kick(), beat_t, gain=0.9); mix.mark_kick(beat_t)
                if bi == 2:
                    mix.add(kick(), beat_t + beat * 0.5, gain=0.7); mix.mark_kick(beat_t + beat * 0.5)
                if bi in (1, 3):
                    mix.add(snare(), beat_t, gain=0.55)
                mix.add(hat(open_=(bi == 3)), swung(beat_t + beat / 2, 1), gain=0.3, pan=-0.2)
                if sec in ("drive", "climax", "finale"):
                    mix.add(hat(), beat_t + beat * 0.25, gain=0.2, pan=0.25)
            elif drums == "halftime":
                if bi == 0:
                    mix.add(kick(punch=1.1), beat_t, gain=0.95); mix.mark_kick(beat_t)
                if bi == 2:
                    mix.add(snare(0.3), beat_t, gain=0.5)
                if sec in ("drive", "climax", "uplift", "finale"):
                    mix.add(hat(), swung(beat_t + beat / 2, 1), gain=0.25, pan=0.2)

        # ---- vocal chops (signature) ----
        if P["chops"] and sec in ("build", "drive", "climax", "uplift", "finale"):
            # chop the top chord tones rhythmically, swung
            tones = chord[1:] if len(chord) > 2 else chord
            pattern = {"build": [0, 2], "drive": [0, 1.5, 2.5, 3],
                       "climax": [0, 1, 2, 3], "uplift": [0, 2, 3],
                       "finale": [0, 1, 2, 3]}.get(sec, [0, 2])
            for k, pos in enumerate(pattern):
                ct = bt + pos * beat
                if ct >= dur:
                    break
                f = tones[k % len(tones)]
                glide = 0.04 if sec == "climax" else 0.0
                mix.add(vocal_chop(f, beat * 0.8, chop_vowel, glide),
                        swung(ct, k), gain=0.34 * (0.7 + 0.3 * energy),
                        pan=((k % 3) - 1) * 0.3)

        # ---- arps / leads in higher energy ----
        if sec in ("drive", "climax", "finale"):
            for bi in range(8):
                at = bt + bi * (beat / 2)
                if at >= dur:
                    break
                f = chord[bi % len(chord)] * 2
                mix.add(arp(f, beat * 0.45), swung(at, bi), gain=0.28, pan=((bi % 2) * 2 - 1) * 0.35)
        if sec in ("climax", "uplift", "finale"):
            mix.add(lead(chord[-1] * 2, beat * 1.8), bt, gain=0.4)
        if sec in ("warm",):
            for bi in range(4):
                mix.add(bell(chord[bi % len(chord)] * 2, beat * 1.5),
                        bt + bi * beat, gain=0.35, pan=(bi - 1.5) * 0.25)

    # ---- texture bed across whole track ----
    mix.add(texture_bed(P["texture"], dur), 0.0, gain=1.0)

    # ---- transitions: riser+impact before each bright pivot, whoosh at boundaries ----
    for s in sections:
        if getattr(s, "pivot_to_major", False) and s.start > 2:
            mix.add(riser(2.0), s.start - 2.0, gain=0.7)
            mix.add(impact(1.6), s.start, gain=0.9)
            mix.mark_kick(s.start)
        if s.start > 0.4:
            mix.add(whoosh(0.6), s.start - 0.3, gain=0.35)
            mix.add(downsweep(1.0), s.start, gain=0.3)

    # ---- final resolve ----
    if sections:
        last = (PALETTES[pal_name]["prog_bright"]
                if any(getattr(x, "pivot_to_major", False) for x in sections)
                else PALETTES[pal_name]["prog"])[0]
        ch = _voicing(last[0], last[1], 3)
        mix.add(pad(ch, 2.2, P["pad"]), max(0, dur - 2.4), gain=0.6)
        mix.add(vocal_chop(ch[-1], 1.6, chop_vowel, 0.02), max(0, dur - 2.2), gain=0.3)

    # ---- sidechain pump + master ----
    mix.apply_sidechain(amount=0.5, length=0.16)
    stack = np.stack([mix.L, mix.R])
    out = np.tanh(stack * 1.05)
    peak = np.max(np.abs(out)) or 1.0
    out = out / peak * 0.93
    fade_n = int(0.7 * SR)
    if out.shape[1] > fade_n:
        out[:, -fade_n:] *= np.linspace(1, 0, fade_n)
    # gentle fade-in too
    fin = int(0.15 * SR)
    out[:, :fin] *= np.linspace(0, 1, fin)

    data = (out.T * 32767).astype(np.int16)
    with wave.open(out_path, "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(data.tobytes())
    return out_path, pal_name
