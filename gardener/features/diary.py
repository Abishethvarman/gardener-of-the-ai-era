"""My garden: what you planted, when it should be ready, and when to sow again.

The diary itself is stored on the gardener's own device (the browser's local
storage); the server only does the date arithmetic. No model is involved.
"""

from __future__ import annotations

from datetime import date, timedelta

from ..brief import fmt_date
from ..crops import CROPS
from ..engine import crop_windows
from ..regions import Region
from . import FeatureError, clean_str

DTM = {c["name"]: c["days_to_harvest"] for c in CROPS}
QUICK_DAYS = 50          # crops this fast are worth sowing again in batches
RESOW_AFTER_DAYS = 14
STALE_AFTER_DAYS = 45    # past this, "should be done by now"
MAX_ENTRIES = 200


def harvest_plan(entries: list, today: date, region: Region | None = None) -> dict:
    if not isinstance(entries, list):
        raise FeatureError("The diary should be a list of plantings.")
    if len(entries) > MAX_ENTRIES:
        raise FeatureError(f"The diary is limited to {MAX_ENTRIES} plantings.")
    out = []
    for e in entries:
        if not isinstance(e, dict):
            raise FeatureError("Each planting needs a crop and a date.")
        crop = clean_str(e.get("crop"), 40)
        if crop not in DTM:
            raise FeatureError(f"Unknown crop {crop!r}.")
        try:
            planted = date.fromisoformat(str(e.get("planted")))
        except ValueError:
            raise FeatureError(f"The planting date for {crop} should look like YYYY-MM-DD.") from None
        if planted > today:
            raise FeatureError(f"The planting date for {crop} is in the future.")
        ready = planted + timedelta(days=DTM[crop])
        days = (ready - today).days
        if days > 0:
            status, text = "growing", f"Ready in about {days} day{'s' if days != 1 else ''}, around {fmt_date(ready)}."
        elif days >= -STALE_AFTER_DAYS:
            status, text = "ready", f"Should be ready now (from about {fmt_date(ready)}). Have a look."
        else:
            status, text = "old", "Probably finished. Clear the bed or pot for the next crop."
        resow = False
        if region and DTM[crop] <= QUICK_DAYS and (today - planted).days >= RESOW_AFTER_DAYS:
            resow = any(i.days_left is not None for i in crop_windows(region, today, {crop}))
        out.append({
            "id": clean_str(e.get("id"), 40), "crop": crop, "note": clean_str(e.get("note"), 200),
            "planted": planted.isoformat(), "ready": ready.isoformat(), "ready_label": fmt_date(ready),
            "days_to_ready": days, "status": status, "text": text,
            "resow": resow, "resow_text": f"Sow another batch of {crop.lower()} now for a steady supply." if resow else None,
        })
    out.sort(key=lambda x: x["days_to_ready"])
    ready_n = sum(1 for x in out if x["status"] == "ready")
    growing = [x for x in out if x["status"] == "growing"]
    parts = []
    if ready_n:
        parts.append(f"{ready_n} planting{'s' if ready_n != 1 else ''} should be ready now.")
    if growing:
        parts.append(f"Next up: {growing[0]['crop'].lower()} around {growing[0]['ready_label']}.")
    if not out:
        parts.append("Nothing planted yet. Pick something from This week and add it here.")
    return {"entries": out, "summary": " ".join(parts)}
