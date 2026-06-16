"""server.py — local backend for the explainer-engine desktop app.

Endpoints:
  GET  /                  -> the chatbot UI
  GET  /api/health        -> {ok, has_key}
  POST /api/chat          -> Claude turn (text + optional image); may return a spec
  POST /api/render        -> start a render job (video or poster); returns job id
  GET  /api/job/<id>      -> job status/progress
  GET  /files/<name>      -> serve rendered output (mp4/png)
"""
import os
import io
import re
import sys
import json
import time
import uuid
import base64
import threading

from flask import Flask, request, jsonify, send_from_directory, send_file, Response

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import spec as spec_mod
from engine import render as render_mod
from engine import assemble as assemble_mod

UI_DIR = os.path.join(ROOT, "app", "ui")
JOBS_DIR = os.path.join(ROOT, "out", "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

app = Flask(__name__, static_folder=None)

# in-memory job table
JOBS = {}

DEFAULT_MODEL = os.environ.get("EXPLAINER_MODEL", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# chat system prompt (creative director that can also emit a spec)
# ---------------------------------------------------------------------------
def _director_catalog():
    p = os.path.join(ROOT, "ideate", "director_prompt.md")
    try:
        with open(p) as f:
            return f.read()
    except Exception:
        return ""


CHAT_SYSTEM = (
    "You are the in-app creative director for 'explainer-engine', a tool that "
    "renders branded, narration-free explainer VIDEOS and single-frame POSTERS "
    "in a dark neon-mint motion-graphics style (it does NOT generate photoreal "
    "images like Midjourney; it composes kinetic text, counters, charts, spheres, "
    "and network graphs).\n\n"
    "Behaviour:\n"
    "- Chat naturally with the user about their idea. Brainstorm, suggest angles, "
    "ask at most one short question if truly needed.\n"
    "- When the user is ready (they say things like 'make it', 'create', 'yarat', "
    "'render', or clearly approve a direction), output a spec.\n"
    "- To output a spec, include exactly one fenced code block ```json ... ``` "
    "containing a VALID spec object. You may add a short sentence before it. Do "
    "not output more than one json block.\n"
    "- For a POSTER (single still), make a spec with ONE scene and set "
    "\"poster\": true at the top level.\n"
    "- Keep on-screen text short and punchy. Numbers must be reasonable.\n\n"
    "Here is the full spec schema and the scene primitive catalog you must use "
    "(use only these scene types):\n\n" + _director_catalog()
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _client(api_key):
    import anthropic
    return anthropic.Anthropic(api_key=api_key)


def _extract_spec(text):
    """Find a ```json ...``` block and parse it. Returns (dict|None)."""
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify(ok=True, has_key=bool(os.environ.get("ANTHROPIC_API_KEY")),
                   model=DEFAULT_MODEL)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True)
    api_key = data.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify(error="no_api_key",
                       message="Add your Anthropic API key in settings to chat."), 400
    history = data.get("messages", [])
    image_b64 = data.get("image")          # optional data URL or raw b64
    image_mime = data.get("image_mime", "image/png")
    lang = data.get("lang", "en")

    system = CHAT_SYSTEM
    if lang == "uz":
        system += (
            "\n\nIMPORTANT — LANGUAGE: The user wants the video in UZBEK. Write ALL "
            "on-screen text fields (line1, line2, title, unit, label, tagline, "
            "caption, weak, strong, example, items, number labels) in natural, "
            "correct Uzbek (Latin script, e.g. o', g', sh, ch). Keep it short and "
            "punchy. Set \"lang\": \"uz\" at the top level of the spec so built-in "
            "labels localize. You may still chat with the user in their language."
        )

    # build anthropic messages
    msgs = []
    for m in history[:-1]:
        msgs.append({"role": m["role"], "content": m["content"]})
    # last user message may carry an image
    last = history[-1] if history else {"role": "user", "content": ""}
    if image_b64:
        if image_b64.startswith("data:"):
            image_b64 = image_b64.split(",", 1)[1]
        content = [
            {"type": "image", "source": {"type": "base64",
                                          "media_type": image_mime, "data": image_b64}},
            {"type": "text", "text": last.get("content", "") or "Here is an image to work from."},
        ]
        msgs.append({"role": "user", "content": content})
    else:
        msgs.append({"role": last["role"], "content": last["content"]})

    try:
        client = _client(api_key)
        resp = client.messages.create(
            model=data.get("model") or DEFAULT_MODEL,
            max_tokens=4000,
            system=system,
            messages=msgs,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    except Exception as e:
        return jsonify(error="api_error", message=str(e)), 500

    spec = _extract_spec(text)
    # strip the json block from the visible reply (UI shows a render card instead)
    visible = re.sub(r"```json\s*\{.*?\}\s*```", "", text, flags=re.S).strip()
    if spec and not visible:
        visible = "Here's a concept I can render for you:"
    return jsonify(reply=visible, spec=spec)


def _run_job(job_id, spec_dict, mode, fast=False, quality="full"):
    job = JOBS[job_id]
    try:
        # fast glow path
        try:
            from engine import core as _core
            _core.FAST = bool(fast)
        except Exception:
            pass
        spec = spec_mod.from_dict(spec_dict)
        # quality scaling: trade resolution/fps for speed
        if quality == "draft":
            spec.resolution = "square" if spec.resolution == "square" else "landscape"
            spec.fps = min(spec.fps, 18)
        spec.validate()
        W, H = spec.dims()
        fps = spec.fps
        bg = render_mod._bg_for(spec)

        if mode == "poster":
            # render a single representative frame (peak of first scene)
            from PIL import Image, ImageDraw
            from engine.core import finish
            from engine.primitives import PRIMITIVES
            # choose a frame ~60% into the first scene
            first_d = spec.scenes[0].duration
            t = first_d * 0.6
            frame = bg.copy()
            glow = Image.new("RGB", (W, H), (0, 0, 0))
            txt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fd = ImageDraw.Draw(frame, "RGBA")
            gd = ImageDraw.Draw(glow, "RGBA")
            td = ImageDraw.Draw(txt, "RGBA")
            st, D, typ, params = spec.timeline()[0]
            pp = dict(params)
            if typ in ("cta", "spark_logo") and "wordmark" not in pp:
                pp["wordmark"] = spec.brand.wordmark
                pp["accent_char"] = spec.brand.accent_char
            if typ == "cta" and "url" not in pp:
                pp["url"] = spec.brand.url
            PRIMITIVES[typ](t, D, frame, fd, gd, td, **pp)
            out = finish(frame, glow, txt, W, H)
            path = os.path.join(JOBS_DIR, job_id + ".png")
            out.save(path)
            job["progress"] = 1.0
            job["status"] = "done"
            job["file"] = job_id + ".png"
            job["kind"] = "image"
            return

        # video: render frames (parallel, all cores) then assemble
        total = int(round(spec.total_duration() * fps))
        job["total"] = total
        done = 0
        # clear previous frames
        frames_dir = render_mod.FRAMES_DIR
        os.makedirs(frames_dir, exist_ok=True)
        for f in os.listdir(frames_dir):
            if f.endswith(".png"):
                os.remove(os.path.join(frames_dir, f))
        # parallel render in chunks so we can report progress
        try:
            from engine import render_fast
            import multiprocessing as mp
            workers = max(1, (os.cpu_count() or 1))
            CH = max(40, total // (workers * 3) or 40)
            while done < total:
                end = min(done + CH, total)
                render_fast.render_frames_parallel(spec, done, end,
                                                   workers=workers, progress=False)
                done = end
                job["progress"] = 0.82 * (done / total)
                job["workers"] = workers
                if job.get("cancel"):
                    job["status"] = "cancelled"
                    return
        except Exception:
            # fallback to single-process if pool fails
            CH = 60
            while done < total:
                end = min(done + CH, total)
                render_mod.render_frames(spec, done, end, bg=bg, progress=False)
                done = end
                job["progress"] = 0.82 * (done / total)
        # audio + assemble
        job["progress"] = 0.85
        job["stage"] = "audio"
        from engine import audio2 as audio_mod
        audio_path = os.path.join(render_mod.os.path.join(ROOT, "out"), "_audio.wav")
        audio_mod.render_audio(spec, audio_path)
        job["progress"] = 0.92
        job["stage"] = "encoding"
        silent = assemble_mod.frames_to_silent(fps)
        final_tmp = assemble_mod.mux(silent, audio_path)
        # move to job file
        final_path = os.path.join(JOBS_DIR, job_id + ".mp4")
        os.replace(final_tmp, final_path)
        job["progress"] = 1.0
        job["status"] = "done"
        job["file"] = job_id + ".mp4"
        job["kind"] = "video"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/api/render", methods=["POST"])
def render():
    data = request.get_json(force=True)
    spec_dict = data.get("spec")
    if not spec_dict:
        return jsonify(error="no_spec"), 400
    mode = data.get("mode", "video")
    if spec_dict.get("poster"):
        mode = "poster"
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "progress": 0.0, "stage": "frames",
                    "kind": "video" if mode == "video" else "image"}
    fast = bool(data.get("fast", True))      # default fast ON
    quality = data.get("quality", "full")     # 'full' | 'draft'
    t = threading.Thread(target=_run_job,
                         args=(job_id, spec_dict, mode, fast, quality), daemon=True)
    t.start()
    return jsonify(job_id=job_id)


@app.route("/api/job/<job_id>")
def job_status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify(error="not_found"), 404
    return jsonify(job)


@app.route("/api/specs")
def list_specs():
    """List the bundled example specs (no API key needed)."""
    specs_dir = os.path.join(ROOT, "specs")
    out = []
    for fn in sorted(os.listdir(specs_dir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(specs_dir, fn)) as f:
                d = json.load(f)
            dur = sum(s.get("duration", 0) for s in d.get("scenes", []))
            out.append({
                "file": fn,
                "title": d.get("title", fn),
                "scenes": len(d.get("scenes", [])),
                "duration": dur,
                "poster": bool(d.get("poster")),
                "spec": d,
            })
        except Exception:
            continue
    return jsonify(specs=out)


@app.route("/api/validate", methods=["POST"])
def validate_spec():
    """Validate a hand-written spec (no API key needed)."""
    data = request.get_json(force=True)
    try:
        spec = spec_mod.from_dict(data.get("spec", {}))
        spec.validate()
        return jsonify(ok=True)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 400


@app.route("/files/<name>")
def files(name):
    """Serve a rendered file inline (for the <video>/<img> preview)."""
    path = os.path.join(JOBS_DIR, name)
    if not os.path.isfile(path):
        return jsonify(error="not_found", name=name), 404
    mt = "video/mp4" if name.endswith(".mp4") else (
        "image/png" if name.endswith(".png") else None)
    # conditional=True enables HTTP range requests so seeking works
    return send_file(path, mimetype=mt, conditional=True)


@app.route("/download/<name>")
def download(name):
    """Force a download (attachment) — reliable on Safari/Chrome."""
    path = os.path.join(JOBS_DIR, name)
    if not os.path.isfile(path):
        return jsonify(error="not_found", name=name), 404
    mt = "video/mp4" if name.endswith(".mp4") else (
        "image/png" if name.endswith(".png") else "application/octet-stream")
    nice = ("explainer-engine." + name.split(".")[-1])
    return send_file(path, mimetype=mt, as_attachment=True, download_name=nice)


def main():
    port = int(os.environ.get("PORT", "7867"))
    print(f"\n  explainer-engine  ->  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, threaded=True)


if __name__ == "__main__":
    main()
