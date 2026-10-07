"""The planning engine.

Pure Python, standard library only, no network. Given today's date and a
place's seasons and rains, it works out which planting windows are open,
closing soon, or coming up. A language model never does this arithmetic: it
only gets to phrase the result (see brief.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from .crops import CROPS, EXTRAS
from .regions import Region

CLOSING_DAYS = 7          # an open window ending within this many days is "closing"
SOON_DAYS = 21            # a window starting within this many days is "coming up"
LATER_LIMIT = 8           # how many further-out windows to list
SEASON_OPEN_DAYS = 60     # a sowing season counts as "open" this long after it starts
RAINS_ALERT_DAYS = 14     # warn this many days before the rains usually arrive

ACTION_LABELS = {
    "nursery": "Start nursery",
    "transplant": "Transplant",
    "sow": "Sow",
    "plant": "Plant",
    "green_manure": "Sow green manure",
    "plant_sapling": "Plant saplings",
}

_MD = re.compile(r"^(\d{1,2})-(\d{1,2})$")


class PlanError(ValueError):
    """Bad input: an unparseable date, an impossible month-day, and so on."""


def parse_md(value: str) -> tuple[int, int]:
    """Parse "MM-DD" into (month, day). Feb 29 is accepted."""
    m = _MD.match((value or "").strip())
    if not m:
        raise PlanError(f"Date {value!r} should look like MM-DD, for example 06-27.")
    month, day = int(m.group(1)), int(m.group(2))
    try:
        date(2024, month, day)  # 2024 is a leap year, so 02-29 is valid
    except ValueError:
        raise PlanError(f"{value!r} is not a real calendar date.") from None
    return month, day


def md_in_year(md: tuple[int, int] | str, year: int) -> date:
    if isinstance(md, str):
        md = parse_md(md)
    month, day = md
    if (month, day) == (2, 29):
        try:
            return date(year, 2, 29)
        except ValueError:
            return date(year, 2, 28)
    return date(year, month, day)


def next_on_or_after(md: str, today: date) -> date:
    for year in (today.year, today.year + 1):
        d = md_in_year(md, year)
        if d >= today:
            return d
    raise AssertionError("unreachable")  # pragma: no cover


def prev_on_or_before(md: str, today: date) -> date:
    for year in (today.year, today.year - 1):
        d = md_in_year(md, year)
        if d <= today:
            return d
    raise AssertionError("unreachable")  # pragma: no cover


@dataclass(frozen=True)
class Window:
    crop: str
    local: str | None
    action: str
    season: str        # season name, or "Rains" for jobs tied to the rains
    start: date
    end: date
    tip: str

    @property
    def action_label(self) -> str:
        return ACTION_LABELS[self.action]


def _local(names: dict, lang: str | None) -> str | None:
    return names.get(lang) if lang else None


def all_windows(region: Region, today: date) -> list[Window]:
    """Every window for the years around `today`, so year boundaries just work."""
    out: list[Window] = []
    for year in (today.year - 1, today.year, today.year + 1):
        for season in region.seasons:
            anchor = md_in_year(season.start, year)
            for crop in CROPS:
                if crop["name"] in region.skip:
                    continue
                if crop.get("only") and region.country not in crop["only"]:
                    continue
                for action, (a, b) in crop["windows"].get(season.kind, {}).items():
                    out.append(Window(
                        crop=crop["name"], local=_local(crop["names"], region.lang), action=action,
                        season=season.name, start=anchor + timedelta(days=a),
                        end=anchor + timedelta(days=b), tip=crop["tip"],
                    ))
        rains_start = md_in_year(region.rains[0].start, year)
        for extra in EXTRAS:
            out.append(Window(
                crop=extra["name"], local=_local(extra["names"], region.lang), action=extra["kind"],
                season="Rains", start=rains_start + timedelta(days=extra["days"][0]),
                end=rains_start + timedelta(days=extra["days"][1]), tip=extra["tip"],
            ))
    return out


@dataclass(frozen=True)
class Item:
    crop: str
    local: str | None
    action: str
    action_label: str
    season: str
    start: date
    end: date
    tip: str
    status: str               # "open", "closing", "soon" or "later"
    days_left: int | None     # open windows: days until it closes (0 = last day)
    days_until: int | None    # upcoming windows: days until it opens


def _item(w: Window, today: date, status: str) -> Item:
    return Item(
        crop=w.crop, local=w.local, action=w.action, action_label=w.action_label, season=w.season,
        start=w.start, end=w.end, tip=w.tip, status=status,
        days_left=(w.end - today).days if w.start <= today <= w.end else None,
        days_until=(w.start - today).days if w.start > today else None,
    )


@dataclass(frozen=True)
class SeasonDate:
    name: str
    title: str
    kind: str
    start: date

    def days_from(self, today: date) -> int:
        return (self.start - today).days


@dataclass(frozen=True)
class RainsStatus:
    name: str
    raining: bool        # today is inside this rainy season
    event: str           # "starts" or "ends"
    date: date           # when that next happens
    days: int


@dataclass(frozen=True)
class Plan:
    today: date
    region: Region
    current_season: SeasonDate | None
    next_season: SeasonDate
    rains: RainsStatus          # the next change in the rains (start or end)
    in_rains: bool
    now: list[Item]             # open windows, closing-soonest first
    soon: list[Item]
    later: list[Item]
    alerts: list[str]


def _rains_status(region: Region, today: date) -> tuple[bool, RainsStatus]:
    """Is it raining season now, and what's the next change in the rains?"""
    statuses: list[RainsStatus] = []
    for band in region.rains:
        started = prev_on_or_before(band.start, today)
        ends = next_on_or_after(band.end, started)
        if today <= ends:
            statuses.append(RainsStatus(band.name, True, "ends", ends, (ends - today).days))
        else:
            nxt = next_on_or_after(band.start, today)
            statuses.append(RainsStatus(band.name, False, "starts", nxt, (nxt - today).days))
    in_rains = any(s.raining for s in statuses)
    if in_rains:
        status = min((s for s in statuses if s.raining), key=lambda s: s.days)
    else:
        status = min(statuses, key=lambda s: s.days)
    return in_rains, status


