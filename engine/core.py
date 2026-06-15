"""core.py — easing, font cache, glow pipeline, text + draw helpers.

The visual identity of every video flows through this module: the optimized
three-pass glow, the variable-Fredoka font cache, and the small kit of
draw helpers (chevron / checkmark / bullet) that replace tofu-prone glyphs.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")

# ----------------------------------------------------------------------------
# easing
# ----------------------------------------------------------------------------
def lerp(a, b, t):
    return a + (b - a) * t

def c01(x):
    return max(0.0, min(1.0, x))

def ss(x):
    """smoothstep — the default fade curve."""
    x = c01(x)
    return x * x * (3 - 2 * x)

def eob(x):
    """ease-out-back — overshoot for slam-in emphasis."""
    x = c01(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2

def eoc(x):
    """ease-out-cubic — smooth deceleration."""
    x = c01(x)
    return 1 - (1 - x) ** 3

# ----------------------------------------------------------------------------
# font cache (variable Fredoka + Poppins ExtraBold)
# ----------------------------------------------------------------------------
_fc = {}

def gf(size, weight=600):
    """Fredoka, variable weight 300..700."""
    k = ("F", int(size), int(weight))
    if k not in _fc:
        f = ImageFont.truetype(os.path.join(FONT_DIR, "Fredoka.ttf"), int(size))
        try:
            f.set_variation_by_axes([int(weight), 100])  # [weight, width]
        except Exception:
            pass
        _fc[k] = f
    return _fc[k]

def pf(size):
    """Poppins ExtraBold for big impact words."""
    k = ("P", int(size))
    if k not in _fc:
        _fc[k] = ImageFont.truetype(os.path.join(FONT_DIR, "Poppins-ExtraBold.ttf"), int(size))
    return _fc[k]

# ----------------------------------------------------------------------------
# glow pipeline — optimized 3-pass bloom (~9x faster than full-res blur)
# ----------------------------------------------------------------------------
GS = 3  # downsample factor

def finish(frame, glow, txt, W, H):
    """Composite the three layers into a final RGB frame.

    frame : RGB  — opaque visuals
    glow  : RGB  — bright shapes to bloom (black = no glow)
    txt   : RGBA — text, composited last so edges stay crisp
    """
    small = glow.resize((W // GS, H // GS), Image.BILINEAR)
    acc = Image.new("RGB", (W // GS, H // GS), (0, 0, 0))
    for radius, gain in [(4, 0.9), (11, 0.58), (24, 0.45)]:
        b = small.filter(ImageFilter.GaussianBlur(radius)).point(
            lambda v: int(min(255, v * gain))
        )
        acc = ImageChops.add(acc, b)
    frame = ImageChops.add(frame, acc.resize((W, H), Image.BILINEAR))
    return Image.alpha_composite(frame.convert("RGBA"), txt).convert("RGB")

# ----------------------------------------------------------------------------
# text helpers
# ----------------------------------------------------------------------------
def _rgba(rgb, alpha):
    a = int(c01(alpha) * 255)
    return (int(rgb[0]), int(rgb[1]), int(rgb[2]), a)

def text(td, cx, cy, s, font, rgb, alpha=1.0, anchor="mm"):
    """Draw a single line of text with an alpha onto an ImageDraw (RGBA)."""
    if alpha <= 0:
        return
    td.text((cx, cy), s, font=font, fill=_rgba(rgb, alpha), anchor=anchor)

def measure(font, s):
    """(w, h) of a string in this font."""
    box = font.getbbox(s)
    return box[2] - box[0], box[3] - box[1]

def wrap(s, font, maxw):
    """Greedy word wrap to fit maxw pixels. Returns list of lines."""
    words = s.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if font.getlength(trial) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def dml(td, cx, cy, lines, font, rgb, alpha=1.0, line_h=None, anchor="mm"):
    """Draw multiline text block centered vertically on cy."""
    if alpha <= 0 or not lines:
        return
    if line_h is None:
        line_h = int(font.size * 1.25)
    total = line_h * len(lines)
    y = cy - total / 2 + line_h / 2
    for ln in lines:
        text(td, cx, y, ln, font, rgb, alpha, anchor=anchor)
        y += line_h

def glowtext(gd, cx, cy, s, font, rgb, k=1.0, anchor="mm"):
    """Draw text onto the GLOW layer so it haloes. k scales brightness."""
    col = (int(rgb[0] * k), int(rgb[1] * k), int(rgb[2] * k))
    gd.text((cx, cy), s, font=font, fill=col, anchor=anchor)

# ----------------------------------------------------------------------------
# draw helpers — replace tofu-prone glyphs with real geometry
# ----------------------------------------------------------------------------
def chevron(d, cx, cy, size, rgb, alpha=1.0, width=None, direction="down"):
    """A chevron (›/v) drawn with two lines."""
    if alpha <= 0:
        return
    w = width or max(3, int(size * 0.16))
    col = _rgba(rgb, alpha)
    s = size
    if direction == "down":
        pts = [(cx - s, cy - s * 0.5), (cx, cy + s * 0.5), (cx + s, cy - s * 0.5)]
    elif direction == "right":
        pts = [(cx - s * 0.5, cy - s), (cx + s * 0.5, cy), (cx - s * 0.5, cy + s)]
    elif direction == "up":
        pts = [(cx - s, cy + s * 0.5), (cx, cy - s * 0.5), (cx + s, cy + s * 0.5)]
    else:  # left
        pts = [(cx + s * 0.5, cy - s), (cx - s * 0.5, cy), (cx + s * 0.5, cy + s)]
    d.line([pts[0], pts[1]], fill=col, width=w, joint="curve")
    d.line([pts[1], pts[2]], fill=col, width=w, joint="curve")

def checkmark(d, cx, cy, size, rgb, alpha=1.0, width=None):
    """A checkmark drawn with two lines."""
    if alpha <= 0:
        return
    w = width or max(3, int(size * 0.18))
    col = _rgba(rgb, alpha)
    s = size
    p1 = (cx - s * 0.6, cy)
    p2 = (cx - s * 0.1, cy + s * 0.5)
    p3 = (cx + s * 0.7, cy - s * 0.55)
    d.line([p1, p2], fill=col, width=w, joint="curve")
    d.line([p2, p3], fill=col, width=w, joint="curve")

def bullet(d, cx, cy, r, rgb, alpha=1.0):
    """A filled round bullet."""
    if alpha <= 0:
        return
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_rgba(rgb, alpha))

def rounded_rect(d, box, radius, fill=None, outline=None, width=1):
    """Convenience wrapper for rounded rectangles with RGBA fill."""
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
