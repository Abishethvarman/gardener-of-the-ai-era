"""Shared pieces for the dataset, evaluation and fine-tuning scripts."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

# Make `import gardener` work when running these scripts from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gardener.brief import check_faithful, facts, mentioned_crops  # noqa: E402
from gardener.engine import Plan  # noqa: E402
from gardener.service import plan_for  # noqa: E402

SFT_SUFFIX = "\nBRIEF:\n"
URGENT_N = 3   # coverage = share of the 3 closing-soonest open crops the brief names


def plan_for_record(record: dict) -> Plan:
    """Rebuild the engine's plan for a dataset record."""
    today = date.fromisoformat(record["today"])
    if record.get("region"):
        return plan_for(today, region=record["region"])
    return plan_for(today, onset=record["onset"], withdrawal=record["withdrawal"], cool=record.get("cool", True))


def sft_prompt(prompt: str) -> str:
    """Prompt text for a base (non-chat) model: our instructions, then a cue to write."""
    return prompt + SFT_SUFFIX


def clean_generation(text: str) -> str:
    """A base model that has not been tuned tends to ramble past the brief.
    Keep only the first paragraph so baseline and tuned models are scored the same way."""
    return text.strip().split("\n\n", 1)[0].strip()


def score(record: dict, text: str) -> dict:
    """Score one generated brief against the engine's plan for that scenario."""
    plan = plan_for_record(record)
    ok, problems = check_faithful(text, plan)
    f = facts(plan)
    want = {i["crop"] for i in f["plant_now"][:URGENT_N]}
    covered = len(want & mentioned_crops(text)) / len(want) if want else 1.0
    season = (plan.current_season or plan.next_season).name
    return {
        "faithful": ok,
        "problems": problems,
        "coverage": covered,
        "season_named": season.lower() in text.lower(),
        "words": len(text.split()),
    }


def summarize(rows: list[dict], seconds: list[float]) -> dict:
    n = len(rows) or 1
    return {
        "n": len(rows),
        "faithful_rate": sum(r["faithful"] for r in rows) / n,
        "coverage": sum(r["coverage"] for r in rows) / n,
        "season_named_rate": sum(r["season_named"] for r in rows) / n,
        "mean_words": sum(r["words"] for r in rows) / n,
        "mean_seconds": (sum(seconds) / len(seconds)) if seconds else None,
    }


def load_jsonl(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]
