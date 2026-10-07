import base64
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from fake_model import FakeModel  # noqa: E402
from gardener import features  # noqa: E402
from gardener.engine import make_plan  # noqa: E402
from gardener.features import FeatureError  # noqa: E402
from gardener.features import ask as ask_mod  # noqa: E402
from gardener.features import balcony, diary, language, packet, photo, water  # noqa: E402
from gardener.llm import LLMClient  # noqa: E402
from gardener.regions import REGIONS  # noqa: E402
from gardener.server import make_handler  # noqa: E402
from gardener.service import Planner  # noqa: E402

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 64).decode()
TODAY = date(2026, 10, 7)
DELHI = REGIONS["delhi"]


def client_for(srv):
    return LLMClient(base_url=srv.url, model="gemma3:4b")


class FlagTests(unittest.TestCase):
    def test_flags(self):
        self.assertEqual(features.enabled("all"), set(features.ALL))
        self.assertEqual(features.enabled("none"), set())
        self.assertEqual(features.enabled("diary, water, nonsense"), {"diary", "water"})

    def test_extract_json_from_fenced_reply(self):
        self.assertEqual(features.extract_json('Sure!\n```json\n{"a": 1}\n```'), {"a": 1})
        with self.assertRaises(ValueError):
            features.extract_json("no json here")


class LanguageTests(unittest.TestCase):
    SRC = "Rabi sowing is open in New Delhi. Garlic closes in 33 days (Nov 9)."

    def test_good_translation_passes(self):
        ok, problems = language.check_translation(self.SRC, "नई दिल्ली में रबी की बुवाई खुली है। लहसुन 33 दिन में (9 नवंबर) बंद।", "hi")
        self.assertTrue(ok, problems)

    def test_devanagari_digits_count_as_numbers(self):
        ok, _ = language.check_translation(self.SRC, "नई दिल्ली में रबी की बुवाई खुली है। लहसुन ३३ दिन में (९ नवंबर) बंद।", "hi")
        self.assertTrue(ok)

    def test_changed_or_dropped_numbers_fail(self):
        ok, problems = language.check_translation(self.SRC, "लहसुन 30 दिन में बंद।", "hi")
        self.assertFalse(ok)
        self.assertTrue(any("added" in p for p in problems))
        self.assertTrue(any("dropped" in p for p in problems))

    def test_wrong_script_fails(self):
        ok, problems = language.check_translation(self.SRC, self.SRC, "ta")
        self.assertFalse(ok)
        self.assertTrue(any("Tamil script" in p for p in problems))

    def test_end_to_end_with_model(self):
        srv = FakeModel(); self.addCleanup(srv.close)
        r = language.translate(self.SRC, "hi", client_for(srv), "New Delhi")
        self.assertTrue(r["ok"], r["note"])
        bad = FakeModel("bad"); self.addCleanup(bad.close)
        r = language.translate(self.SRC, "hi", client_for(bad), "New Delhi")
        self.assertFalse(r["ok"])
        self.assertIn("failed the check", r["note"])
        self.assertFalse(language.translate(self.SRC, "xx", client_for(srv), "x")["ok"])


class WaterTests(unittest.TestCase):
    def fc(self, rain, tmax):
        return {"daily": {"time": ["2026-10-07", "2026-10-08", "2026-10-09"], "precipitation_sum": rain, "temperature_2m_max": tmax}}

    def test_rules(self):
        self.assertIn("Skip watering today", water.decide(self.fc([6, 0, 0], [30, 30, 30]), TODAY)["advice"])
        self.assertIn("tomorrow", water.decide(self.fc([0, 9, 0], [30, 30, 30]), TODAY)["advice"])
        self.assertIn("Hot day (37°C)", water.decide(self.fc([0, 0, 0], [37, 30, 30]), TODAY)["advice"])
        self.assertIn("Check the soil", water.decide(self.fc([1, 2, 0], [31, 30, 30]), TODAY)["advice"])

    def test_missing_today_and_network_failure(self):
        with self.assertRaises(water.WaterError):
            water.decide(self.fc([0, 0, 0], [30, 30, 30]), date(2026, 12, 1))

        def broken(lat, lon):
            raise water.WaterError("no network")
        tip = water.water_tip(1.0, 2.0, date(2026, 1, 3), fetch=broken)
        self.assertFalse(tip["available"])
        self.assertFalse(water.water_tip(None, None, TODAY)["available"])

    def test_tip_uses_fetch(self):
        tip = water.water_tip(28.61, 77.21, TODAY, fetch=lambda lat, lon: self.fc([0, 0, 0], [36, 30, 30]))
        self.assertTrue(tip["available"])
        self.assertIn("Hot day", tip["advice"])


