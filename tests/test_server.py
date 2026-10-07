import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gardener.llm import LLMClient  # noqa: E402
from gardener.server import make_handler  # noqa: E402
from gardener.service import Planner  # noqa: E402


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        planner = Planner(LLMClient(enabled=False))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(planner))
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close()

    def get(self, path):
        try:
            with urllib.request.urlopen(self.base + path) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read()

    def test_plan_for_preset(self):
        status, _, body = self.get("/api/plan?region=delhi&date=2026-10-06")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["region"]["label"], "New Delhi")
        self.assertEqual(data["current_season"]["title"], "Rabi sowing")
        self.assertEqual(data["next_season"]["start"], "2027-02-21")
        self.assertEqual((data["now"][0]["crop"], data["now"][0]["action"]), ("Cauliflower", "nursery"))
        self.assertEqual(data["now"][0]["local"], "phool gobhi")
        self.assertEqual(data["rains_bands"], [{"start": "06-27", "end": "09-25", "name": "monsoon"}])
        self.assertEqual(data["brief"]["source"], "template")

    def test_plan_for_custom_dates(self):
        status, _, body = self.get("/api/plan?onset=06-15&withdrawal=10-01&cool=0&date=2026-10-20")
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(data["current_season"]["name"], "Post-monsoon")
        self.assertNotIn("Cauliflower", {i["crop"] for i in data["now"] + data["soon"] + data["later"]})

    def test_alerts_are_returned(self):
        data = json.loads(self.get("/api/plan?region=chennai&date=2026-10-06")[2])
        self.assertEqual(len(data["alerts"]), 1)

    def test_bad_input_is_a_400_with_a_useful_message(self):
        for path, needle in [
            ("/api/plan?region=atlantis", "Unknown place"),
            ("/api/plan?onset=06-15", "Enter both dates"),
            ("/api/plan?onset=06-15&withdrawal=6-15", "same day"),
            ("/api/plan?onset=13-40&withdrawal=10-01", "not a real calendar date"),
            ("/api/plan?region=delhi&date=tomorrow", "YYYY-MM-DD"),
            ("/api/plan", "Choose a place"),
        ]:
            status, _, body = self.get(path)
            self.assertEqual(status, 400, path)
            self.assertIn(needle, json.loads(body)["error"], path)

    def test_regions_and_health(self):
        status, _, body = self.get("/api/regions")
        regions = json.loads(body)
        self.assertEqual(status, 200)
        keys = {r["key"] for r in regions}
        self.assertTrue({"delhi", "lahore", "dhaka", "colombo", "chennai"} <= keys)
        delhi = next(r for r in regions if r["key"] == "delhi")
        self.assertEqual((delhi["onset"], delhi["withdrawal"]), ("06-27", "09-25"))
        self.assertFalse(json.loads(self.get("/api/health")[2])["model_reachable"])

    def test_static_files_and_unknown_paths(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertIn(b"Gardener", body)
        self.assertEqual(self.get("/sw.js")[0], 200)
        self.assertEqual(self.get("/nope")[0], 404)
        self.assertEqual(self.get("/../engine.py")[0], 404)


if __name__ == "__main__":
    unittest.main()
