"""backgrounds.py — precomputed background builders.

Backgrounds are built ONCE per run and copied per frame, never redrawn.
"""
import random
import numpy as np
from PIL import Image, ImageDraw
from . import BG_DARK, BG_SPACE, MINT, GRID


def _radial_glow_np(W, H, color, strength=0.22, cx=0.5, cy=0.42, spread=0.6):
    """Additive radial glow toward a center point, as an HxWx3 float array."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xx = (xx / W - cx)
    yy = (yy / H - cy)
    # aspect-correct distance
    d = np.sqrt(xx ** 2 + yy ** 2)
    g = np.clip(1.0 - d / spread, 0.0, 1.0) ** 2
    g = g * strength
    out = np.zeros((H, W, 3), np.float32)
    for i in range(3):
        out[:, :, i] = g * color[i]
    return out


def build_background(kind, W, H, base=None, accent=MINT, seed=7):
    """Return an RGB PIL Image for the given background kind.

    kind: 'grid' | 'starfield' | 'radialglow' | combos joined by '+'
          (e.g. 'starfield+radialglow', 'grid+radialglow')
    """
    kinds = kind.split("+") if kind else ["grid"]
    space = "starfield" in kinds
    base_col = base or (BG_SPACE if space else BG_DARK)

    arr = np.zeros((H, W, 3), np.float32)
    arr[:, :] = base_col

    # subtle vertical vignette darkening at edges
    yy = np.linspace(-1, 1, H)[:, None]
    xx = np.linspace(-1, 1, W)[None, :]
    vig = 1.0 - 0.18 * np.clip(xx ** 2 + yy ** 2, 0, 1)
    arr *= vig[:, :, None]

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    d = ImageDraw.Draw(img, "RGBA")

    if "grid" in kinds:
        step = max(40, W // 36)
        gc = (GRID[0], GRID[1], GRID[2], 150)
        for x in range(0, W, step):
            d.line([(x, 0), (x, H)], fill=gc, width=1)
        for y in range(0, H, step):
            d.line([(0, y), (W, y)], fill=gc, width=1)

    if space:
        rng = random.Random(seed)
        n = int(W * H / 5200)
        for _ in range(n):
            x = rng.randint(0, W - 1)
            y = rng.randint(0, H - 1)
            r = rng.choice([1, 1, 1, 2])
            b = rng.randint(60, 200)
            tint = rng.random()
            col = (
                int(b * (0.8 + 0.2 * tint)),
                int(b * (0.85 + 0.15 * tint)),
                int(b),
                rng.randint(120, 255),
            )
            if r == 1:
                d.point((x, y), fill=col)
            else:
                d.ellipse([x - 1, y - 1, x + 1, y + 1], fill=col)

    if "radialglow" in kinds or space:
        strength = 0.26 if space else 0.20
        glow = _radial_glow_np(W, H, accent, strength=strength)
        out = np.asarray(img).astype(np.float32) + glow
        img = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")

    return img
