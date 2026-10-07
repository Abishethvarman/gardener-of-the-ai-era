"""Read a seed packet photo and say whether it's time to sow it here.

The vision model only reads what's printed (crop, variety, sowing months). The
decision, "sow now" or "opens in 12 days", comes from the engine's calendar for
this place, not from the packet or the model. The packet's own sowing months
are shown as "printed on the packet", because a packet sold nationwide can't
know your local seasons.
"""

from __future__ import annotations

from datetime import date

from ..brief import fmt_date, mentioned_crops
from ..crops import CROPS, EXTRAS
from ..engine import crop_windows
from ..llm import LLMClient, LLMError
from ..regions import Region
from ..service import item_json
from . import clean_str, extract_json
from .photo import validate_image

PROMPT = """This is a photo of a seed packet. Read only what is printed on it.

Reply with JSON only:
{"crop": "the crop in English, e.g. Tomato, Okra, Spinach",
 "variety": "variety name as printed, or null",
 "local_name": "the crop name in any other language on the packet, or null",
 "sowing_time": "sowing months or season as printed, or null",
 "days_to_harvest": "days to harvest as printed, or null"}

Use null for anything that isn't printed. Don't guess.
"""

_ORDER = [c["name"] for c in CROPS + EXTRAS]


def verdict(crop: str, region: Region, today: date) -> tuple[str, list]:
    items = crop_windows(region, today, {crop})
    if not items:
        return f"{crop} isn't in the calendar for {region.where}.", []
    first = items[0]
    if first.days_left is not None:
        msg = f"Yes: {crop.lower()} can go in now ({first.action_label.lower()} until {fmt_date(first.end)})."
    else:
        msg = (f"Not yet: the next window for {crop.lower()} ({first.action_label.lower()}) opens in "
               f"{first.days_until} day{'s' if first.days_until != 1 else ''}, on {fmt_date(first.start)}.")
    return msg, [item_json(i) for i in items]


def read_packet(image: str, region: Region, today: date, client: LLMClient | None) -> dict:
    image = validate_image(image)
    if client is None or not client.enabled:
        return {"ok": False, "note": "Reading packets needs a vision model (Gemma 3 4b or larger), and the model is turned off."}
    try:
        text, seconds = client.chat(PROMPT, image=image, max_tokens=250, json_mode=True,
                                    timeout=max(client.timeout, 120))
    except LLMError as e:
        return {"ok": False, "note": f"Packet reading unavailable: {e}."}
    try:
        data = extract_json(text)
    except ValueError:
        return {"ok": False, "seconds": round(seconds, 2), "note": "The model's answer couldn't be read. Try a clearer photo."}

    packet = {k: clean_str(data.get(k), 120) for k in ("crop", "variety", "local_name", "sowing_time", "days_to_harvest")}
    found = mentioned_crops(" ".join(v for v in (packet["crop"], packet["local_name"], packet["variety"]) if v))
    crop = min(found, key=_ORDER.index) if found else None
    result = {"ok": True, "packet": packet, "crop": crop, "seconds": round(seconds, 2), "model": client.model}
    if crop is None:
        result.update(verdict="This crop isn't in the calendar yet, so check the packet and your local nursery.", windows=[])
    else:
        result["verdict"], result["windows"] = verdict(crop, region, today)
    return result
