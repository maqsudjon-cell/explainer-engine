"""primitives.py — the scene primitive library.

Each primitive has the signature:
    scene_fn(tau, D, frame, fd, gd, td, **params)
where tau = seconds into this scene, D = scene duration,
frame = RGB image, fd = ImageDraw(frame), gd = ImageDraw(glow RGB),
td = ImageDraw(txt RGBA).

Standard envelope: fade in over 0.5s, fade out over last 0.5s.
"""
import math
import numpy as np
from PIL import Image, ImageDraw
from . import MINT, MINT_BRIGHT, WHITE, DIM, RED, AMBER, BG_DARK
from .core import (
    ss, eob, eoc, lerp, c01, gf, pf, text, dml, wrap, glowtext,
    chevron, checkmark, bullet, measure, _rgba, fit_font, fit_lines,
)

# ----------------------------------------------------------------------------
# envelope helpers
# ----------------------------------------------------------------------------
def envelope(tau, D, fin=0.5, fout=0.5):
    """Return overall scene alpha (fade in / fade out)."""
    a = ss(tau / fin) if fin > 0 else 1.0
    o = 1.0 - ss((tau - (D - fout)) / fout) if fout > 0 else 1.0
    return c01(min(a, o))


def _col(params, key, default):
    v = params.get(key)
    return tuple(v) if v else default

# ----------------------------------------------------------------------------
# spark logo + wordmark
# ----------------------------------------------------------------------------
def _spark_rays(cx, cy, r_in, r_out):
    """8 rays at 45 degree steps from a hollow center."""
    rays = []
    for i in range(8):
        a = math.radians(i * 45)
        ca, sa = math.cos(a), math.sin(a)
        rays.append(((cx + ca * r_in, cy + sa * r_in),
                     (cx + ca * r_out, cy + sa * r_out)))
    return rays


def draw_spark(fd, gd, cx, cy, radius, rgb=MINT, alpha=1.0, ignite=1.0, width=None):
    """Draw the spark mark. ignite in [0,1] grows rays out, staggered."""
    if alpha <= 0:
        return
    w = width or max(4, int(radius * 0.13))
    r_in = radius * 0.34
    for i, (p_in, p_full) in enumerate(_spark_rays(cx, cy, r_in, radius)):
        # staggered ignite per ray
        local = c01((ignite * 8 - i) / 1.4) if ignite < 1.0 else 1.0
        if local <= 0:
            continue
        ex = lerp(p_in[0], p_full[0], eoc(local))
        ey = lerp(p_in[1], p_full[1], eoc(local))
        col = _rgba(rgb, alpha)
        fd.line([p_in, (ex, ey)], fill=col, width=w)
        # round caps
        fd.ellipse([p_in[0] - w / 2, p_in[1] - w / 2, p_in[0] + w / 2, p_in[1] + w / 2], fill=col)
        fd.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=col)
        # glow layer
        gcol = (int(rgb[0] * alpha), int(rgb[1] * alpha), int(rgb[2] * alpha))
        gd.line([p_in, (ex, ey)], fill=gcol, width=w)


def draw_wordmark(td, gd, cx, cy, name, size, accent=MINT, base=WHITE,
                  accent_char=None, alpha=1.0):
    """Render the brand name with one accent-colored character (e.g. '8')."""
    if alpha <= 0:
        return
    font = gf(size, 600)
    if accent_char is None and name and name[-1].isdigit():
        accent_char = name[-1]
    total_w = font.getlength(name)
    x = cx - total_w / 2
    for ch in name:
        cw = font.getlength(ch)
        col = accent if (accent_char and ch == accent_char) else base
        text(td, x + cw / 2, cy, ch, font, col, alpha, anchor="mm")
        x += cw


