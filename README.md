# explainer-engine

Generate **branded, narration-free explainer videos** — kinetic text, data
visualizations, a glowing neon aesthetic, and an original multi-section
synthesized soundtrack — entirely from code. Topic in, finished `.mp4` out.

![spark logo](docs/sample_spark.png)

Two decoupled modes:

- **ideate** — `python cli.py ideate "How big is the universe?"` asks Claude
  (as a creative director) to author a **content spec** (JSON).
- **render** — `python cli.py render specs/universe.json` turns a spec into
  PNG frames → silent H.264 → synthesized audio → final MP4.

The **spec JSON is the contract**. A human, Claude, or the ideate module can
all author specs — no engine code changes needed for a new video.

---

## Quick start

```bash
# 1. install
pip install -r requirements.txt          # pillow + numpy
#    ffmpeg: use system ffmpeg, or `pip install imageio-ffmpeg` as a fallback

# 2. render an example (short, ~52s)
python cli.py render specs/vocab.json
#    -> out/final.mp4

# 3. or render the flagship (~2 min) in chunks via the Makefile
make render SPEC=specs/universe.json
```

Preview a single frame while iterating (invaluable — catches layout bugs cheaply):

```bash
python cli.py preview specs/universe.json --frame 600
```

---

## Requirements

- **Python 3.9+**, `pillow`, `numpy` (see `requirements.txt`).
- **ffmpeg** — either the system binary on your `PATH`, or `imageio-ffmpeg`
  (the engine auto-detects, preferring system ffmpeg).
- **Fonts** ship in `fonts/`: **Fredoka** (variable weight — the whole look
  depends on it) and **Poppins ExtraBold** (big impact words). Both are
  open-source Google Fonts.
- For `ideate` only: `pip install anthropic` and set `ANTHROPIC_API_KEY`.

---

## How it renders (the frame pipeline)

Each frame composites **three layers**:

| layer   | mode | what goes here                                  |
|---------|------|-------------------------------------------------|
| `frame` | RGB  | opaque visuals (planets, dots, chart lines)     |
| `glow`  | RGB  | bright shapes that should **bloom** (black = none) |
| `txt`   | RGBA | **all text**, composited last so edges stay crisp |

The bloom uses an optimized **3-pass downsampled blur** (~9× faster than
full-res) in `engine/core.py:finish()`.

Resolutions: `landscape` 1920×1080, `vertical` 1080×1920, `square` 1080×1080.
Default 24 fps.

---

## Chunked rendering (important for long videos)

A 3-minute video at 24 fps is ~4,300 PNGs — rendering in one process is slow
and memory-heavy. `engine/render.py` accepts a frame range:

```bash
python -m engine.render specs/universe.json 0 750     # render frames [0,750)
python -m engine.render specs/universe.json 750 1500  # next chunk ...
python -m engine.assemble specs/universe.json         # frames -> mp4 + audio
```

The **Makefile** drives this automatically:

```bash
make render SPEC=specs/universe.json   # chunks, then assembles
make clean                              # wipe out/ artifacts
```

Backgrounds and cached sprites are module-level, so they're built once per
process. Frames are written to `out/frames/`, never held in RAM.

---

## The spec format

```json
{
  "title": "How big is the universe?",
  "resolution": "landscape",
  "fps": 24,
  "background": "starfield+radialglow",
  "brand": { "wordmark": "pangea8", "url": "pangea8.com", "accent_char": "8" },
  "audio": { "tempo_bpm": 120, "sections": [
      {"name": "intro", "start": 0},
      {"name": "climax", "start": 84, "pivot_to_major": true},
      {"name": "finale", "start": 150} ] },
  "scenes": [
    {"type": "hook", "duration": 8, "params": {"line1": "How big is", "line2": "THE UNIVERSE?"}},
    {"type": "big_counter", "duration": 18, "params": {"title": "GALAXIES", "target": 2000000000000}},
    {"type": "cta", "duration": 17, "params": {"tagline": "Master English & IELTS — free."}}
  ]
}
```

`background`: `grid`, `starfield`, `radialglow`, or combos joined by `+`.
Audio `sections[].name`: `intro, build, drive, climax, warm, uplift, finale`.
Mark the turning point with `"pivot_to_major": true`.

---

## Scene primitives

| type | purpose | key params |
|------|---------|------------|
| `hook` | opening lines | `line1`, `line2` |
| `big_counter` | number counts up from 0 | `title`, `target`, `unit` |
| `glowing_sphere` | planet/star disc | `label`, `color`, `scale`, `continents`, `counter` |
| `dot_grid` | N×M dots, highlight subset | `cols`, `rows`, `highlight`, `title` |
| `network_graph` | nodes + lighting edges | `nodes`, `highlight`, `title`, `caption` |
| `line_chart` | progressive polyline | `title`, `values` |
| `section_card` | chapter divider | `number`, `label` |
| `person_icon` | a silhouette | `title` |
| `word_upgrade` | kinetic vocab swap | `weak`, `strong`, `example`, `label`, `counter` |
| `bullet_list` | animated rows | `title`, `items` |
| `spark_logo` | brand mark intro | `wordmark`, `accent_char` |
| `cta` | closing call-to-action | `tagline`, `url` |

All colors/sizes are parameterized. Arrows/checks/bullets are **drawn**
(Fredoka has no glyphs for many symbols), so there are no tofu boxes.

---

## The soundtrack

`engine/audio.py` synthesizes everything from scratch with numpy — no samples.
Stereo, 44.1 kHz, written via the stdlib `wave` module.

- Per-bar **pads + sub bass** over a 4-chord progression.
- Per-beat **percussion/arps/lead gated by section**, so texture evolves:
  sparse intro → 4-on-the-floor drive → fast 16th climax → triumphant finale.
- A **minor → major pivot** at the climax, with a **riser + boom** placed right
  before it so the turn lands.
- Master: `tanh` soft-clip → normalize to ~0.93 peak → 0.6 s end fade.

Section boundaries line up with scene boundaries (the spec carries both).

---

## ideate (topic → spec)

```bash
export ANTHROPIC_API_KEY=sk-...
pip install anthropic
python cli.py ideate "Why sleep matters" --brand pangea8
# -> writes specs/why_sleep_matters.json for you to review, then render
```

The system prompt (`ideate/director_prompt.md`) gives Claude the full primitive
catalog and demands valid JSON matching the schema. Ideation and rendering are
separate so you can hand-edit specs or have an LLM write them.

---

## Repo layout

```
explainer-engine/
  fonts/          Fredoka.ttf (variable), Poppins-ExtraBold.ttf
  engine/
    core.py       easing, font cache, glow finish(), text/draw helpers
    primitives.py the scene primitive library
    backgrounds.py grid / starfield / radialglow builders
    audio.py      numpy synth + section/progression sequencer
    assemble.py   ffmpeg wrappers (frames->mp4, mux)
    spec.py       dataclasses + JSON (de)serialization
    render.py     spec -> frames (chunked)
  ideate/
    generate.py   topic -> spec via Anthropic API
    director_prompt.md
  specs/          example specs (universe.json, vocab.json)
  out/            frames/ + final videos
  cli.py          ideate / render / preview
  Makefile        chunked render driver
```

---

## License

Code: MIT. Fonts: SIL Open Font License (Fredoka, Poppins) — see Google Fonts.
