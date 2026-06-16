"""assemble.py — ffmpeg wrappers: frames -> silent mp4 -> mux audio -> final."""
import os
import sys
import shutil
import subprocess

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "out")
FRAMES = os.path.join(OUT, "frames")


def _ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        raise RuntimeError("ffmpeg not found. Install system ffmpeg or pip install imageio-ffmpeg")


def frames_to_silent(fps=24, out_path=None):
    out_path = out_path or os.path.join(OUT, "_silent.mp4")
    ff = _ffmpeg()
    cmd = [ff, "-y", "-framerate", str(fps),
           "-i", os.path.join(FRAMES, "f%05d.png"),
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def mux(silent_path=None, audio_path=None, out_path=None):
    silent_path = silent_path or os.path.join(OUT, "_silent.mp4")
    audio_path = audio_path or os.path.join(OUT, "_audio.wav")
    out_path = out_path or os.path.join(OUT, "final.mp4")
    ff = _ffmpeg()
    if not os.path.exists(audio_path):
        # no audio: just copy silent to final
        shutil.copy(silent_path, out_path)
        return out_path
    cmd = [ff, "-y", "-i", silent_path, "-i", audio_path,
           "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", out_path]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def assemble(spec, with_audio=True):
    """Full assembly: frames -> silent -> (audio) -> final."""
    fps = spec.fps
    silent = frames_to_silent(fps)
    if with_audio:
        from . import audio2 as audio_mod
        audio_mod.render_audio(spec, os.path.join(OUT, "_audio.wav"))
    final = mux(silent, os.path.join(OUT, "_audio.wav"))
    return final


def main(argv):
    if not argv:
        print("usage: python -m engine.assemble SPEC.json")
        return 1
    from . import spec as spec_mod
    spec = spec_mod.load(argv[0])
    out = assemble(spec, with_audio=True)
    print("final:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
