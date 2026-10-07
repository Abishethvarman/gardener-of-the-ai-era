"""Generate a synthetic fine-tuning set from the planning engine.

Each record is one imaginary gardener on one imaginary day: a preset place
(Delhi, Dhaka, Colombo...) or random monsoon dates, and a random date. The
engine works out the facts; the prompt is exactly what the app sends to a
model; the completion is the deterministic brief (one of four phrasings).
Nothing here needs a model or a network, and the labels are correct by
construction, which is the point: the engine knows the calendar, and the model
only has to learn to say it faithfully.

    python training/make_dataset.py --train 1200 --test 150
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import date, timedelta
from pathlib import Path

from common import plan_for_record  # also fixes sys.path
from gardener.brief import build_prompt, templated_brief
from gardener.regions import REGIONS


def random_scenario(rng: random.Random) -> dict:
    today = (date(2026, 1, 1) + timedelta(days=rng.randint(0, 364))).isoformat()
    if rng.random() < 0.6:
        return {"today": today, "region": rng.choice(list(REGIONS))}
    onset = date(2026, 5, 25) + timedelta(days=rng.randint(0, 45))        # late May to early July
    withdrawal = date(2026, 9, 15) + timedelta(days=rng.randint(0, 40))   # mid-Sep to late Oct
    return {
        "today": today,
        "onset": f"{onset.month:02d}-{onset.day:02d}",
        "withdrawal": f"{withdrawal.month:02d}-{withdrawal.day:02d}",
        "cool": rng.random() < 0.8,
    }


def build_record(scn: dict, rng: random.Random) -> dict:
    plan = plan_for_record(scn)
    return {**scn, "prompt": build_prompt(plan), "completion": templated_brief(plan, rng.randrange(4))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=int, default=1200)
    ap.add_argument("--test", type=int, default=150)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(Path(__file__).parent / "data"))
    args = ap.parse_args()

    rng = random.Random(args.seed)
    seen: set[str] = set()
    records: list[dict] = []
    while len(records) < args.train + args.test:
        scn = random_scenario(rng)
        key = json.dumps(scn, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        records.append(build_record(scn, rng))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, chunk in (("train", records[: args.train]), ("test", records[args.train:])):
        with open(out / f"{name}.jsonl", "w", encoding="utf-8") as fh:
            for r in chunk:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"wrote {len(chunk)} records to {out / (name + '.jsonl')}")


if __name__ == "__main__":
    main()
