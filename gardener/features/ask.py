"""Ask a question about your calendar.

The model answers in a few sentences, using only a calendar the engine built
for this place and day. Two things keep it honest:

* any date in the answer must appear in that calendar;
* any crop it names must be in the calendar or in the question.

Whatever the model says, if the question names crops, the engine's own windows
for those crops are returned alongside, so the gardener always gets the real
dates even when the model fails or is turned off.
"""

from __future__ import annotations

from datetime import date

from ..brief import fmt_date, mentioned_crops, mentioned_dates
from ..engine import Item, Plan, crop_windows
from ..llm import LLMClient, LLMError
from ..service import item_json
from . import FeatureError

MAX_QUESTION = 400

PROMPT = """You answer a home gardener's question using ONLY the sowing calendar below.

Rules:
- At most 4 short sentences of plain prose.
- Only use dates that appear in the calendar. Never invent dates or numbers.
- If the calendar doesn't answer the question, say you don't know and suggest asking a local nursery.

CALENDAR for {place}, today {today}:
{season}
{lines}

QUESTION: {question}
"""


def _line(i: Item) -> str:
    name = f"{i.crop} ({i.local})" if i.local else i.crop
    when = (f"open now, closes {fmt_date(i.end)}" if i.days_left is not None
            else f"opens {fmt_date(i.start)}, closes {fmt_date(i.end)}")
    return f"- {name}: {i.action_label.lower()}, {when}"


def season_line(plan: Plan) -> str:
    cur, nxt = plan.current_season, plan.next_season
    parts = [f"{cur.title} is open (since {fmt_date(cur.start)})." if cur else f"{nxt.title} opens {fmt_date(nxt.start)}."]
    r = plan.rains
    parts.append(f"The {r.name} usually {r.event} around {fmt_date(r.date)}.")
    return " ".join(parts)


def ask(question: str, plan: Plan, today: date, client: LLMClient | None) -> dict:
    question = (question or "").strip()
    if not question:
        raise FeatureError("Type a question first.")
    if len(question) > MAX_QUESTION:
        raise FeatureError(f"Keep the question under {MAX_QUESTION} characters.")

    asked = mentioned_crops(question)
    if asked:
        items = crop_windows(plan.region, today, asked)
    else:
        items = plan.now + plan.soon + plan.later
    lines = "\n".join(_line(i) for i in items) or "- (no planting windows for these crops at this place)"
    season = season_line(plan)
    calendar_text = season + "\n" + lines + f"\nToday {fmt_date(today)}"

    result = {
        "question": question,
        "crops": sorted(asked),
        "windows": [item_json(i) for i in crop_windows(plan.region, today, asked)] if asked else [],
        "missing": sorted(c for c in asked if not any(i.crop == c for i in items)),
        "answer": None, "source": None, "seconds": None, "note": None,
    }
    if client is None or not client.enabled:
        result["note"] = "The model is off, so here are the calendar's dates only."
        return result
    try:
        text, seconds = client.chat(PROMPT.format(place=plan.region.where, today=fmt_date(today), season=season,
                                                  lines=lines, question=question), max_tokens=250)
    except LLMError as e:
        result["note"] = f"No answer from the model ({e}). Here are the calendar's dates."
        return result
    result["seconds"] = round(seconds, 2)

    problems = []
    bad_dates = mentioned_dates(text) - mentioned_dates(calendar_text)
    if bad_dates:
        problems.append("it used dates not in the calendar: " + ", ".join(sorted(bad_dates)))
    allowed = {i.crop for i in items} | asked
    bad_crops = mentioned_crops(text) - allowed
    if bad_crops:
        problems.append("it named crops not in the calendar: " + ", ".join(sorted(bad_crops)))
    if problems:
        result["note"] = "The model's answer failed the check (" + "; ".join(problems) + "). Here are the calendar's dates."
        return result
    result.update(answer=text.strip(), source="model", model=client.model)
    return result
