"""Score any OpenAI-compatible model on the held-out scenarios.

Use it to measure the baseline (Gemma through Ollama, or a hosted endpoint) and
any model you serve yourself. For each scenario it sends the same prompt the app
sends, then checks the reply against the engine's facts:

  faithful_rate            no crop or date outside the plan
  coverage                 share of the 3 most urgent open crops the brief names
  season_named_rate        the brief names the sowing season that is open (or opens next)
  mean_seconds             wall-clock time per brief

    python training/eval_faithfulness.py --model gemma3:4b
    python training/eval_faithfulness.py --model gemma3:4b --url https://my-droplet:11434/v1 --limit 50
    python training/eval_faithfulness.py --reference    # the built-in writer, as a sanity check
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import clean_generation, load_jsonl, plan_for_record, score, summarize
from gardener.brief import templated_brief
from gardener.llm import LLMClient, LLMError


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).parent / "data" / "test.jsonl"))
    ap.add_argument("--model", default="gemma3:4b")
    ap.add_argument("--url", default="http://localhost:11434/v1")
    ap.add_argument("--api-key", default="")
    ap.add_argument("--limit", type=int, default=0, help="only score the first N scenarios")
    ap.add_argument("--reference", action="store_true", help="score the built-in writer instead of a model")
    ap.add_argument("--out", help="write full results as JSON to this path")
    args = ap.parse_args()

    records = load_jsonl(args.data)
    if args.limit:
        records = records[: args.limit]
    client = None if args.reference else LLMClient(base_url=args.url.rstrip("/"), model=args.model, api_key=args.api_key, timeout=120)

    rows: list[dict] = []
    seconds: list[float] = []
    failures = 0
    for n, rec in enumerate(records, 1):
        if client is None:
            plan = plan_for_record(rec)
            text, secs = templated_brief(plan), 0.0
        else:
            try:
                text, secs = client.complete(rec["prompt"])
            except LLMError as e:
                failures += 1
                print(f"[{n}/{len(records)}] model error: {e}")
                if failures >= 5 and not rows:
                    print("Giving up: the endpoint isn't answering. Is the model server running?")
                    return 1
                continue
        rows.append(score(rec, clean_generation(text)))
        seconds.append(secs)
        if n % 25 == 0:
            print(f"  scored {n}/{len(records)}")

    summary = summarize(rows, seconds)
    summary["model"] = "built-in writer" if client is None else client.model
    summary["errors"] = failures
    print(json.dumps(summary, indent=2))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
