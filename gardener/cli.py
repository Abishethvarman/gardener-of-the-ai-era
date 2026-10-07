"""Command line: print a garden card, list places, or start the server.

    python -m gardener card --region delhi
    python -m gardener card --onset 06-10 --withdrawal 10-05 --no-model
    python -m gardener card --region colombo --date 2027-04-05
    python -m gardener regions
    python -m gardener serve --port 8000
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from .engine import PlanError
from .regions import REGIONS
from .service import Planner, parse_day, resolve_region


def _fmt(item: dict) -> str:
    if item["days_left"] is not None:
        when = "last day" if item["days_left"] == 0 else f"{item['days_left']}d left"
    else:
        when = f"opens in {item['days_until']}d"
    crop = item["crop"] + (f" ({item['local']})" if item["local"] else "")
    return f"  {crop:<28} {item['action_label']:<17} {item['start_label']} - {item['end_label']}  ({when})"


def render_card(data: dict) -> str:
    cur, nxt = data["current_season"], data["next_season"]
    head = f"{cur['title']} is open" if cur else f"{nxt['title']} opens in {nxt['days_until']}d ({nxt['start_label']})"
    lines = [f"GARDENER  {data['region']['label']}  {data['today']}", head, ""]
    lines += textwrap.wrap(data["brief"]["text"], 78)
    lines.append("")
    for alert in data["alerts"]:
        lines += textwrap.wrap("! " + alert, 78, subsequent_indent="  ")
        lines.append("")
    for title, key in (("Plant now", "now"), ("Coming up", "soon"), ("Later", "later")):
        if data[key]:
            lines.append(title)
            lines += [_fmt(i) for i in data[key]]
            lines.append("")
    b = data["brief"]
    src = f"{b['model']} (open-weight)" if b["source"] == "model" else "built-in writer"
    lines.append(f"Brief written by: {src}" + (f"  [{b['note']}]" if b["note"] else ""))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gardener", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd")

    card = sub.add_parser("card", help="print this week's garden card")
    card.add_argument("--region", choices=list(REGIONS))
    card.add_argument("--onset", metavar="MM-DD", help="when your monsoon usually arrives")
    card.add_argument("--withdrawal", metavar="MM-DD", help="when your monsoon usually ends")
    card.add_argument("--no-cool-winter", action="store_true", help="winters are too warm for Rabi crops like cauliflower and peas")
    card.add_argument("--date", metavar="YYYY-MM-DD", help="plan for this day instead of today")
    card.add_argument("--no-model", action="store_true", help="use the built-in writer, skip the language model")

    sub.add_parser("regions", help="list preset places")

    srv = sub.add_parser("serve", help="start the web app")
    srv.add_argument("--host")
    srv.add_argument("--port", type=int)

    args = parser.parse_args(argv)
    cmd = args.cmd or "serve"

    if cmd == "regions":
        for key, r in REGIONS.items():
            seasons = ", ".join(f"{s.name} from {s.start}" for s in r.seasons)
            print(f"{key:<13} {r.label:<24} {r.country:<11} {seasons}")
        return 0

    if cmd == "serve":
        from .server import serve
        serve(getattr(args, "host", None), getattr(args, "port", None))
        return 0

    try:
        region = resolve_region(args.region, args.onset, args.withdrawal, cool=not args.no_cool_winter)
        data = Planner().plan(parse_day(args.date), region, use_model=not args.no_model)
    except PlanError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(render_card(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