class PhotoTests(unittest.TestCase):
    def test_image_validation(self):
        for bad in (None, "", "data:image/gif;base64,AAAA", "data:image/png;base64,***"):
            with self.assertRaises(FeatureError):
                photo.validate_image(bad)
        self.assertEqual(photo.validate_image(PNG), PNG)

    def test_good_reply(self):
        srv = FakeModel(); self.addCleanup(srv.close)
        r = photo.check_plant(PNG, client_for(srv), "New Delhi", "Rabi sowing is open.", "yellow leaves")
        self.assertTrue(r["ok"])
        self.assertEqual(r["plant"], "Tomato")
        self.assertEqual(len(r["possible_causes"]), 2)
        content = srv.requests[0]["messages"][0]["content"]
        self.assertEqual(content[1]["type"], "image_url")          # the photo really is sent
        self.assertIn("yellow leaves", content[0]["text"])
        self.assertEqual(srv.requests[0]["response_format"], {"type": "json_object"})

    def test_doses_are_removed(self):
        srv = FakeModel("bad"); self.addCleanup(srv.close)
        r = photo.check_plant(PNG, client_for(srv), "New Delhi", "", None)
        self.assertNotIn("2 ml", json.dumps(r))
        self.assertNotIn("5 g", json.dumps(r))
        self.assertEqual(r["possible_causes"][0]["check"], photo.DOSE_REPLACEMENT)
        self.assertIn("dose", r["note"])

    def test_model_off(self):
        self.assertFalse(photo.check_plant(PNG, LLMClient(enabled=False), "x", "", None)["ok"])


class AskTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan(TODAY, DELHI)

    def test_windows_always_returned_for_named_crops(self):
        r = ask_mod.ask("When can I plant tamatar and bhindi?", self.plan, TODAY, LLMClient(enabled=False))
        self.assertEqual(r["crops"], ["Okra", "Tomato"])
        self.assertTrue(any(w["crop"] == "Tomato" and w["action"] == "transplant" for w in r["windows"]))
        self.assertIsNone(r["answer"])

    def test_good_answer_is_used(self):
        srv = FakeModel(); self.addCleanup(srv.close)
        r = ask_mod.ask("Can I still plant garlic?", self.plan, TODAY, client_for(srv))
        self.assertEqual(r["source"], "model", r["note"])

    def test_bad_answer_is_rejected(self):
        srv = FakeModel("bad"); self.addCleanup(srv.close)
        r = ask_mod.ask("Can I still plant garlic?", self.plan, TODAY, client_for(srv))
        self.assertIsNone(r["answer"])
        self.assertIn("Dec 31", r["note"])
        self.assertIn("Bitter gourd", r["note"])

    def test_crop_not_grown_here(self):
        r = ask_mod.ask("When do I sow cauliflower?", make_plan(TODAY, REGIONS["colombo"]), TODAY, None)
        self.assertEqual(r["missing"], ["Cauliflower"])

    def test_input_limits(self):
        with self.assertRaises(FeatureError):
            ask_mod.ask("   ", self.plan, TODAY, None)
        with self.assertRaises(FeatureError):
            ask_mod.ask("x" * 401, self.plan, TODAY, None)


class PacketTests(unittest.TestCase):
    def test_packet_read_and_calendar_decides(self):
        srv = FakeModel(); self.addCleanup(srv.close)
        r = packet.read_packet(PNG, DELHI, TODAY, client_for(srv))
        self.assertEqual(r["crop"], "Tomato")
        self.assertEqual(r["packet"]["sowing_time"], "Jun-Jul, Oct-Nov")
        self.assertTrue(r["verdict"].startswith("Yes"))   # Delhi Oct 7: tomato transplanting is open
        r = packet.read_packet(PNG, REGIONS["delhi"], date(2026, 5, 1), client_for(srv))
        self.assertTrue(r["verdict"].startswith("Not yet"))

    def test_verdict_for_crop_not_grown_here(self):
        msg, windows = packet.verdict("Cauliflower", REGIONS["colombo"], TODAY)
        self.assertIn("isn't in the calendar", msg)
        self.assertEqual(windows, [])


class DiaryTests(unittest.TestCase):
    def test_ready_dates_and_status(self):
        r = diary.harvest_plan([
            {"id": "a", "crop": "Spinach", "planted": "2026-09-01"},    # ready Oct 6: ready now
            {"id": "b", "crop": "Garlic", "planted": "2026-10-05"},     # ready Mar 4
            {"id": "c", "crop": "Radish", "planted": "2026-06-01"},     # long finished
        ], TODAY, DELHI)
        by = {e["crop"]: e for e in r["entries"]}
        self.assertEqual(by["Spinach"]["status"], "ready")
        self.assertEqual((by["Garlic"]["status"], by["Garlic"]["ready"]), ("growing", "2027-03-04"))
        self.assertEqual(by["Radish"]["status"], "old")
        self.assertIn("1 planting should be ready now", r["summary"])

    def test_resow_nudge_only_for_quick_crops_in_an_open_window(self):
        r = diary.harvest_plan([{"crop": "Spinach", "planted": "2026-09-20"}, {"crop": "Garlic", "planted": "2026-09-20"}], TODAY, DELHI)
        by = {e["crop"]: e for e in r["entries"]}
        self.assertTrue(by["Spinach"]["resow"])
        self.assertFalse(by["Garlic"]["resow"])

    def test_bad_input(self):
        for entries in ([{"crop": "Dragonfruit", "planted": "2026-10-01"}], [{"crop": "Spinach", "planted": "soon"}],
                        [{"crop": "Spinach", "planted": "2027-01-01"}], "nope"):
            with self.assertRaises(FeatureError):
                diary.harvest_plan(entries, TODAY)


