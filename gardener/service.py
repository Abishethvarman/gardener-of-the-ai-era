"""Glue between the engine, the brief writer and the transports (HTTP and CLI)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from .brief import Brief, fmt_date, make_brief
from .engine import Item, Plan, PlanError, make_plan, parse_md
from .llm import LLMClient
from .regions import REGIONS, Region, custom_region


def resolve_region(region: str | None = None, onset: str | None = None, withdrawal: str | None = None,
                   cool: bool = True) -> Region:
    """A preset by key, or a custom place from monsoon onset and withdrawal dates."""
    if onset or withdrawal:
        if not (onset and withdrawal):
            raise PlanError("Enter both dates: when the monsoon usually arrives and when it usually ends (MM-DD).")
        if parse_md(onset) == parse_md(withdrawal):
            raise PlanError("The monsoon can't arrive and end on the same day.")
        return custom_region(onset.strip(), withdrawal.strip(), cool)
    if region:
        key = region.lower()
        if key not in REGIONS:
            raise PlanError(
                f"Unknown place {region!r}. Pick one of: {', '.join(REGIONS)}, "
                "or enter your own monsoon dates."
            )
        return REGIONS[key]
    raise PlanError("Choose a place, or enter when your monsoon usually arrives and ends (MM-DD).")


def region_from(params: dict) -> Region:
    """A Region from request parameters: region=..., or onset/withdrawal/cool, plus optional lat/lon."""
    cool = str(params.get("cool", "1")).lower() not in ("0", "false", "no", "off")
    region = resolve_region(params.get("region"), params.get("onset"), params.get("withdrawal"), cool)
    if params.get("lat") not in (None, "") and params.get("lon") not in (None, ""):
        try:
            lat, lon = float(params["lat"]), float(params["lon"])
        except (TypeError, ValueError):
            raise PlanError("Location should be two numbers: latitude and longitude.") from None
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise PlanError("That location is off the map.")
        region = replace(region, lat=lat, lon=lon)
    return region


def plan_for(today: date, region: str | None = None, onset: str | None = None,
             withdrawal: str | None = None, cool: bool = True) -> Plan:
    return make_plan(today, resolve_region(region, onset, withdrawal, cool))


def parse_day(value: str | None) -> date:
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise PlanError(f"Date {value!r} should look like YYYY-MM-DD.") from None


def item_json(i: Item) -> dict:
    return {
        "crop": i.crop, "local": i.local, "action": i.action, "action_label": i.action_label,
        "season": i.season, "start": i.start.isoformat(), "end": i.end.isoformat(),
        "start_label": fmt_date(i.start), "end_label": fmt_date(i.end),
        "status": i.status, "days_left": i.days_left, "days_until": i.days_until, "tip": i.tip,
    }


def plan_json(plan: Plan, brief: Brief) -> dict:
    r = plan.region
    cur = plan.current_season
    return {
        "region": {"key": r.key, "label": r.label, "country": r.country, "source": r.source},
        "today": plan.today.isoformat(),
        "seasons": [{"name": s.name, "title": s.title, "kind": s.kind, "start": s.start} for s in r.seasons],
        "rains_bands": [{"start": b.start, "end": b.end, "name": b.name} for b in r.rains],
        "in_rains": plan.in_rains,
        "rains": {
            "name": plan.rains.name, "event": plan.rains.event,
            "date": plan.rains.date.isoformat(), "date_label": fmt_date(plan.rains.date), "days": plan.rains.days,
        },
        "current_season": None if cur is None else {
            "name": cur.name, "title": cur.title, "start": cur.start.isoformat(),
            "start_label": fmt_date(cur.start), "days_since": (plan.today - cur.start).days,
        },
        "next_season": {
            "name": plan.next_season.name, "title": plan.next_season.title,
            "start": plan.next_season.start.isoformat(), "start_label": fmt_date(plan.next_season.start),
            "days_until": plan.next_season.days_from(plan.today),
        },
        "alerts": plan.alerts,
        "now": [item_json(i) for i in plan.now],
        "soon": [item_json(i) for i in plan.soon],
        "later": [item_json(i) for i in plan.later],
        "brief": {
            "text": brief.text, "source": brief.source, "model": brief.model,
            "seconds": round(brief.seconds, 2) if brief.seconds is not None else None,
            "note": brief.note,
        },
    }


class Planner:
    """Builds plans and caches model briefs, since a model call is the slow part."""

    def __init__(self, client: LLMClient | None = None, cache_size: int = 256):
        self.client = client if client is not None else LLMClient.from_env()
        self._cache: dict[tuple, Brief] = {}
        self._cache_size = cache_size

    def plan(self, today: date, region: Region, use_model: bool = True, lang: str | None = None) -> dict:
        plan = make_plan(today, region)
        key = (today, region, use_model, self.client.model)
        brief = self._cache.get(key)
        if brief is None:
            brief = make_brief(plan, self.client if use_model else None)
            if brief.source == "model" or not use_model:
                if len(self._cache) >= self._cache_size:
                    self._cache.pop(next(iter(self._cache)))
                self._cache[key] = brief
        data = plan_json(plan, brief)
        if lang:
            from .features.language import translate
            tkey = ("translate", brief.text, lang, self.client.model)
            tr = self._cache.get(tkey)
            if tr is None:
                tr = translate(brief.text, lang, self.client if use_model else None, region.where)
                if tr["ok"]:
                    self._cache[tkey] = tr
            data["translation"] = tr
        return data
