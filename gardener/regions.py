"""Seasons and rains for each preset place.

Most of South Asia has one main monsoon, so a place is described by two dates
people already know, when the monsoon usually arrives and when it usually
withdraws, plus whether winters are cool enough for Rabi crops. The three sowing
seasons are derived from those dates (see `monsoon_region`).

Places that don't follow that pattern (Sri Lanka with Yala and Maha, Chennai with
the northeast monsoon) list their seasons explicitly.

Sources for the dates (rounded; your own street can differ):
  India      IMD new normal onset and withdrawal dates (2020 press release).
  Pakistan   PMD: normal monsoon onset 1 July; season July to September.
             Withdrawal here is the end of September, the end of that season.
  Bangladesh BMD journal (1992-2021 means): onset 2 June (south-east) to
             15 June (north-west), withdrawal 30 September (north-west) to
             17 October (south-east). Dhaka is set between those, so it is an
             estimate, not a published Dhaka normal.
  Sri Lanka  Department of Agriculture planting times (e.g. okra: Yala early
             April to early May, Maha early September to early October); FAO
             country profile for the monsoon months.
  Chennai    TNAU (Adi pattam June to August, Thai pattam around February);
             IMD Chennai: normal northeast monsoon onset 20 October, and IMD's
             northeast monsoon season runs October to December.
  Thailand   Thai Meteorological Department's national seasons: hot mid-February
             to mid-May, rainy mid-May to mid-October, cool mid-October to
             mid-February (boundaries can shift by one to two weeks).
  Philippines PAGASA: the rainy season typically runs June to November.
  Vietnam    Southern rainy season May to November, dry December to April
             (month ranges, so the exact days are approximate).

Not included, because no published normal was found: Yangon, Jakarta, Hanoi,
Phnom Penh. Use custom dates there; rains that cross New Year are supported.
Equatorial places that are wet all year (Singapore, Kuala Lumpur) don't fit a
two-date model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

# Summer (dry-season) sowing is set this many days before the monsoon arrives.
# With a late-June monsoon that lands in late February, matching published
# February-March sowing for summer vegetables.
SUMMER_LEAD_DAYS = 126


@dataclass(frozen=True)
class Season:
    kind: str           # "wet", "cool" or "dry"
    name: str           # "Rabi", "Yala", "Adi pattam"...
    start: str          # "MM-DD": the day sowing for this season usually begins
    label: str = ""     # how a headline says it: "Rabi sowing", "Adi pattam"

    @property
    def title(self) -> str:
        return self.label or f"{self.name} sowing"


@dataclass(frozen=True)
class Rains:
    start: str          # "MM-DD"
    end: str            # "MM-DD"
    name: str = "monsoon"


@dataclass(frozen=True)
class Region:
    key: str
    label: str
    country: str
    lang: str | None
    seasons: tuple[Season, ...]
    rains: tuple[Rains, ...]       # the main rains first
    source: str = ""
    skip: tuple[str, ...] = ()     # crops that don't suit this place's calendar
    onset: str | None = None       # set for monsoon-derived places (pre-fills custom dates)
    withdrawal: str | None = None
    cool: bool = True
    place: str = ""                # how a sentence names it, when that differs from the label
    lat: float | None = None       # city centre, for the watering forecast
    lon: float | None = None

    @property
    def where(self) -> str:
        return self.place or self.label


def shift_md(md: str, days: int) -> str:
    """Move a "MM-DD" by a number of days, in a common (non-leap) year."""
    month, day = (int(x) for x in md.split("-"))
    if (month, day) == (2, 29):
        day = 28
    d = date(2025, month, day) + timedelta(days=days)
    return f"{d.month:02d}-{d.day:02d}"


NAMES = {
    "India": ("Zaid", "Kharif", "Rabi"),
    "Pakistan": ("Summer vegetable", "Monsoon", "Winter vegetable"),
    "Bangladesh": ("Kharif-1", "Kharif-2", "Rabi"),
    "custom": ("Summer", "Monsoon", "Winter"),
}


def monsoon_region(key: str, label: str, country: str, lang: str | None, onset: str, withdrawal: str,
                   cool: bool = True, names: tuple[str, str, str] | None = None,
                   source: str = "", skip: tuple[str, ...] = ()) -> Region:
    """Build a place with one main monsoon from its onset and withdrawal dates.

    dry   summer sowing, SUMMER_LEAD_DAYS before the monsoon (needs watering)
    wet   monsoon sowing, from onset
    cool  winter (Rabi) sowing, from withdrawal, if winters are cool;
          otherwise a second warm, dry sowing after the rains
    """
    dry_name, wet_name, cool_name = names or NAMES["custom"]
    seasons = [
        Season("dry", dry_name, shift_md(onset, -SUMMER_LEAD_DAYS)),
        Season("wet", wet_name, onset),
        Season("cool", cool_name, withdrawal) if cool else Season("dry", "Post-monsoon", withdrawal),
    ]
    return Region(
        key=key, label=label, country=country, lang=lang,
        seasons=tuple(seasons), rains=(Rains(onset, withdrawal, "monsoon"),),
        source=source, skip=skip, onset=onset, withdrawal=withdrawal, cool=cool,
    )


IMD = "IMD normal monsoon onset and withdrawal (2020)"

_PRESETS: list[Region] = [
    # India
    monsoon_region("delhi", "New Delhi", "India", "hi", "06-27", "09-25", names=NAMES["India"], source=IMD),
    monsoon_region("lucknow", "Lucknow", "India", "hi", "06-23", "10-03", names=NAMES["India"], source=IMD),
    monsoon_region("mumbai", "Mumbai", "India", "hi", "06-11", "10-08", names=NAMES["India"], source=IMD),
    monsoon_region("pune", "Pune", "India", "hi", "06-10", "10-11", names=NAMES["India"], source=IMD),
    monsoon_region("hyderabad", "Hyderabad", "India", "te", "06-08", "10-14", names=NAMES["India"], source=IMD),
    monsoon_region("kolkata", "Kolkata", "India", "bn", "06-11", "10-12", names=NAMES["India"], source=IMD),
    Region(
        key="chennai", label="Chennai", country="India", lang="ta",
        seasons=(
            Season("dry", "Thai pattam", "01-15", label="Thai pattam"),
            Season("wet", "Adi pattam", "07-01", label="Adi pattam"),
        ),
        rains=(Rains("10-20", "12-31", "northeast monsoon"),),
        source="TNAU sowing seasons; IMD Chennai northeast monsoon normal onset",
        skip=("Ginger", "Turmeric"),
    ),
    # Pakistan
    monsoon_region("lahore", "Lahore", "Pakistan", "hi", "07-01", "09-30", names=NAMES["Pakistan"],
                   source="PMD normal onset 1 July; Punjab agriculture department sowing advice"),
    # Bangladesh
    monsoon_region("dhaka", "Dhaka", "Bangladesh", "bn", "06-08", "10-08", names=NAMES["Bangladesh"],
                   source="Estimated from BMD 1992-2021 onset and withdrawal ranges"),
    # Sri Lanka
    Region(
        key="colombo", label="Colombo (wet zone)", country="Sri Lanka", lang="si",
        seasons=(Season("wet", "Yala", "04-01"), Season("wet", "Maha", "09-01")),
        rains=(Rains("05-25", "09-25", "southwest monsoon"), Rains("10-01", "11-30", "inter-monsoon season")),
        source="Sri Lanka Department of Agriculture planting times; FAO",
        skip=("Ginger", "Turmeric"),
    ),
    Region(
        key="anuradhapura", label="Anuradhapura (dry zone)", country="Sri Lanka", lang="si",
        seasons=(Season("wet", "Yala", "04-01"), Season("wet", "Maha", "09-01")),
        rains=(Rains("10-01", "01-31", "Maha rainy season"),),
        source="Sri Lanka Department of Agriculture planting times; FAO",
        skip=("Ginger", "Turmeric"),
    ),
    # Southeast Asia: places with one clear wet season.
    Region(
        key="bangkok", label="Bangkok", country="Thailand", lang="th",
        seasons=(
            Season("dry", "Hot season", "02-15"),
            Season("wet", "Rainy season", "05-15"),
            Season("dry", "Cool season", "10-15"),
        ),
        rains=(Rains("05-15", "10-15", "rainy season"),),
        source="Thai Meteorological Department seasons (national)",
    ),
    Region(
        key="chiangmai", label="Chiang Mai", country="Thailand", lang="th",
        seasons=(
            Season("dry", "Hot season", "02-15"),
            Season("wet", "Rainy season", "05-15"),
            Season("cool", "Cool season", "10-15"),
        ),
        rains=(Rains("05-15", "10-15", "rainy season"),),
        source="Thai Meteorological Department seasons (national); northern winters are cool",
    ),
    Region(
        key="manila", label="Manila", country="Philippines", lang="tl",
        seasons=(Season("wet", "Wet season", "06-01"), Season("dry", "Dry season", "12-01")),
        rains=(Rains("06-01", "11-30", "rainy season"),),
        source="PAGASA: rainy season typically June to November",
    ),
    Region(
        key="hochiminh", label="Ho Chi Minh City", country="Vietnam", lang="vi",
        seasons=(Season("wet", "Rainy season", "05-01"), Season("dry", "Dry season", "12-01")),
        rains=(Rains("05-01", "11-30", "rainy season"),),
        source="Southern Vietnam rainy season, May to November",
    ),
]

COORDS = {'delhi': (28.61, 77.21), 'lucknow': (26.85, 80.95), 'mumbai': (19.08, 72.88), 'pune': (18.52, 73.86), 'hyderabad': (17.39, 78.49), 'kolkata': (22.57, 88.36), 'chennai': (13.08, 80.27), 'lahore': (31.55, 74.34), 'dhaka': (23.81, 90.41), 'colombo': (6.93, 79.86), 'anuradhapura': (8.31, 80.4), 'bangkok': (13.76, 100.5), 'chiangmai': (18.79, 98.99), 'manila': (14.6, 120.98), 'hochiminh': (10.82, 106.63)}
_PRESETS = [replace(r, lat=COORDS[r.key][0], lon=COORDS[r.key][1]) for r in _PRESETS]

REGIONS: dict[str, Region] = {r.key: r for r in _PRESETS}
DEFAULT_REGION = "delhi"


def custom_region(onset: str, withdrawal: str, cool: bool = True) -> Region:
    r = monsoon_region("custom", "Your monsoon dates", "", None, onset, withdrawal, cool=cool, names=NAMES["custom"])
    return replace(r, place="your garden")


def list_regions() -> list[dict]:
    return [
        {
            "key": r.key, "label": r.label, "country": r.country,
            "onset": r.onset, "withdrawal": r.withdrawal, "cool": r.cool,
            "source": r.source, "lat": r.lat, "lon": r.lon,
        }
        for r in _PRESETS
    ]
