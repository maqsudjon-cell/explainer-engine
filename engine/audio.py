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
    click = (np.random.rand(n) * 2 - 1) * np.exp(-t * 120) * 0.5
    return (body + click) * 0.9


def hat(dur=0.06):
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    # crude high-pass: difference
    noise = np.diff(noise, prepend=0)
    return noise * np.exp(-t * 90) * 0.4


def clap(dur=0.3):
    n = int(dur * SR)
    t = _t(n)
    out = np.zeros(n)
    for d in [0.0, 0.012, 0.024]:
        s = int(d * SR)
        e = np.exp(-(t) * 50)
        burst = (np.random.rand(n) * 2 - 1) * e
        out[s:] += burst[:n - s]
    return out * 0.35


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
    sweep = np.sin(2 * np.pi * (200 + 800 * (t / dur) ** 2) * t)
    e = (t / dur) ** 2
    return (noise * 0.4 + sweep * 0.6) * e * 0.5


def whoosh(dur=0.6):
    n = int(dur * SR)
    t = _t(n)
    noise = np.random.rand(n) * 2 - 1
    e = np.exp(-((t - dur / 2) ** 2) / (2 * (dur / 5) ** 2))
    return noise * e * 0.4


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
    """note name -> freq, e.g. A2, C4."""
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5,
             "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
    n = name[:-1]
    octave = int(name[-1])
    midi = 12 * (octave + 1) + names[n]
    return 440.0 * 2 ** ((midi - 69) / 12)


# progression = list of 4 chords: (pad_freqs, bass_root, lead_freqs)
def chord(root_notes, bass, lead_notes):
    return ([note(x) for x in root_notes], note(bass), [note(x) for x in lead_notes])


MINOR = [  # Am - F - C - G
    chord(["A3", "C4", "E4"], "A1", ["A4", "C5"]),
    chord(["F3", "A3", "C4"], "F1", ["F4", "A4"]),
    chord(["C4", "E4", "G4"], "C2", ["C5", "E5"]),
    chord(["G3", "B3", "D4"], "G1", ["G4", "B4"]),
]
MAJOR = [  # C - G - Am - F
    chord(["C4", "E4", "G4"], "C2", ["C5", "E5", "G5"]),
    chord(["G3", "B3", "D4"], "G1", ["G4", "B4", "D5"]),
    chord(["A3", "C4", "E4"], "A1", ["A4", "C5", "E5"]),
    chord(["F3", "A3", "C4"], "F1", ["F4", "A4", "C5"]),
]


# ----------------------------------------------------------------------------
# arrangement
# ----------------------------------------------------------------------------
def render_audio(spec, out_path):
    dur = spec.total_duration() + 0.8
    L, R = make_buffers(dur)

    sections = sorted(spec.audio.sections, key=lambda s: s.start) if spec.audio.sections else []

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

    n_bars = int(dur / BAR) + 1
    for b in range(n_bars):
        bar_t = b * BAR
        if bar_t >= dur:
            break
        sec = section_at(bar_t)
        prog = MAJOR if is_major(bar_t) else MINOR
        pads, bass, leads = prog[b % 4]

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
    last_prog = MAJOR if (sections and any(x.pivot_to_major for x in sections)) else MINOR
    add(L, R, padnote(last_prog[0][0], 2.0), max(0, dur - 2.2), gain=0.6)

    # ---- master ----
    stack = np.stack([L, R])
    mix = np.tanh(stack * 1.0)
    peak = np.max(np.abs(mix)) or 1.0
    mix = mix / peak * 0.93
    # end fade
    fade_n = int(0.6 * SR)
    if mix.shape[1] > fade_n:
        fade = np.linspace(1, 0, fade_n)
        mix[:, -fade_n:] *= fade

    # write 16-bit PCM
    data = (mix.T * 32767).astype(np.int16)
    with wave.open(out_path, "w") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return out_path
