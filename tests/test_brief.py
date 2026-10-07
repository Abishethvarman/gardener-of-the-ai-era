import json
import random
import sys
import threading
import unittest
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gardener.brief import check_faithful, make_brief, mentioned_crops, templated_brief  # noqa: E402
from gardener.engine import make_plan  # noqa: E402
from gardener.llm import LLMClient, LLMError  # noqa: E402
from gardener.regions import REGIONS, custom_region  # noqa: E402


def random_plan(rng):
    today = date(2026, 1, 1) + timedelta(days=rng.randint(0, 364))
    if rng.random() < 0.6:
        return make_plan(today, REGIONS[rng.choice(list(REGIONS))])
    onset = date(2026, 5, 25) + timedelta(days=rng.randint(0, 45))
    withdrawal = date(2026, 9, 15) + timedelta(days=rng.randint(0, 40))
    return make_plan(today, custom_region(f"{onset:%m-%d}", f"{withdrawal:%m-%d}", rng.random() < 0.8))


class TemplateTests(unittest.TestCase):
    def test_template_always_passes_its_own_fact_check(self):
        """The fallback writer must never be rejected by the guardrail."""
        rng = random.Random(1)
        for _ in range(400):
            plan = random_plan(rng)
            for variant in range(4):
                text = templated_brief(plan, variant)
                ok, problems = check_faithful(text, plan)
                self.assertTrue(ok, f"{plan.region.key} {plan.today} v{variant}: {problems}\n{text}")

    def test_closing_window_is_named(self):
        plan = make_plan(date(2026, 10, 6), REGIONS["lahore"])
        self.assertIn("Tomato nursery closes soonest: in 1 day (Oct 7).", templated_brief(plan))

    def test_local_names_and_actions(self):
        text = templated_brief(make_plan(date(2026, 10, 6), REGIONS["delhi"]))
        self.assertIn("Rabi sowing is open in New Delhi.", text)
        self.assertIn("cauliflower nursery (phool gobhi)", text)
        self.assertIn("tomato transplanting (tamatar)", text)

    def test_custom_place_reads_naturally(self):
        text = templated_brief(make_plan(date(2026, 7, 1), custom_region("06-15", "10-01")))
        self.assertIn("open in your garden", text)

    def test_alert_is_not_repeated_in_the_brief(self):
        plan = make_plan(date(2026, 10, 6), REGIONS["chennai"])
        self.assertTrue(plan.alerts)
        self.assertNotIn("Raise beds", templated_brief(plan))


class FactCheckTests(unittest.TestCase):
    def setUp(self):
        self.delhi = make_plan(date(2026, 10, 6), REGIONS["delhi"])     # Rabi open
        self.colombo = make_plan(date(2026, 10, 6), REGIONS["colombo"])  # Maha open

    def test_accepts_local_names_in_the_plan(self):
        ok, problems = check_faithful("Sow palak and methi now, and plant lehsun before Nov 9.", self.delhi)
        self.assertTrue(ok, problems)

    def test_rejects_crop_out_of_season(self):
        ok, problems = check_faithful("Sow karela and bhindi this week.", self.delhi)
        self.assertFalse(ok)
        self.assertIn("mentions Bitter gourd, which the plan does not include", problems)
        self.assertIn("mentions Okra, which the plan does not include", problems)

    def test_rejects_invented_date(self):
        ok, problems = check_faithful("Garlic closes on Nov 30.", self.delhi)
        self.assertFalse(ok)
        self.assertTrue(any("Nov 30" in p for p in problems))

    def test_longer_names_win(self):
        self.assertEqual(mentioned_crops("water spinach"), {"Water spinach"})
        self.assertEqual(mentioned_crops("Malabar spinach and spinach"), {"Malabar spinach", "Spinach"})
        self.assertEqual(mentioned_crops("watermelon"), {"Watermelon"})
        ok, _ = check_faithful("Cut the water spinach (kankun) often.", self.colombo)
        self.assertTrue(ok)
        ok, _ = check_faithful("Sow spinach.", self.colombo)
        self.assertFalse(ok)

    def test_english_words_that_are_local_names_are_ignored(self):
        self.assertEqual(mentioned_crops("The season has begun."), set())

    def test_southeast_asian_names(self):
        self.assertEqual(mentioned_crops("Gieo rau muống và cải thìa; trồng ớt."), {"Water spinach", "Pak choi", "Chilli"})
        self.assertEqual(mentioned_crops("Plant sitaw and ampalaya."), {"Yardlong bean", "Bitter gourd"})
        # Longer names first: "makhuea thet" is tomato, "makhuea" alone is brinjal.
        self.assertEqual(mentioned_crops("makhuea thet"), {"Tomato"})
        self.assertEqual(mentioned_crops("luyang dilaw"), {"Turmeric"})

    def test_curly_apostrophes(self):
        self.assertEqual(mentioned_crops("Pick lady’s finger young."), {"Okra"})


class FakeModelServer:
    """A stand-in OpenAI-compatible endpoint that returns a canned reply."""

    def __init__(self, reply=None, status=200):
        outer = self
        self.reply, self.status, self.requests = reply, status, []

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(b'{"data": []}')

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append(body)
                self.send_response(outer.status); self.send_header("Content-Type", "application/json"); self.end_headers()
                self.wfile.write(json.dumps({"choices": [{"message": {"content": outer.reply}}]}).encode())

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close()


class ModelPathTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan(date(2026, 10, 6), REGIONS["delhi"])

    def serve(self, reply, status=200):
        srv = FakeModelServer(reply, status)
        self.addCleanup(srv.close)
        return srv

    def test_good_model_reply_is_used(self):
        srv = self.serve("Rabi sowing is open. Start a cauliflower nursery (phool gobhi) now; it closes Oct 16. "
                         "Garlic and potato can go in too.")
        brief = make_brief(self.plan, LLMClient(base_url=srv.url, model="fake"))
        self.assertEqual(brief.source, "model")
        self.assertEqual(len(srv.requests[0]["messages"]), 1)  # instructions and facts in one user message
        self.assertIn("phool gobhi", srv.requests[0]["messages"][0]["content"])

    def test_hallucinating_model_is_rejected(self):
        srv = self.serve("Sow okra and watermelon before Oct 30.")
        brief = make_brief(self.plan, LLMClient(base_url=srv.url, model="fake"))
        self.assertEqual(brief.source, "template")
        self.assertIn("fact check", brief.note)
        self.assertEqual(brief.text, templated_brief(self.plan))

    def test_unreachable_model_falls_back(self):
        brief = make_brief(self.plan, LLMClient(base_url="http://127.0.0.1:9/v1", model="fake", timeout=1))
        self.assertEqual(brief.source, "template")
        self.assertIn("Offline", brief.note)

    def test_http_error_falls_back(self):
        srv = self.serve("x", status=500)
        self.assertEqual(make_brief(self.plan, LLMClient(base_url=srv.url, model="fake")).source, "template")

    def test_disabled_model_is_never_called(self):
        srv = self.serve("anything")
        brief = make_brief(self.plan, LLMClient(base_url=srv.url, model="fake", enabled=False))
        self.assertEqual(brief.source, "template")
        self.assertEqual(srv.requests, [])

    def test_complete_raises_when_disabled(self):
        with self.assertRaises(LLMError):
            LLMClient(enabled=False).complete("hi")


if __name__ == "__main__":
    unittest.main()
