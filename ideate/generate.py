"""generate.py — topic -> spec via the Anthropic API (Claude as creative director)."""
import os
import json
import re

from engine import spec as spec_mod

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "director_prompt.md")
DEFAULT_MODEL = os.environ.get("EXPLAINER_MODEL", "claude-sonnet-4-6")

BRANDS = {
    "pangea8": {"wordmark": "pangea8", "url": "pangea8.com", "accent_char": "8"},
}


def _system_prompt():
    with open(PROMPT_PATH) as f:
        return f.read()


def _extract_json(text):
    """Pull the JSON object out of a model response, tolerating fences/prose."""
    text = text.strip()
    # strip code fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # find the outermost {...}
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start:end + 1])


def ideate(topic, brand="pangea8", model=None):
    """Call Claude to produce a VideoSpec for the topic.

    Requires ANTHROPIC_API_KEY in the environment.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "The 'anthropic' package is required for ideate. "
            "Install it with: pip install anthropic"
        )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("Set ANTHROPIC_API_KEY in your environment to use ideate.")

    client = anthropic.Anthropic(api_key=api_key)
    brand_cfg = BRANDS.get(brand, BRANDS["pangea8"])

    user_msg = (
        f"Topic: {topic}\n\n"
        f"Brand wordmark: {brand_cfg['wordmark']} (accent char '{brand_cfg['accent_char']}', "
        f"url {brand_cfg['url']}).\n"
        "Produce the spec JSON now."
    )

    resp = client.messages.create(
        model=model or DEFAULT_MODEL,
        max_tokens=4000,
        system=_system_prompt(),
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
    data = _extract_json(text)

    # ensure brand defaults are present
    data.setdefault("brand", {})
    for k, v in brand_cfg.items():
        data["brand"].setdefault(k, v)

    spec = spec_mod.from_dict(data)
    spec.validate()
    return spec
