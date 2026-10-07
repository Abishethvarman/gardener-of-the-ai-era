"""Plant photo check: "what might be wrong with my plant?"

A vision model (Gemma 3 4b or larger) looks at a photo taken in the garden and
suggests up to three possible causes, each with a simple thing to check. The
photo goes only to the model endpoint you configured (your own laptop with
Ollama), never to a third party.

Guardrails:
* the answer is framed as possible causes, never a diagnosis;
* any spray or fertiliser amount (a number with ml, g, %, and so on) is removed
  and replaced with "ask a local nursery", because a small model shouldn't be
  giving doses;
* if the reply isn't valid JSON, the user gets a plain "couldn't read that"
  instead of half-parsed text.
"""

from __future__ import annotations

import base64
import re

from ..llm import LLMClient, LLMError
from . import FeatureError, clean_str, extract_json

MAX_IMAGE_BYTES = 6_000_000
ALLOWED_PREFIXES = ("data:image/jpeg;base64,", "data:image/png;base64,", "data:image/webp;base64,")
DOSE = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:ml|g|gm|grams?|kg|l|litres?|liters?|%|tsp|tbsp|teaspoons?|tablespoons?)(?![a-z])",
    re.I,
)
DOSE_REPLACEMENT = "Ask a local nursery or agriculture office before using any spray or fertiliser."

PROMPT = """You are helping a home gardener in {place}. {season}
Look at the photo of their plant.{note}

Reply with JSON only, in this shape:
{{"plant": "your best guess of the plant, or null",
  "looks_healthy": true or false,
  "possible_causes": [{{"cause": "a possible problem", "check": "one simple thing the gardener can check or do"}}],
  "next_step": "one sentence"}}

Rules:
- Give at most 3 possible causes, most likely first. These are possibilities, not a diagnosis.
- Prefer simple checks: watering, sunlight, drainage, looking under leaves for insects, removing damaged leaves.
- Never give amounts or doses of any spray, pesticide or fertiliser.
- If the photo is not a plant, set "plant" to null and say so in next_step.
"""


def validate_image(data_url: str | None) -> str:
    if not data_url or not isinstance(data_url, str):
        raise FeatureError("Add a photo first.")
    if not data_url.startswith(ALLOWED_PREFIXES):
        raise FeatureError("The photo must be a JPEG, PNG or WebP image.")
    payload = data_url.split(",", 1)[1]
    if len(payload) * 3 // 4 > MAX_IMAGE_BYTES:
        raise FeatureError("That photo is too large. Try one under 6 MB.")
    try:
        base64.b64decode(payload, validate=True)
    except ValueError:
        raise FeatureError("The photo data is damaged. Try taking it again.") from None
    return data_url


def _strip_doses(text: str | None) -> tuple[str | None, bool]:
    if text and DOSE.search(text):
        return DOSE_REPLACEMENT, True
    return text, False


def check_plant(image: str, client: LLMClient | None, place: str, season: str, note: str | None = None) -> dict:
    image = validate_image(image)
    if client is None or not client.enabled:
        return {"ok": False, "note": "Plant check needs a vision model (Gemma 3 4b or larger), and the model is turned off."}
    user_note = f" The gardener says: \"{clean_str(note, 200)}\"" if clean_str(note, 200) else ""
    try:
        text, seconds = client.chat(
            PROMPT.format(place=place, season=season, note=user_note), image=image,
            max_tokens=500, json_mode=True, timeout=max(client.timeout, 120),
        )
    except LLMError as e:
        return {"ok": False, "note": f"Plant check unavailable: {e}. It needs Gemma 3 4b or larger, which can see images."}
    try:
        data = extract_json(text)
    except ValueError:
        return {"ok": False, "seconds": round(seconds, 2), "note": "The model's answer couldn't be read. Try another photo."}

    removed = False
    causes = []
    for c in (data.get("possible_causes") or [])[:3]:
        if not isinstance(c, dict):
            continue
        cause, check = clean_str(c.get("cause")), clean_str(c.get("check"))
        cause, r1 = _strip_doses(cause)
        check, r2 = _strip_doses(check)
        removed = removed or r1 or r2
        if cause:
            causes.append({"cause": cause, "check": check})
    next_step, r3 = _strip_doses(clean_str(data.get("next_step")))
    removed = removed or r3
    healthy = data.get("looks_healthy")
    return {
        "ok": True,
        "plant": clean_str(data.get("plant"), 80),
        "looks_healthy": healthy if isinstance(healthy, bool) else None,
        "possible_causes": causes,
        "next_step": next_step,
        "seconds": round(seconds, 2),
        "model": client.model,
        "note": "A dose amount was removed from the answer." if removed else None,
    }
