#!/usr/bin/env python3
"""cli.py — ideate / render / preview commands for explainer-engine."""
import os
import sys
import argparse

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from engine import spec as spec_mod
from engine import render as render_mod
from engine import assemble as assemble_mod


def cmd_ideate(args):
    from ideate.generate import ideate
    spec = ideate(args.topic, brand=args.brand)
    out = args.out or os.path.join(ROOT, "specs", _slug(args.topic) + ".json")
    spec_mod.save(spec, out)
    print(f"Spec written to {out}")
    print(f"  {len(spec.scenes)} scenes, {spec.total_duration():.0f}s")
    print(f"Review it, then:  python cli.py render {out}")


def cmd_render(args):
    spec = spec_mod.load(args.spec)
    spec.validate()
    total = int(round(spec.total_duration() * spec.fps))
    if args.chunk:
        start, end = args.chunk
        render_mod.render_frames(spec, start, end)
        print(f"Rendered frames [{start},{end})")
    else:
        print(f"Rendering all {total} frames in-process...")
        render_mod.render_frames(spec, 0, total)
        if not args.no_assemble:
            final = assemble_mod.assemble(spec, with_audio=not args.no_audio)
            print(f"Final video: {final}")


def cmd_preview(args):
    spec = spec_mod.load(args.spec)
    spec.validate()
    bg = render_mod._bg_for(spec)
    from PIL import Image, ImageDraw
    from engine.core import finish
    from engine.primitives import PRIMITIVES
    W, H = spec.dims()
    i = args.frame
    t = i / spec.fps
    frame = bg.copy()
    glow = Image.new("RGB", (W, H), (0, 0, 0))
    txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fd = ImageDraw.Draw(frame, "RGBA")
    gd = ImageDraw.Draw(glow, "RGBA")
    td = ImageDraw.Draw(txt, "RGBA")
    for (st, D, typ, params) in spec.timeline():
        if st <= t < st + D:
            pp = dict(params)
            if typ in ("cta", "spark_logo") and "wordmark" not in pp:
                pp["wordmark"] = spec.brand.wordmark
                pp["accent_char"] = spec.brand.accent_char
            if typ == "cta" and "url" not in pp:
                pp["url"] = spec.brand.url
            PRIMITIVES[typ](t - st, D, frame, fd, gd, td, **pp)
            print(f"  frame {i} (t={t:.2f}s) -> scene '{typ}'")
            break
    out = finish(frame, glow, txt, W, H)
    out_path = args.out or os.path.join(ROOT, "out", f"preview_{i:05d}.png")
    out.save(out_path)
    print(f"Preview saved: {out_path}")


def _slug(s):
    return "".join(c if c.isalnum() else "_" for c in s.lower()).strip("_")[:40]


def main():
    p = argparse.ArgumentParser(description="explainer-engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ideate", help="topic -> spec JSON via Claude")
    pi.add_argument("topic")
    pi.add_argument("--brand", default="pangea8")
    pi.add_argument("--out", default=None)
    pi.set_defaults(func=cmd_ideate)

    pr = sub.add_parser("render", help="spec -> video")
    pr.add_argument("spec")
    pr.add_argument("--chunk", nargs=2, type=int, metavar=("START", "END"))
    pr.add_argument("--no-audio", action="store_true")
    pr.add_argument("--no-assemble", action="store_true")
    pr.set_defaults(func=cmd_render)

    pp = sub.add_parser("preview", help="render a single frame")
    pp.add_argument("spec")
    pp.add_argument("--frame", type=int, default=0)
    pp.add_argument("--out", default=None)
    pp.set_defaults(func=cmd_preview)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