def _seasons(region: Region, today: date) -> tuple[SeasonDate | None, SeasonDate]:
    dates = sorted(
        (SeasonDate(s.name, s.title, s.kind, md_in_year(s.start, y))
         for y in (today.year - 1, today.year, today.year + 1) for s in region.seasons),
        key=lambda s: s.start,
    )
    past = [s for s in dates if s.start <= today]
    current = past[-1] if past and (today - past[-1].start).days <= SEASON_OPEN_DAYS else None
    upcoming = next(s for s in dates if s.start > today)
    return current, upcoming


def make_plan(today: date, region: Region) -> Plan:
    windows = all_windows(region, today)
    now: list[Item] = []
    soon: list[Item] = []
    later_candidates: list[Window] = []
    seen_now: set[tuple[str, str]] = set()

    for w in sorted(windows, key=lambda w: (w.start, w.crop)):
        key = (w.crop, w.action)
        if w.end < today:
            continue
        if w.start <= today:
            if key in seen_now:
                continue
            seen_now.add(key)
            status = "closing" if (w.end - today).days <= CLOSING_DAYS else "open"
            now.append(_item(w, today, status))
        elif (w.start - today).days <= SOON_DAYS:
            if key not in seen_now:
                soon.append(_item(w, today, "soon"))
        else:
            later_candidates.append(w)

    soon_keys = {(i.crop, i.action) for i in soon}
    later: list[Item] = []
    seen_later: set[tuple[str, str]] = set()
    for w in later_candidates:  # already sorted by start
        key = (w.crop, w.action)
        if key in seen_later or key in seen_now or key in soon_keys:
            continue
        seen_later.add(key)
        later.append(_item(w, today, "later"))
        if len(later) >= LATER_LIMIT:
            break

    now.sort(key=lambda i: (i.days_left, i.crop))
    soon.sort(key=lambda i: (i.days_until, i.crop))

    in_rains, rains = _rains_status(region, today)
    current, upcoming = _seasons(region, today)

    alerts: list[str] = []
    if not in_rains and rains.days <= RAINS_ALERT_DAYS:
        alerts.append(
            f"The {rains.name} usually starts in {rains.days} day{'s' if rains.days != 1 else ''}. "
            "Raise beds, clear drains and stake climbers before the heavy rain."
        )

    return Plan(
        today=today, region=region, current_season=current, next_season=upcoming,
        rains=rains, in_rains=in_rains, now=now, soon=soon, later=later, alerts=alerts,
    )


def crop_windows(region: Region, today: date, crops: set[str] | None = None, horizon_days: int = 366) -> list[Item]:
    """The current or next window for each (crop, action) at this place, within a year.

    Used by the features that answer "when can I plant X?" so they quote the
    engine's dates instead of a model's."""
    best: dict[tuple[str, str], Window] = {}
    for w in all_windows(region, today):
        if crops is not None and w.crop not in crops:
            continue
        if w.end < today or (w.start - today).days > horizon_days:
            continue
        key = (w.crop, w.action)
        if key not in best or w.start < best[key].start:
            best[key] = w
    items = []
    for w in best.values():
        status = ("closing" if (w.end - today).days <= CLOSING_DAYS else "open") if w.start <= today else (
            "soon" if (w.start - today).days <= SOON_DAYS else "later")
        items.append(_item(w, today, status))
    return sorted(items, key=lambda i: (i.start, i.crop, i.action))
