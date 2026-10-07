"""Balcony and terrace planner: what fits your pots and your sunlight this week.

Plain rules over the crop table, no model:
* crops that need open ground (pumpkin, melons) are left out;
* "full sun" crops need 6 or more hours of direct sun, "part sun" crops 3 or more;
* open windows come first (closing soonest), then the ones opening soon.
"""

from __future__ import annotations

from ..crops import CROPS
from ..engine import Plan
from ..service import item_json
from . import FeatureError

INFO = {c["name"]: c for c in CROPS}
POT_TEXT = {"small": "a small pot, 15 cm deep", "medium": "a medium pot, 25 to 30 cm deep", "large": "a large pot or grow bag, 40 cm or deeper"}
SUN_NEED = {"full": 6, "part": 3}


def suggest(plan: Plan, sun_hours: float, pots: int) -> dict:
    if not 0 <= sun_hours <= 14:
        raise FeatureError("Sun hours should be between 0 and 14.")
    if not 1 <= pots <= 30:
        raise FeatureError("Pots should be between 1 and 30.")
    picks, skipped, seen = [], [], set()
    for item in plan.now + plan.soon:
        info = INFO.get(item.crop)
        if info is None or item.crop in seen:
            continue                      # green manure, saplings, or already listed
        seen.add(item.crop)
        if info["pot"] is None:
            skipped.append({"crop": item.crop, "reason": "needs open ground"})
            continue
        if sun_hours < SUN_NEED[info["sun"]]:
            skipped.append({"crop": item.crop, "reason": f"needs {SUN_NEED[info['sun']]}+ hours of sun"})
            continue
        sun = "Happy with 3 to 6 hours of sun." if info["sun"] == "part" else "Needs 6 or more hours of sun."
        picks.append({**item_json(item), "pot": info["pot"], "sun": info["sun"],
                      "why": f"Grows in {POT_TEXT[info['pot']]}. {sun}"})
    note = None
    if sun_hours < 3:
        note = "Under 3 hours of direct sun is too shady for the vegetables in this calendar."
    elif not picks:
        note = "Nothing in this week's calendar fits your pots and sun. Check Coming up next week."
    return {"sun_hours": sun_hours, "pots": pots, "suggestions": picks[:pots], "more": max(0, len(picks) - pots),
            "skipped": skipped, "note": note}
