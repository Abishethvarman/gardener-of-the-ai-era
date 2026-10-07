"""Turn a Plan into a short "this week in the garden" brief.

Two writers share one contract:

* `templated_brief` is deterministic and needs nothing. It is the offline
  fallback, and also the training target for the fine-tuning pipeline.
* `model_brief` asks an open-weight model (Gemma by default) to phrase the same
  facts more naturally.

The model is never trusted. `check_faithful` rejects any brief that names a
crop or a date the engine did not produce, in English or by a local name
(bhindi, dherosh, bandakka...), and the caller then falls back to the template.
A small model can only ever make the wording nicer, never the calendar wrong.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date

from .crops import CROPS, EXTRAS, FACTCHECK_IGNORE
from .engine import Item, Plan
from .llm import LLMClient, LLMError

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MAX_ITEMS_PER_GROUP = 6
MAX_NAMED_IN_BRIEF = 5


def fmt_date(d: date) -> str:
    return f"{MONTHS[d.month - 1]} {d.day}"


def plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _item_fact(i: Item) -> dict:
    fact = {"crop": i.crop}
    if i.local:
        fact["local_name"] = i.local
    fact["action"] = i.action_label
    fact["window"] = f"{fmt_date(i.start)} to {fmt_date(i.end)}"
    if i.days_left is not None:
        fact["days_left"] = i.days_left
    if i.days_until is not None:
        fact["opens_in_days"] = i.days_until
    return fact


def facts(plan: Plan) -> dict:
    """The only information a model is allowed to use, as plain JSON."""
    r = plan.rains
    out: dict = {
        "place": plan.region.where,
        "today": fmt_date(plan.today),
        "rainy_season_now": plan.in_rains,
        "rains": {"name": r.name, "next": f"usually {r.event}", "date": fmt_date(r.date), "in_days": r.days},
    }
    if plan.current_season:
        out["sowing_season_now"] = {"name": plan.current_season.title, "opened": fmt_date(plan.current_season.start)}
    nxt = plan.next_season
    out["next_sowing_season"] = {"name": nxt.title, "opens": fmt_date(nxt.start), "in_days": nxt.days_from(plan.today)}
    out["plant_now"] = [_item_fact(i) for i in plan.now[:MAX_ITEMS_PER_GROUP]]
    if len(plan.now) > MAX_ITEMS_PER_GROUP:
        out["more_open_now"] = len(plan.now) - MAX_ITEMS_PER_GROUP
    out["coming_up"] = [_item_fact(i) for i in plan.soon[:MAX_ITEMS_PER_GROUP]]
    if plan.alerts:
        out["alerts"] = plan.alerts
    return out


# --------------------------------------------------------------------------
# Deterministic writer
# --------------------------------------------------------------------------

ACTION_NOUNS = {"nursery": "nursery", "transplant": "transplanting"}


def _label(fact: dict, item: Item) -> str:
    """'Peas', or 'cauliflower nursery' when the action isn't plain sowing."""
    noun = ACTION_NOUNS.get(item.action)
    return f"{fact['crop']} {noun}" if noun else fact["crop"]


def _with_local(fact: dict, item: Item) -> str:
    """'peas (matar)', or 'cauliflower nursery (phool gobhi)'."""
    name = _label(fact, item).lower()
    return f"{name} ({fact['local_name']})" if fact.get("local_name") else name


def _join(names: list[str]) -> str:
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def templated_brief(plan: Plan, variant: int = 0) -> str:
    """Plain-language brief built straight from the facts. `variant` (0-3)
    changes the phrasing so a fine-tuned model doesn't learn one rigid sentence."""
    f = facts(plan)
    v = variant % 4
    place = f["place"]
    parts: list[str] = []

    if "sowing_season_now" in f:
        s = f["sowing_season_now"]
        parts.append([
            f"{s['name']} is open in {place}.",
            f"It's {s['name']} time in {place}.",
            f"{_cap(place)} is in its {s['name']} window, which opened on {s['opened']}.",
            f"{s['name']} opened on {s['opened']}.",
        ][v])
    else:
        n = f["next_sowing_season"]
        d = plural(n["in_days"], "day")
        parts.append([
            f"{n['name']} opens in {d}, around {n['opens']}.",
            f"In {place}, the next window is {n['name']}, from about {n['opens']} ({d}).",
            f"{d} until {n['name']} begins ({n['opens']}).",
            f"{n['name']} starts around {n['opens']}, {d} from now.",
        ][v])

    r = f["rains"]
    if plan.in_rains or r["in_days"] <= 45:
        parts.append(f"The {r['name']} {r['next']} around {r['date']}, in {plural(r['in_days'], 'day')}.")

    now_items = plan.now[:MAX_ITEMS_PER_GROUP]
    now_facts = f["plant_now"]
    if now_facts:
        named = [_with_local(x, i) for x, i in zip(now_facts[:MAX_NAMED_IN_BRIEF], now_items)]
        extra = len(plan.now) - len(named)
        if extra > 0:
            named.append(f"{extra} more")
        lead = ["Open this week:", "Open right now:", "Ready to go now:", "Good to start this week:"][v]
        parts.append(f"{lead} {_join(named)}.")
        first, first_item = now_facts[0], now_items[0]
        if first["days_left"] <= 7:
            when = "today is the last day" if first["days_left"] == 0 else f"in {plural(first['days_left'], 'day')}"
            end = first["window"].split(" to ")[1]
            parts.append(f"{_cap(_label(first, first_item).lower())} closes soonest: {when} ({end}).")
    else:
        parts.append("Nothing is open for planting right now.")

    if f["coming_up"]:
        nxt, nxt_item = f["coming_up"][0], plan.soon[0]
        start = nxt["window"].split(" to ")[0]
        parts.append(
            f"Next up: {_label(nxt, nxt_item).lower()}, opening in {plural(nxt['opens_in_days'], 'day')} ({start})."
        )

    # Alerts are shown on their own (a box in the app, a line in the CLI), not repeated here.
    parts.append("Pick one bed or a few pots, take a trowel outside, and check the soil by hand.")
    return " ".join(parts)


