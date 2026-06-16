"""spec.py — the video spec contract (dataclasses + JSON)."""
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from . import RESOLUTIONS, FPS, MINT


@dataclass
class Scene:
    type: str
    duration: float
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioSection:
    name: str
    start: float
    pivot_to_major: bool = False


@dataclass
class AudioPlan:
    tempo_bpm: int = 120
    mood: str = None          # emotional | uplifting | cosmic | driving | tense | playful (auto if None)
    sections: List[AudioSection] = field(default_factory=list)


@dataclass
class Brand:
    mint: list = field(default_factory=lambda: list(MINT))
    wordmark: str = "pangea8"
    url: str = "pangea8.com"
    accent_char: Optional[str] = None


@dataclass
class VideoSpec:
    title: str
    resolution: str = "landscape"
    fps: int = FPS
    background: str = "grid+radialglow"
    lang: str = "en"   # "en" | "uz" — sets built-in label language
    brand: Brand = field(default_factory=Brand)
    audio: AudioPlan = field(default_factory=AudioPlan)
    scenes: List[Scene] = field(default_factory=list)

    # ---- derived ----
    def dims(self):
        return RESOLUTIONS.get(self.resolution, RESOLUTIONS["landscape"])

    def total_duration(self):
        return sum(s.duration for s in self.scenes)

    def timeline(self):
        """List of (start, duration, type, params)."""
        out = []
        t = 0.0
        for s in self.scenes:
            out.append((t, s.duration, s.type, s.params))
            t += s.duration
        return out

    def validate(self):
        from .primitives import PRIMITIVES
        errs = []
        if self.resolution not in RESOLUTIONS:
            errs.append(f"unknown resolution '{self.resolution}'")
        if not self.scenes:
            errs.append("no scenes")
        for i, s in enumerate(self.scenes):
            if s.type not in PRIMITIVES:
                errs.append(f"scene {i}: unknown type '{s.type}'")
            if s.duration <= 0:
                errs.append(f"scene {i}: duration must be > 0")
        if errs:
            raise ValueError("Invalid spec:\n  - " + "\n  - ".join(errs))
        return True


def from_dict(d: dict) -> VideoSpec:
    brand = Brand(**d.get("brand", {})) if d.get("brand") else Brand()
    ap = d.get("audio", {}) or {}
    sections = [AudioSection(**s) for s in ap.get("sections", [])]
    audio = AudioPlan(tempo_bpm=ap.get("tempo_bpm", 120),
                      mood=ap.get("mood"), sections=sections)
    scenes = [Scene(type=s["type"], duration=float(s["duration"]),
                    params=s.get("params", {})) for s in d.get("scenes", [])]
    return VideoSpec(
        title=d.get("title", "Untitled"),
        resolution=d.get("resolution", "landscape"),
        fps=int(d.get("fps", FPS)),
        background=d.get("background", "grid+radialglow"),
        lang=d.get("lang", "en"),
        brand=brand, audio=audio, scenes=scenes,
    )


def load(path: str) -> VideoSpec:
    with open(path) as f:
        return from_dict(json.load(f))


def save(spec: VideoSpec, path: str):
    d = asdict(spec)
    with open(path, "w") as f:
        json.dump(d, f, indent=2)


def to_json(spec: VideoSpec) -> str:
    return json.dumps(asdict(spec), indent=2)