def spark_logo(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx, cy = W / 2, H / 2
    R = min(W, H) * p.get("scale", 0.13)
    ignite = eoc(c01(tau / 1.1))
    # gentle breathing after ignite
    breath = 1.0 + 0.03 * math.sin(tau * 1.6)
    draw_spark(fd, gd, cx, cy - R * 0.4, R * breath, MINT, e, ignite)
    if p.get("wordmark"):
        draw_wordmark(td, gd, cx, cy + R * 1.15, p["wordmark"],
                      int(R * 0.62), MINT, WHITE, p.get("accent_char"), e * ss(c01((tau - 0.8) / 0.6)))


# ----------------------------------------------------------------------------
# hook + cta
# ----------------------------------------------------------------------------
def hook(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx = W / 2
    line1 = p.get("line1", "")
    line2 = p.get("line2", "")
    maxw = W * 0.88
    # line1: small, fit to width
    f1 = fit_font(lambda s: gf(s, 500), line1, maxw, int(H * 0.062)) if line1 else gf(int(H*0.062), 500)
    # line2: big impact — scale down and wrap up to 2 lines so it never overflows
    f2, l2 = fit_lines(pf, line2, maxw, int(H * 0.13), min_size=int(H*0.05), max_lines=2) if line2 else (pf(int(H*0.13)), [])
    a1 = e * ss(c01(tau / 0.5))
    a2 = e * ss(c01((tau - 0.35) / 0.5))
    dy = lerp(40, 0, eob(c01((tau - 0.35) / 0.7)))
    if line1:
        text(td, cx, H * 0.38, line1, f1, DIM, a1, anchor="mm")
    if line2:
        line_h = int(f2.size * 1.12)
        total = line_h * len(l2)
        y0 = H * 0.54 + dy - total / 2 + line_h / 2
        for i, ln in enumerate(l2):
            yy = y0 + i * line_h
            glowtext(gd, cx, yy, ln, f2, MINT, 0.5 * a2)
            text(td, cx, yy, ln, f2, MINT_BRIGHT, a2, anchor="mm")


def cta(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx = W / 2
    R = min(W, H) * 0.075
    ignite = eoc(c01(tau / 1.0))
    draw_spark(fd, gd, cx, H * 0.34, R, MINT, e, ignite)
    wm = p.get("wordmark", "pangea8")
    draw_wordmark(td, gd, cx, H * 0.52, wm, int(H * 0.072), MINT, WHITE,
                  p.get("accent_char"), e * ss(c01((tau - 0.6) / 0.5)))
    tag = p.get("tagline", "")
    if tag:
        ft = gf(int(H * 0.034), 400)
        for i, ln in enumerate(wrap(tag, ft, W * 0.7)):
            text(td, cx, H * 0.63 + i * H * 0.05, ln, ft, WHITE,
                 e * ss(c01((tau - 0.9) / 0.5)), anchor="mm")
    url = p.get("url", "")
    if url:
        fu = gf(int(H * 0.030), 500)
        text(td, cx, H * 0.76, url, fu, MINT,
             e * ss(c01((tau - 1.2) / 0.5)), anchor="mm")


# ----------------------------------------------------------------------------
# big_counter
# ----------------------------------------------------------------------------
def big_counter(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx = W / 2
    title = p.get("title", "")
    target = int(p.get("target", 0))
    unit = p.get("unit", "")
    # count up over the bulk of the scene
    prog = ss(c01((tau - 0.4) / max(0.1, D * 0.62)))
    n = int(target * prog)
    if title:
        ft = fit_font(lambda s: gf(s, 500), title, W * 0.86, int(H * 0.040))
        text(td, cx, H * 0.34, title, ft, DIM, e, anchor="mm")
    num = f"{n:,}"
    fn = fit_font(pf, num, W * 0.88, int(H * 0.135))
    glowtext(gd, cx, H * 0.52, num, fn, MINT, 0.55 * e)
    text(td, cx, H * 0.52, num, fn, MINT_BRIGHT, e, anchor="mm")
    if unit:
        fu = fit_font(lambda s: gf(s, 500), unit, W * 0.86, int(H * 0.044))
        text(td, cx, H * 0.66, unit, fu, WHITE, e, anchor="mm")


# ----------------------------------------------------------------------------
# glowing_sphere (cached by (radius, key))
# ----------------------------------------------------------------------------
_sphere_cache = {}

def _make_sphere(radius, base, key, continents=False):
    ck = (radius, key)
    if ck in _sphere_cache:
        return _sphere_cache[ck]
    R = radius
    size = R * 2 + 8
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2
    dx = (xx - cx) / R
    dy = (yy - cy) / R
    d2 = dx * dx + dy * dy
    inside = d2 <= 1.0
    # radial gradient: bright center -> base
    z = np.sqrt(np.clip(1 - d2, 0, 1))
    # light from upper-left
    shade = np.clip(0.35 + 0.75 * (0.5 * (-dx) + 0.6 * (-dy) + 0.6 * z), 0.1, 1.3)
    img = np.zeros((size, size, 4), np.float32)
    for i in range(3):
        img[:, :, i] = base[i] * shade
    # bright core
    core = np.clip(1 - d2 * 4.0, 0, 1) ** 2
    for i in range(3):
        img[:, :, i] += (255 - base[i]) * core * 0.5
    # alpha with soft edge
    edge = np.clip((1.0 - d2) * R * 0.5, 0, 1)
    img[:, :, 3] = np.where(inside, 255, edge * 255)

    if continents:
        rng = np.random.RandomState(hash(key) & 0xFFFF)
        for _ in range(5):
            bx = rng.uniform(-0.5, 0.5)
            by = rng.uniform(-0.5, 0.5)
            br = rng.uniform(0.18, 0.32)
            blob = ((dx - bx) ** 2 + (dy - by) ** 2) <= br ** 2
            blob &= inside
            for i in range(3):
                img[:, :, i][blob] *= 0.62

    out = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGBA")
    _sphere_cache[ck] = out
    return out


def glowing_sphere(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    base = _col(p, "color", (70, 130, 180))
    R = int(min(W, H) * p.get("scale", 0.20))
    key = p.get("label", "planet")
    sphere = _make_sphere(R, base, key, p.get("continents", False))
    # gentle float; do NOT animate size
    fy = math.sin(tau * 1.1) * H * 0.012
    px = int(W / 2 - sphere.width / 2)
    py = int(H * 0.46 - sphere.height / 2 + fy)
    if e > 0.01:
        tmp = sphere.copy()
        if e < 1.0:
            al = tmp.split()[3].point(lambda v: int(v * e))
            tmp.putalpha(al)
        frame.paste(tmp, (px, py), tmp)
        # glow halo: small bright core, let blur spread
        gd.ellipse([W / 2 - R * 0.25, H * 0.46 + fy - R * 0.25,
                    W / 2 + R * 0.25, H * 0.46 + fy + R * 0.25],
                   fill=(int(base[0] * e), int(base[1] * e), int(base[2] * e)))
    label = p.get("label")
    if label:
        fl = pf(int(H * 0.058))
        text(td, W / 2, H * 0.78, label, fl, WHITE, e, anchor="mm")
    counter = p.get("counter")
    if counter:
        val, unit = counter[0], counter[1]
        fc = gf(int(H * 0.036), 500)
        s = f"{val:,} {unit}" if isinstance(val, (int, float)) else f"{val} {unit}"
        text(td, W / 2, H * 0.85, s, fc, MINT, e, anchor="mm")


# ----------------------------------------------------------------------------
# dot_grid
# ----------------------------------------------------------------------------
def dot_grid(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cols = int(p.get("cols", 10))
    rows = int(p.get("rows", 10))
    highlight = int(p.get("highlight", 0))
    title = p.get("title", "")
    area_w = W * 0.5
    area_h = H * 0.55
    x0 = W / 2 - area_w / 2
    y0 = H * 0.30
    sx = area_w / max(1, cols - 1)
    sy = area_h / max(1, rows - 1)
    r = max(4, int(min(sx, sy) * 0.28))
    total = cols * rows
    for idx in range(total):
        c = idx % cols
        rr = idx // cols
        x = x0 + c * sx
        y = y0 + rr * sy
        reveal = ss(c01((tau - 0.3 - idx * 0.012) / 0.4))
        if reveal <= 0:
            continue
        is_hi = idx < highlight
        col = MINT if is_hi else (60, 78, 74)
        a = e * reveal
        bullet(fd, x, y, r, col, a)
        if is_hi:
            gd.ellipse([x - r, y - r, x + r, y + r],
                       fill=(int(MINT[0] * a), int(MINT[1] * a), int(MINT[2] * a)))
    if title:
        ft = gf(int(H * 0.040), 500)
        text(td, W / 2, H * 0.16, title, ft, WHITE, e, anchor="mm")
    if highlight:
        fc = gf(int(H * 0.034), 500)
        text(td, W / 2, H * 0.90, f"{highlight} / {total}", fc, MINT, e, anchor="mm")


# ----------------------------------------------------------------------------
# network_graph
# ----------------------------------------------------------------------------
_net_cache = {}

def _net_layout(n, W, H, seed):
    key = (n, W, H, seed)
    if key in _net_cache:
        return _net_cache[key]
    rng = np.random.RandomState(seed)
    pts = []
    for _ in range(n):
        pts.append((rng.uniform(W * 0.18, W * 0.82),
                    rng.uniform(H * 0.26, H * 0.80)))
    # edges: connect each node to 2 nearest
    edges = []
    for i in range(n):
        d = [( (pts[i][0]-pts[j][0])**2 + (pts[i][1]-pts[j][1])**2, j) for j in range(n) if j != i]
        d.sort()
        for _, j in d[:2]:
            if (j, i) not in edges:
                edges.append((i, j))
    _net_cache[key] = (pts, edges)
    return pts, edges


def network_graph(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    n = int(p.get("nodes", 26))
    pts, edges = _net_layout(n, W, H, int(p.get("seed", 3)))
    title = p.get("title", "")
    caption = p.get("caption", "")
    # progressive edge light-up
    for k, (i, j) in enumerate(edges):
        rev = ss(c01((tau - 0.4 - k * 0.02) / 0.5))
        if rev <= 0:
            continue
        shimmer = 0.5 + 0.5 * math.sin(tau * 3 + k)
        b = (0.25 + 0.35 * shimmer) * rev * e
        col = (int(MINT[0] * b * 0.5), int(MINT[1] * b), int(MINT[2] * b * 0.7), int(200 * rev * e))
        fd.line([pts[i], pts[j]], fill=col, width=2)
        gd.line([pts[i], pts[j]], fill=(int(MINT[0]*b*0.3), int(MINT[1]*b*0.5), int(MINT[2]*b*0.4)), width=1)
        # traveling dot
        tp = (tau * 0.6 + k * 0.3) % 1.0
        dx = lerp(pts[i][0], pts[j][0], tp)
        dy = lerp(pts[i][1], pts[j][1], tp)
        if rev > 0.5:
            bullet(fd, dx, dy, 3, MINT_BRIGHT, e * rev)
            gd.ellipse([dx-3, dy-3, dx+3, dy+3], fill=(int(MINT[0]*e), int(MINT[1]*e), int(MINT[2]*e)))
    # nodes
    hi = int(p.get("highlight", -1))
    for i, (x, y) in enumerate(pts):
        rev = ss(c01((tau - 0.3 - i * 0.02) / 0.4))
        if rev <= 0:
            continue
        if i == hi:
            bullet(fd, x, y, 9, MINT_BRIGHT, e * rev)
            gd.ellipse([x-9, y-9, x+9, y+9], fill=(int(MINT[0]*e), int(MINT[1]*e), int(MINT[2]*e)))
            fh = gf(int(H * 0.028), 600)
            text(td, x, y - 22, p.get("you_label", "YOU"), fh, MINT_BRIGHT, e * rev, anchor="mm")
        else:
            bullet(fd, x, y, 5, MINT, e * rev * 0.85)
    if title:
        ft = pf(int(H * 0.058))
        text(td, W / 2, H * 0.16, title, ft, MINT_BRIGHT, e, anchor="mm")
    if caption:
        fc = gf(int(H * 0.034), 400)
        text(td, W / 2, H * 0.90, caption, fc, WHITE, e, anchor="mm")


# ----------------------------------------------------------------------------
# line_chart
# ----------------------------------------------------------------------------
def line_chart(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    title = p.get("title", "")
    values = p.get("values", [10, 12, 18, 30, 55, 120, 280, 600])
    ax0 = W * 0.18
    ax1 = W * 0.82
    ay0 = H * 0.78  # baseline (bottom)
    ay1 = H * 0.30  # top
    vmax = max(values) or 1
    pts = []
    for i, v in enumerate(values):
        x = lerp(ax0, ax1, i / max(1, len(values) - 1))
        y = lerp(ay0, ay1, v / vmax)
        pts.append((x, y))
    # axes
    axc = (DIM[0], DIM[1], DIM[2], int(180 * e))
    fd.line([(ax0, ay0), (ax1, ay0)], fill=axc, width=2)
    fd.line([(ax0, ay0), (ax0, ay1)], fill=axc, width=2)
    # progressive polyline reveal
    rev = c01((tau - 0.4) / max(0.1, D * 0.6))
    nshow = rev * (len(pts) - 1)
    seg = int(nshow)
    for i in range(seg):
        fd.line([pts[i], pts[i + 1]], fill=(MINT[0], MINT[1], MINT[2], int(255 * e)), width=4)
        gd.line([pts[i], pts[i + 1]], fill=(int(MINT[0]*e*0.6), int(MINT[1]*e*0.6), int(MINT[2]*e*0.6)), width=3)
    if seg < len(pts) - 1:
        frac = nshow - seg
        x = lerp(pts[seg][0], pts[seg + 1][0], frac)
        y = lerp(pts[seg][1], pts[seg + 1][1], frac)
        fd.line([pts[seg], (x, y)], fill=(MINT[0], MINT[1], MINT[2], int(255 * e)), width=4)
        bullet(fd, x, y, 6, MINT_BRIGHT, e)
        gd.ellipse([x-6, y-6, x+6, y+6], fill=(int(MINT[0]*e), int(MINT[1]*e), int(MINT[2]*e)))
    if title:
        ft = gf(int(H * 0.044), 500)
        text(td, W / 2, H * 0.18, title, ft, WHITE, e, anchor="mm")


# ----------------------------------------------------------------------------
# section_card / title_card
# ----------------------------------------------------------------------------
def section_card(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx = W / 2
    number = p.get("number", "")
    label = p.get("label", "")
    if number:
        fn = pf(int(H * 0.16))
        glowtext(gd, cx, H * 0.46, str(number), fn, MINT, 0.5 * e)
        text(td, cx, H * 0.46, str(number), fn, MINT_BRIGHT, e, anchor="mm")
    if label:
        fl = fit_font(lambda q: gf(q, 500), label, W * 0.86, int(H * 0.044))
        text(td, cx, H * 0.60, label, fl, WHITE, e, anchor="mm")
    # small spark accents flanking
    R = H * 0.03
    draw_spark(fd, gd, cx - W * 0.18, H * 0.46, R, MINT, e * 0.8, 1.0)
    draw_spark(fd, gd, cx + W * 0.18, H * 0.46, R, MINT, e * 0.8, 1.0)


# ----------------------------------------------------------------------------
# person_icon (single + helper for crowds)
# ----------------------------------------------------------------------------
def _draw_person(fd, cx, cy, s, col, alpha):
    c = _rgba(col, alpha)
    # head
    hr = s * 0.32
    fd.ellipse([cx - hr, cy - s * 0.5, cx + hr, cy - s * 0.5 + hr * 2], fill=c)
    # shoulders (pieslice)
    fd.pieslice([cx - s * 0.55, cy + s * 0.05, cx + s * 0.55, cy + s * 1.1],
                180, 360, fill=c)


def person_icon(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    title = p.get("title", "")
    s = H * 0.13
    _draw_person(fd, W / 2, H * 0.50, s, MINT, e)
    gd.ellipse([W/2 - s*0.3, H*0.50 - s*0.4, W/2 + s*0.3, H*0.50 + s*0.2],
               fill=(int(MINT[0]*e*0.5), int(MINT[1]*e*0.5), int(MINT[2]*e*0.5)))
    if title:
        ft = gf(int(H * 0.044), 500)
        text(td, W / 2, H * 0.72, title, ft, WHITE, e, anchor="mm")


# ----------------------------------------------------------------------------
# word_upgrade (kinetic vocab unit)
# ----------------------------------------------------------------------------
def word_upgrade(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    cx = W / 2
    weak = p.get("weak", "good")
    strong = p.get("strong", "excellent")
    example = p.get("example", "")
    label = p.get("label", "")
    counter = p.get("counter")  # [n, total]

    # phase timings
    t_weak = c01(tau / 0.6)
    t_strike = c01((tau - 0.7) / 0.5)
    t_chev = c01((tau - 1.2) / 0.4)
    t_strong = c01((tau - 1.5) / 0.6)
    t_ex = c01((tau - 2.3) / 0.6)

    fw = gf(int(H * 0.075), 500)
    # weak word fades, then dims when replaced
    weak_alpha = e * ss(t_weak) * (1 - 0.55 * ss(t_strong))
    wy = H * 0.40
    text(td, cx, wy, weak, fw, DIM, weak_alpha, anchor="mm")
    # red strikethrough
    if t_strike > 0:
        ww = fw.getlength(weak)
        x1 = cx - ww / 2
        x2 = cx - ww / 2 + ww * ss(t_strike)
        fd.line([(x1, wy), (x2, wy)], fill=_rgba(RED, e), width=max(4, int(H*0.008)))
    # chevron down
    if t_chev > 0:
        chevron(fd, cx, H * 0.52, H * 0.022, MINT, e * ss(t_chev), direction="down")
    # strong word slams in (fixed size, position overshoot)
    if t_strong > 0:
        fs = pf(int(H * 0.092))
        dy = lerp(36, 0, eob(t_strong))
        sa = e * ss(t_strong)
        sy = H * 0.63 + dy
        # glow flash early
        flash = 1.0 - c01((tau - 1.5) / 0.5)
        glowtext(gd, cx, sy, strong, fs, MINT, (0.5 + 0.8 * flash) * sa)
        text(td, cx, sy, strong, fs, MINT_BRIGHT, sa, anchor="mm")
    # example sentence
    if t_ex > 0 and example:
        fe = gf(int(H * 0.034), 400)
        for i, ln in enumerate(wrap(example, fe, W * 0.7)):
            text(td, cx, H * 0.78 + i * H * 0.05, ln, fe, WHITE, e * ss(t_ex), anchor="mm")
    # section label + counter
    if label:
        fl = gf(int(H * 0.026), 600)
        text(td, W * 0.12, H * 0.12, label.upper(), fl, MINT, e, anchor="lm")
    if counter:
        fcn = gf(int(H * 0.026), 500)
        text(td, W * 0.88, H * 0.12, f"{counter[0]:02d} / {counter[1]}", fcn, DIM, e, anchor="rm")


# ----------------------------------------------------------------------------
# bullet_list
# ----------------------------------------------------------------------------
def bullet_list(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    title = p.get("title", "")
    items = p.get("items", [])  # list of [label, desc]
    x0 = W * 0.22
    y0 = H * 0.34
    row_h = H * 0.11
    if title:
        ft = pf(int(H * 0.060))
        text(td, W / 2, H * 0.20, title, ft, MINT_BRIGHT, e, anchor="mm")
    fl = gf(int(H * 0.040), 600)
    fdd = gf(int(H * 0.030), 400)
    for i, item in enumerate(items):
        rev = ss(c01((tau - 0.4 - i * 0.18) / 0.5))
        if rev <= 0:
            continue
        a = e * rev
        dx = lerp(-30, 0, eoc(rev))
        y = y0 + i * row_h
        bullet(fd, x0 + dx, y, max(5, int(H * 0.010)), MINT, a)
        gd.ellipse([x0+dx-6, y-6, x0+dx+6, y+6], fill=(int(MINT[0]*a*0.6), int(MINT[1]*a*0.6), int(MINT[2]*a*0.6)))
        label = item[0] if isinstance(item, (list, tuple)) else str(item)
        desc = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else ""
        text(td, x0 + dx + W * 0.025, y, label, fl, MINT_BRIGHT, a, anchor="lm")
        if desc:
            text(td, x0 + dx + W * 0.025, y + H * 0.040, desc, fdd, DIM, a, anchor="lm")


# ----------------------------------------------------------------------------
# screenshot_kenburns
# ----------------------------------------------------------------------------
def _browser_frame(img, W, H, url="pangea8.com"):
    """Wrap an image in a rounded dark browser window. Returns RGBA."""
    pad = int(min(W, H) * 0.02)
    bar = int(min(W, H) * 0.05)
    fw = img.width + pad * 2
    fh = img.height + pad * 2 + bar
    win = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    d = ImageDraw.Draw(win)
    rad = int(min(W, H) * 0.018)
    d.rounded_rectangle([0, 0, fw, fh], radius=rad, fill=(16, 22, 20, 255),
                        outline=(int(MINT[0]*0.5), int(MINT[1]*0.5), int(MINT[2]*0.5), 200), width=2)
    # title dots
    for i, c in enumerate([(232,90,82),(255,200,120),(56,222,158)]):
        d.ellipse([pad + i*bar*0.32, bar*0.38, pad + i*bar*0.32 + bar*0.2, bar*0.58], fill=c+(255,))
    # url pill
    pill_w = fw * 0.4
    d.rounded_rectangle([fw/2 - pill_w/2, bar*0.28, fw/2 + pill_w/2, bar*0.72],
                        radius=bar*0.22, fill=(8, 12, 11, 255))
    fu = gf(int(bar * 0.34), 400)
    d.text((fw/2, bar*0.5), url, font=fu, fill=(150,168,182,255), anchor="mm")
    # content with rounded mask
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, img.width, img.height], radius=rad//2, fill=255)
    win.paste(img, (pad, pad + bar), mask)
    return win


def screenshot_kenburns(tau, D, frame, fd, gd, td, **p):
    W, H = frame.size
    e = envelope(tau, D)
    # We can't load external images in the sandbox reliably; render a synthetic
    # "screenshot" (gradient + mock UI) if no path is given or load fails.
    title = p.get("title", "")
    src = p.get("image")
    base_img = None
    if src:
        try:
            base_img = Image.open(src).convert("RGB")
        except Exception:
            base_img = None
    iw, ih = int(W * 0.52), int(H * 0.52)
    if base_img is None:
        base_img = _mock_screenshot(iw * 2, ih * 2)
    # ken burns: interpolate a normalized crop
    z0, z1 = 1.0, 1.12
    z = lerp(z0, z1, eoc(c01(tau / D)))
    cw, ch = int(base_img.width / z), int(base_img.height / z)
    ox = int((base_img.width - cw) * (0.3 + 0.4 * c01(tau / D)))
    oy = int((base_img.height - ch) * 0.4)
    crop = base_img.crop((ox, oy, ox + cw, oy + ch)).resize((iw, ih), Image.BILINEAR)
    win = _browser_frame(crop, W, H, p.get("url", "pangea8.com"))
    px = int(W / 2 - win.width / 2)
    py = int(H * 0.52 - win.height / 2)
    if e > 0.01:
        tmp = win
        if e < 1.0:
            al = win.split()[3].point(lambda v: int(v * e))
            tmp = win.copy(); tmp.putalpha(al)
        frame.paste(tmp, (px, py), tmp)
        # mint edge glow
        gd.rounded_rectangle([px, py, px+win.width, py+win.height], radius=20,
                             outline=(int(MINT[0]*e*0.5), int(MINT[1]*e*0.5), int(MINT[2]*e*0.5)), width=4)
    if title:
        ft = gf(int(H * 0.044), 500)
        text(td, W / 2, H * 0.15, title, ft, WHITE, e, anchor="mm")


def _mock_screenshot(W, H):
    """Synthetic product screenshot for demos without a real image."""
    img = Image.new("RGB", (W, H), (10, 14, 13))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, int(H*0.14)], fill=(14, 20, 18))
    d.ellipse([int(W*0.04), int(H*0.04), int(W*0.04)+int(H*0.06), int(H*0.04)+int(H*0.06)], fill=MINT)
    fb = gf(int(H * 0.05), 600)
    d.text((int(W*0.16), int(H*0.07)), "pangea8", font=fb, fill=WHITE, anchor="lm")
    # cards grid
    for r in range(2):
        for c in range(3):
            x = int(W*0.06) + c*int(W*0.30)
            y = int(H*0.22) + r*int(H*0.34)
            d.rounded_rectangle([x, y, x+int(W*0.26), y+int(H*0.28)], radius=18,
                                fill=(18, 26, 23), outline=(40, 60, 54), width=2)
            d.rounded_rectangle([x+20, y+20, x+120, y+50], radius=12, fill=(30, 48, 42))
            ft = gf(int(H*0.032), 600)
            d.text((x+24, y+90), "Mock Listening", font=ft, fill=WHITE, anchor="lm")
    return img


# ----------------------------------------------------------------------------
# registry
# ----------------------------------------------------------------------------
PRIMITIVES = {
    "spark_logo": spark_logo,
    "hook": hook,
    "cta": cta,
    "big_counter": big_counter,
    "glowing_sphere": glowing_sphere,
    "dot_grid": dot_grid,
    "network_graph": network_graph,
    "line_chart": line_chart,
    "section_card": section_card,
    "title_card": section_card,
    "person_icon": person_icon,
    "word_upgrade": word_upgrade,
    "bullet_list": bullet_list,
    "screenshot_kenburns": screenshot_kenburns,
}