# --------------------------------------------------------------------------
# Model writer + guardrail
# --------------------------------------------------------------------------

PROMPT = """You write the weekly note for a home gardener's monsoon sowing calendar in South Asia.

Rules:
- Use ONLY the facts in the JSON below. Do not add crops, dates, or numbers that are not in it.
- Write 3 to 5 short sentences of plain prose. No lists, no headings, no emoji.
- Say which sowing season is open (or opens next), name what can be started now (you may add the local names given), and say which window closes first.
- Finish with one sentence nudging them to go outside and do it.

FACTS:
{facts}
"""


def build_prompt(plan: Plan) -> str:
    return PROMPT.format(facts=json.dumps(facts(plan), indent=2, ensure_ascii=False))


_DATE_RE = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2})\b")


def _names_for(entry: dict) -> list[str]:
    names = [entry["name"], *entry.get("also", []), *entry.get("names", {}).values()]
    return sorted({n.lower() for n in names if n.lower() not in FACTCHECK_IGNORE})


def _build_patterns() -> list[tuple[re.Pattern, str]]:
    pairs = [(alias, entry["name"]) for entry in CROPS + EXTRAS for alias in _names_for(entry)]
    # Longest first, so "water spinach" is matched (and masked) before "spinach".
    pairs.sort(key=lambda p: -len(p[0]))
    return [(re.compile(rf"\b{re.escape(alias)}(?:s|es)?\b"), crop) for alias, crop in pairs]


_CROP_PATTERNS = _build_patterns()


def mentioned_crops(text: str) -> set[str]:
    """Every crop named in `text`, by English or local name."""
    lowered = text.lower().replace("’", "'")
    found: set[str] = set()
    for pattern, crop in _CROP_PATTERNS:
        def mask(m: re.Match, crop=crop) -> str:
            found.add(crop)
            return " " * len(m.group(0))
        lowered = pattern.sub(mask, lowered)
    return found


def mentioned_dates(text: str) -> set[str]:
    return {f"{m} {int(d)}" for m, d in _DATE_RE.findall(text)}


def check_faithful(text: str, plan: Plan) -> tuple[bool, list[str]]:
    """Return (ok, problems). Fails on any crop or date not in the engine's plan.

    Crops: anything open now or coming up is allowed, even past the six the
    model was shown, because naming a crop that really is open isn't wrong.
    Dates: only dates that appear in the facts the model was given."""
    f = facts(plan)
    allowed_crops = {i.crop for i in plan.now + plan.soon}
    allowed_dates = mentioned_dates(json.dumps(f))
    problems: list[str] = []
    for crop in sorted(mentioned_crops(text) - allowed_crops):
        problems.append(f"mentions {crop}, which the plan does not include")
    for d in sorted(mentioned_dates(text) - allowed_dates):
        problems.append(f"mentions {d}, which is not a date in the plan")
    return (not problems, problems)


@dataclass
class Brief:
    text: str
    source: str              # "model" or "template"
    model: str | None = None
    seconds: float | None = None
    note: str | None = None  # why we fell back, when we did


def make_brief(plan: Plan, client: LLMClient | None) -> Brief:
    """Ask the model for a brief; fall back to the template on any problem."""
    if client is None or not client.enabled:
        return Brief(templated_brief(plan), "template", note="The model is turned off.")
    try:
        text, seconds = client.complete(build_prompt(plan))
    except LLMError as e:
        return Brief(templated_brief(plan), "template", note=f"Offline mode: {e}.")
    ok, problems = check_faithful(text, plan)
    if not ok:
        return Brief(
            templated_brief(plan), "template", model=client.model, seconds=seconds,
            note="The model's draft failed the fact check (" + "; ".join(problems[:2]) + ").",
        )
    return Brief(text, "model", model=client.model, seconds=seconds)