class BalconyTests(unittest.TestCase):
    def test_shade_and_pots(self):
        plan = make_plan(TODAY, DELHI)
        r = balcony.suggest(plan, sun_hours=4, pots=3)
        self.assertEqual(len(r["suggestions"]), 3)
        self.assertTrue(all(s["sun"] == "part" for s in r["suggestions"]))
        self.assertTrue(any(x["crop"] == "Tomato" and "6+" in x["reason"] for x in r["skipped"]))
        full = balcony.suggest(plan, sun_hours=8, pots=30)
        self.assertTrue(any(s["crop"] == "Tomato" for s in full["suggestions"]))

    def test_open_ground_crops_are_skipped(self):
        plan = make_plan(date(2027, 3, 1), DELHI)  # Zaid: watermelon is open
        r = balcony.suggest(plan, sun_hours=8, pots=30)
        self.assertNotIn("Watermelon", {s["crop"] for s in r["suggestions"]})
        self.assertIn({"crop": "Watermelon", "reason": "needs open ground"}, r["skipped"])

    def test_too_shady_and_bad_input(self):
        self.assertIsNotNone(balcony.suggest(make_plan(TODAY, DELHI), 2, 4)["note"])
        with self.assertRaises(FeatureError):
            balcony.suggest(make_plan(TODAY, DELHI), 20, 4)


class ServerFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = FakeModel()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Planner(client_for(cls.model))))
        cls.base = f"http://127.0.0.1:{cls.httpd.server_port}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.off = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(Planner(client_for(cls.model)), enabled={"diary"}))
        cls.off_base = f"http://127.0.0.1:{cls.off.server_port}"
        threading.Thread(target=cls.off.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for h in (cls.httpd, cls.off):
            h.shutdown(); h.server_close()
        cls.model.close()

    def call(self, path, body=None, base=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request((base or self.base) + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_plan_with_translation(self):
        s, d = self.call("/api/plan?region=delhi&date=2026-10-07&lang=hi")
        self.assertEqual(s, 200)
        self.assertTrue(d["translation"]["ok"], d["translation"]["note"])

    def test_post_features(self):
        s, d = self.call("/api/photo", {"region": "delhi", "date": "2026-10-07", "image": PNG})
        self.assertEqual((s, d["plant"]), (200, "Tomato"))
        s, d = self.call("/api/packet", {"region": "delhi", "date": "2026-10-07", "image": PNG})
        self.assertEqual((s, d["crop"]), (200, "Tomato"))
        s, d = self.call("/api/ask", {"region": "delhi", "date": "2026-10-07", "question": "When can I plant garlic?"})
        self.assertEqual((s, d["source"]), (200, "model"))
        s, d = self.call("/api/diary", {"region": "delhi", "date": "2026-10-07", "entries": [{"crop": "Spinach", "planted": "2026-10-01"}]})
        self.assertEqual((s, d["entries"][0]["ready"]), (200, "2026-11-05"))
        s, d = self.call("/api/balcony?region=delhi&date=2026-10-07&sun=4&pots=2")
        self.assertEqual((s, len(d["suggestions"])), (200, 2))

    def test_errors(self):
        self.assertEqual(self.call("/api/photo", {"region": "delhi", "image": "data:image/gif;base64,AA"})[0], 400)
        self.assertEqual(self.call("/api/ask", {"region": "atlantis", "question": "hi"})[0], 400)
        self.assertEqual(self.call("/api/balcony?region=delhi&sun=lots")[0], 400)
        self.assertEqual(self.call("/api/photo")[0], 405)
        req = urllib.request.Request(self.base + "/api/ask", data=b"not json", headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req)
        self.assertEqual(cm.exception.code, 400)

    def test_switched_off_features(self):
        self.assertEqual(self.call("/api/features", base=self.off_base)[1], {"enabled": ["diary"]})
        self.assertEqual(self.call("/api/photo", {"region": "delhi", "image": PNG}, base=self.off_base)[0], 404)
        s, d = self.call("/api/plan?region=delhi&lang=hi", base=self.off_base)
        self.assertEqual(s, 200)
        self.assertNotIn("translation", d)           # language is off: calendar still works
        self.assertEqual(self.call("/api/diary", {"entries": []}, base=self.off_base)[0], 200)


if __name__ == "__main__":
    unittest.main()
