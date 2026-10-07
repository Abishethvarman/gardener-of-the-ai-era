"""Optional features. Each lives in its own module, has its own API route, and
can be switched off without touching the sowing calendar.

    GARDENER_FEATURES=all                      (default) everything on
    GARDENER_FEATURES=language,water,diary     only these
    GARDENER_FEATURES=none                     just the calendar

    language  the weekly note in your language          (needs the model)
    water     water-today tip from a free forecast       (needs internet)
    photo     plant photo check                          (needs a vision model)
    ask       ask a question about your calendar         (needs the model)
    packet    read a seed packet photo                   (needs a vision model)
    diary     my garden: harvest dates and resow nudges  (no model)
    balcony   crops that fit your pots and sunlight      (no model)
"""

from __future__ import annotations

import os
import re

ALL = ("language", "water", "photo", "ask", "packet", "diary", "balcony")


class FeatureError(ValueError):
    """Bad input to a feature (shown to the user as a 400)."""


def enabled(env: str | None = None) -> set[str]:
    raw = (env if env is not None else os.environ.get("GARDENER_FEATURES", "all")).strip().lower()
    if raw in ("", "all"):
        return set(ALL)
    if raw == "none":
        return set()
    return {f.strip() for f in raw.split(",") if f.strip() in ALL}


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (models like to wrap it in ```json fences)."""
    import json

    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in the reply")
    data = json.loads(m.group(0))
    if not isinstance(data, dict):
        raise ValueError("reply JSON is not an object")
    return data


def clean_str(value, limit: int = 300) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("null", "none", "unknown", "n/a"):
        return None
    return s[:limit]
