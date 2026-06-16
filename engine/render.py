"""render.py — spec -> PNG frames (chunked) + drives audio + assembly.

Usage:
    python -m engine.render SPEC.json [START END]
    (no START/END = render all frames in-process)
"""
import os
import sys
from PIL import Image, ImageDraw
from . import backgrounds
from .core import finish
from .primitives import PRIMITIVES
from . import spec as spec_mod

FRAMES_DIR = os.path.join(os.path.dirname(__file__), "..", "out", "frames")


def _bg_for(spec):
    W, H = spec.dims()
    accent = tuple(spec.brand.mint)
    return backgrounds.build_background(spec.background, W, H, accent=accent)


def render_frames(spec, start, end, bg=None, progress=True):
    """Render frames [start, end) to disk."""
    spec.validate()
    W, H = spec.dims()
    fps = spec.fps
    os.makedirs(FRAMES_DIR, exist_ok=True)
    if bg is None:
        bg = _bg_for(spec)
    timeline = spec.timeline()
    total = int(round(spec.total_duration() * fps))
    end = min(end, total)

    for i in range(start, end):
        t = i / fps
        frame = bg.copy()
        glow = Image.new("RGB", (W, H), (0, 0, 0))
        txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fd = ImageDraw.Draw(frame, "RGBA")
        gd = ImageDraw.Draw(glow, "RGBA")
        td = ImageDraw.Draw(txt, "RGBA")

        for (st, D, typ, params) in timeline:
            if st <= t < st + D:
                fn = PRIMITIVES.get(typ)
                if fn:
                    # inject brand defaults for logo/cta scenes
                    pp = dict(params)
                    if typ in ("cta", "spark_logo") and "wordmark" not in pp:
                        pp["wordmark"] = spec.brand.wordmark
                        pp["accent_char"] = spec.brand.accent_char
                    if typ == "cta" and "url" not in pp:
                        pp["url"] = spec.brand.url
                    # localize built-in labels by spec language
                    if typ == "network_graph" and "you_label" not in pp:
                        pp["you_label"] = "SIZ" if getattr(spec, "lang", "en") == "uz" else "YOU"
                    fn(t - st, D, frame, fd, gd, td, **pp)
                break

        out = finish(frame, glow, txt, W, H)
        out.save(os.path.join(FRAMES_DIR, f"f{i:05d}.png"))
        if progress and (i - start) % 50 == 0:
            print(f"  frame {i}/{end}", flush=True)

    return total


def main(argv):
    if len(argv) < 1:
        print("usage: python -m engine.render SPEC.json [START END]")
        return 1
    spec = spec_mod.load(argv[0])
    total = int(round(spec.total_duration() * spec.fps))
    if len(argv) >= 3:
        start, end = int(argv[1]), int(argv[2])
    else:
        start, end = 0, total
    print(f"Rendering '{spec.title}' frames [{start},{end}) of {total} "
          f"@ {spec.dims()} {spec.fps}fps")
    render_frames(spec, start, end)
    print("  done.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
