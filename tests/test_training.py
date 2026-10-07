import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "training"))

import make_dataset  # noqa: E402
import train_tinker  # noqa: E402
from common import clean_generation, score, sft_prompt, summarize  # noqa: E402
import random  # noqa: E402


class CharTokenizer:
    eos_token_id = 1

    def encode(self, text, add_special_tokens=True):
        ids = [ord(c) + 10 for c in text]
        return ([2] + ids) if add_special_tokens else ids  # 2 plays the BOS role


class DatasetTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(3)
        self.records = [make_dataset.build_record(make_dataset.random_scenario(rng), rng) for _ in range(60)]

    def test_gold_completions_score_perfectly(self):
        rows = [score(r, r["completion"]) for r in self.records]
        summary = summarize(rows, [])
        self.assertEqual(summary["faithful_rate"], 1.0)
        self.assertEqual(summary["coverage"], 1.0)
        self.assertEqual(summary["season_named_rate"], 1.0)

    def test_records_cover_presets_and_custom_dates(self):
        self.assertTrue(any("region" in r for r in self.records))
        self.assertTrue(any("onset" in r for r in self.records))

    def test_hallucination_is_caught_and_gaps_are_measured(self):
        # Delhi on Oct 6: Rabi is open; the three most urgent jobs are the
        # cauliflower nursery, the cabbage nursery and tomato transplanting.
        rec = {"today": "2026-10-06", "region": "delhi"}
        bad = score(rec, "Sow okra and watermelon on Dec 31.")
        self.assertFalse(bad["faithful"])
        self.assertEqual(bad["coverage"], 0.0)
        self.assertFalse(bad["season_named"])
        good = score(rec, "Rabi is open: start phool gobhi and cabbage nurseries, and transplant tomatoes.")
        self.assertTrue(good["faithful"])
        self.assertEqual(good["coverage"], 1.0)
        self.assertTrue(good["season_named"])
        partial = score(rec, "Rabi is open. Start a cauliflower nursery.")
        self.assertAlmostEqual(partial["coverage"], 1 / 3)

    def test_prompt_matches_what_the_app_sends(self):
        self.assertIn("FACTS:", self.records[0]["prompt"])
        self.assertTrue(sft_prompt("x").endswith("BRIEF:\n"))


class ExampleTests(unittest.TestCase):
    def test_shift_and_masking(self):
        tok = CharTokenizer()
        inp, tgt, w = train_tinker.build_example(tok, "abc", "xy")
        prompt_len = len(tok.encode(sft_prompt("abc")))
        full = tok.encode(sft_prompt("abc")) + tok.encode("xy", add_special_tokens=False) + [tok.eos_token_id]
        self.assertEqual(inp, full[:-1])
        self.assertEqual(tgt, full[1:])
        self.assertEqual(len(inp), len(tgt))
        self.assertEqual(len(tgt), len(w))
        # prompt tokens are never scored; completion and EOS always are
        self.assertEqual(sum(w), 3.0)
        self.assertEqual(w[: prompt_len - 1], [0.0] * (prompt_len - 1))
        self.assertEqual(tgt[-1], tok.eos_token_id)

    def test_clean_generation_keeps_first_paragraph(self):
        self.assertEqual(clean_generation("  Hello there.\n\nRambling on...\n"), "Hello there.")


if __name__ == "__main__":
    unittest.main()
