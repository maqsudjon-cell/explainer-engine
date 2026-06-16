"""render_fast.py — parallel, multi-core frame rendering.

Renders frames across all CPU cores using a process pool. On a typical
4–8 core laptop this is 3–6x faster than the single-process path.

    python -m engine.render_fast SPEC.json [START END] [--workers N]
"""
import os
import sys
import time
import multiprocessing as mp
from PIL import Image, ImageDraw

from . import backgrounds
from .core import finish
from .primitives import PRIMITIVES
from . import spec as spec_mod
from .render import FRAMES_DIR, _bg_for

# worker globals (set once per process)
_W = {}


def _init(spec_dict):
    """Per-process init: rebuild spec + background once, cache them."""
    spec = spec_mod.from_dict(spec_dict)
    _W["spec"] = spec
    _W["bg"] = _bg_for(spec)
    _W["timeline"] = spec.timeline()
    _W["dims"] = spec.dims()


def _render_one(i):
    spec = _W["spec"]
    bg = _W["bg"]
    timeline = _W["timeline"]
    W, H = _W["dims"]
    fps = spec.fps
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
                pp = dict(params)
                if typ in ("cta", "spark_logo") and "wordmark" not in pp:
                    pp["wordmark"] = spec.brand.wordmark
                    pp["accent_char"] = spec.brand.accent_char
                if typ == "cta" and "url" not in pp:
                    pp["url"] = spec.brand.url
                if typ == "network_graph" and "you_label" not in pp:
                    pp["you_label"] = "SIZ" if getattr(spec, "lang", "en") == "uz" else "YOU"
                fn(t - st, D, frame, fd, gd, td, **pp)
            break
    out = finish(frame, glow, txt, W, H)
    out.save(os.path.join(FRAMES_DIR, f"f{i:05d}.png"))
    return i


def render_frames_parallel(spec, start, end, workers=None, progress=True):
    """Render [start, end) across a process pool."""
    spec.validate()
    os.makedirs(FRAMES_DIR, exist_ok=True)
    workers = workers or max(1, (os.cpu_count() or 1))
    spec_dict = _spec_to_dict(spec)
    frames = list(range(start, end))
    total = len(frames)
    done = 0
    t0 = time.time()
    # chunksize keeps IPC overhead low
    chunk = max(1, total // (workers * 4) or 1)
    with mp.Pool(workers, initializer=_init, initargs=(spec_dict,)) as pool:
        for _ in pool.imap_unordered(_render_one, frames, chunksize=chunk):
            done += 1
            if progress and done % 40 == 0:
                rate = done / (time.time() - t0 + 1e-9)
                eta = (total - done) / (rate + 1e-9)
                print(f"  {done}/{total}  ({rate:.1f} fps, ETA {eta:.0f}s)", flush=True)
    if progress:
        dt = time.time() - t0
        print(f"  {total} frames in {dt:.1f}s ({total/dt:.1f} fps, {workers} workers)")
    return total


def _spec_to_dict(spec):
    from dataclasses import asdict
    return asdict(spec)


def main(argv):
    if not argv:
        print("usage: python -m engine.render_fast SPEC.json [START END] [--workers N]")
        return 1
    workers = None
    if "--workers" in argv:
        i = argv.index("--workers")
        workers = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    spec = spec_mod.load(argv[0])
    total = int(round(spec.total_duration() * spec.fps))
    if len(argv) >= 3:
        start, end = int(argv[1]), int(argv[2])
    else:
        start, end = 0, total
    print(f"Parallel render '{spec.title}' [{start},{end}) of {total} "
          f"@ {spec.dims()} {spec.fps}fps")
    render_frames_parallel(spec, start, end, workers=workers)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
