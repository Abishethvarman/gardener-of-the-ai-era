"""Fine-tune a small open-weight model on Tinker to write Gardener briefs,
then compare it with the same model before tuning.

Why: a general model has to be coaxed into staying inside the plan's facts. A
small model fine-tuned on a few thousand engine-generated examples can do the
one job (turn facts into a brief) faithfully and cheaply. This script measures
whether that's true, using the same fact check the app runs at request time.

Setup (needs a Tinker account; promo credits are at hacktoberfest.com/my/promos):

    pip install -r training/requirements.txt
    export TINKER_API_KEY=...
    python training/make_dataset.py
    python training/train_tinker.py --list-models          # see what's currently offered
    python training/train_tinker.py --base-model meta-llama/Llama-3.2-1B

`--dry-run` builds the training examples and checks token alignment without
touching the network, so you can validate the data before spending anything.

NOTE: written against the Tinker SDK docs (ServiceClient, TrainingClient,
forward_backward, optim_step, save_weights_for_sampler, SamplingClient).
Check the current docs if a call has changed: https://tinker-docs.thinkingmachines.ai
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

from common import clean_generation, load_jsonl, score, sft_prompt, summarize

DATA = Path(__file__).parent / "data"
RESULTS = Path(__file__).parent / "results"


def build_example(tokenizer, prompt: str, completion: str) -> tuple[list[int], list[int], list[float]]:
    """Return (input_ids, target_ids, weights) for next-token training.

    The model sees prompt + completion, but only the completion is scored:
    weights are 0 over the prompt and 1 over the completion (plus an
    end-of-sequence token so the tuned model learns to stop).
    Inputs are tokens[:-1] and targets are tokens[1:], the usual one-step shift.
    """
    p = tokenizer.encode(sft_prompt(prompt), add_special_tokens=True)
    c = tokenizer.encode(completion, add_special_tokens=False) + [tokenizer.eos_token_id]
    tokens = p + c
    weights = [0.0] * len(p) + [1.0] * len(c)
    return tokens[:-1], tokens[1:], weights[1:]


def to_datum(example: tuple[list[int], list[int], list[float]]):
    import torch
    from tinker import types

    inp, tgt, w = example
    return types.Datum(
        model_input=types.ModelInput.from_ints(inp),
        loss_fn_inputs={
            "target_tokens": torch.tensor(tgt, dtype=torch.long),
            "weights": torch.tensor(w, dtype=torch.float32),
        },
    )


def loss_of(result) -> float | None:
    """The docs show `result.loss`; fall back to metrics if this SDK version differs."""
    if getattr(result, "loss", None) is not None:
        return float(result.loss)
    metrics = getattr(result, "metrics", None) or {}
    for k, v in metrics.items():
        if "loss" in k:
            return float(v)
    return None


def sample_text(client, tokenizer, prompt: str, max_tokens: int) -> tuple[str, float]:
    from tinker import types

    mi = types.ModelInput.from_ints(tokenizer.encode(sft_prompt(prompt), add_special_tokens=True))
    params = types.SamplingParams(max_tokens=max_tokens, temperature=0.3)
    start = time.perf_counter()
    res = client.sample(mi, 1, params).result()
    elapsed = time.perf_counter() - start
    tokens = res.sequences[0].tokens
    return clean_generation(tokenizer.decode(tokens, skip_special_tokens=True)), elapsed


def evaluate(client, tokenizer, records: list[dict], max_tokens: int) -> dict:
    rows, secs = [], []
    for rec in records:
        text, s = sample_text(client, tokenizer, rec["prompt"], max_tokens)
        rows.append(score(rec, text))
        secs.append(s)
    return summarize(rows, secs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", default="meta-llama/Llama-3.2-1B")
    ap.add_argument("--train", default=str(DATA / "train.jsonl"))
    ap.add_argument("--test", default=str(DATA / "test.jsonl"))
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32)
    ap.add_argument("--eval-n", type=int, default=100, help="held-out scenarios to score")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--name", default="gardener-writer")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.list_models:
        import tinker
        print(tinker.ServiceClient().get_server_capabilities())
        return 0

    train = load_jsonl(args.train)
    test = load_jsonl(args.test)[: args.eval_n]
    random.Random(0).shuffle(train)

    service = None
    if args.dry_run:
        class Whitespace:  # stand-in tokenizer, only to check shapes
            eos_token_id = 0
            def encode(self, text, add_special_tokens=True):
                return [hash(w) % 50000 + 1 for w in text.split()]
        tokenizer = Whitespace()
    else:
        import tinker
        from tinker import types
        service = tinker.ServiceClient()
        training = service.create_lora_training_client(base_model=args.base_model, rank=args.rank)
        tokenizer = training.get_tokenizer()

    examples = [build_example(tokenizer, r["prompt"], r["completion"]) for r in train]
    tokens_per_epoch = sum(len(e[0]) for e in examples)
    scored_tokens = sum(int(sum(e[2])) for e in examples)
    print(f"{len(examples)} examples, {tokens_per_epoch:,} tokens per epoch "
          f"({scored_tokens:,} scored), {args.epochs} epochs")
    assert all(len(i) == len(t) == len(w) for i, t, w in examples), "misaligned example"
    if args.dry_run:
        print("Dry run OK: every example has matching input, target and weight lengths.")
        return 0

    from tinker import types

    print("Scoring the base model before tuning...")
    base_client = service.create_sampling_client(base_model=args.base_model)
    before = evaluate(base_client, tokenizer, test, args.max_tokens)
    print("before:", json.dumps(before))

    datums = [to_datum(e) for e in examples]
    steps = 0
    started = time.perf_counter()
    for epoch in range(args.epochs):
        random.Random(epoch).shuffle(datums)
        for i in range(0, len(datums), args.batch_size):
            batch = datums[i : i + args.batch_size]
            # Submit both calls before waiting so they pipeline on the server.
            fb = training.forward_backward(batch, "cross_entropy")
            op = training.optim_step(types.AdamParams(learning_rate=args.lr))
            loss = loss_of(fb.result())
            op.result()
            steps += 1
            if steps % 5 == 0:
                print(f"epoch {epoch + 1} step {steps} loss {loss}")
    train_seconds = time.perf_counter() - started

    path = training.save_weights_for_sampler(args.name).result().path
    print("Saved sampler weights:", path)
    tuned_client = service.create_sampling_client(model_path=path)

    print("Scoring the tuned model...")
    after = evaluate(tuned_client, tokenizer, test, args.max_tokens)
    print("after: ", json.dumps(after))

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"tinker_{int(time.time())}.json"
    out.write_text(json.dumps({
        "base_model": args.base_model, "tinker_path": path, "epochs": args.epochs,
        "batch_size": args.batch_size, "learning_rate": args.lr, "lora_rank": args.rank,
        "train_examples": len(examples), "tokens_per_epoch": tokens_per_epoch,
        "train_seconds": round(train_seconds, 1), "before": before, "after": after,
    }, indent=2))
    print("wrote", out)

    def pct(x): return f"{x * 100:.0f}%"
    print("\n| metric | base model | tuned |\n|---|---|---|")
    print(f"| faithful briefs | {pct(before['faithful_rate'])} | {pct(after['faithful_rate'])} |")
    print(f"| crops covered | {pct(before['coverage'])} | {pct(after['coverage'])} |")
    print(f"| names the right season | {pct(before['season_named_rate'])} | {pct(after['season_named_rate'])} |")
    print(f"| seconds per brief | {before['mean_seconds']:.2f} | {after['mean_seconds']:.2f} |")
    print("\nTo serve it yourself: tinker checkpoint download", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
