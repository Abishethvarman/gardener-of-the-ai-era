import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gardener.engine import PlanError, make_plan, md_in_year, parse_md  # noqa: E402
from gardener.regions import REGIONS, custom_region, shift_md  # noqa: E402


def find(items, crop, action=None):
    return next((i for i in items if i.crop == crop and (action is None or i.action == action)), None)


def every_item_over_a_year(region, year=2026):
    seen = set()
    d = date(year, 1, 1)
    while d.year == year:
        p = make_plan(d, region)
        seen |= {i.crop for i in p.now + p.soon + p.later}
        d = date.fromordinal(d.toordinal() + 7)
    return seen


class ParseTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(parse_md("06-27"), (6, 27))
        self.assertEqual(parse_md("6-8"), (6, 8))

    def test_invalid(self):
        for bad in ("", "June 27", "13-01", "02-30", "06/27", "9-31"):
            with self.assertRaises(PlanError, msg=bad):
                parse_md(bad)

    def test_feb_29(self):
        self.assertEqual(md_in_year((2, 29), 2027), date(2027, 2, 28))
        self.assertEqual(md_in_year((2, 29), 2028), date(2028, 2, 29))
        make_plan(date(2028, 2, 29), REGIONS["delhi"])  # must not raise

    def test_shift_md(self):
        self.assertEqual(shift_md("06-27", -126), "02-21")
        self.assertEqual(shift_md("01-10", -30), "12-11")


class DelhiTests(unittest.TestCase):
    """New Delhi: IMD normal onset Jun 27, withdrawal Sep 25."""

    def setUp(self):
        self.plan = make_plan(date(2026, 10, 6), REGIONS["delhi"])

    def test_seasons(self):
        self.assertEqual(self.plan.current_season.name, "Rabi")
        self.assertEqual(self.plan.current_season.start, date(2026, 9, 25))
        self.assertEqual(self.plan.next_season.name, "Zaid")
        self.assertEqual(self.plan.next_season.start, date(2027, 2, 21))

    def test_rains(self):
        self.assertFalse(self.plan.in_rains)
        self.assertEqual((self.plan.rains.event, self.plan.rains.date, self.plan.rains.days), ("starts", date(2027, 6, 27), 264))

    def test_rabi_windows(self):
        garlic = find(self.plan.now, "Garlic", "plant")
        self.assertEqual((garlic.start, garlic.end), (date(2026, 10, 2), date(2026, 11, 9)))
        cauli = find(self.plan.now, "Cauliflower", "nursery")
        self.assertEqual(cauli.days_left, 10)
        self.assertEqual(find(self.plan.soon, "Peas", "sow").days_until, 3)
        self.assertEqual(find(self.plan.now, "Spinach").local, "palak")

    def test_no_warm_season_sowing_in_rabi(self):
        self.assertIsNone(find(self.plan.now, "Okra"))
        self.assertIsNone(find(self.plan.now, "Watermelon"))

    def test_open_items_are_sorted_closing_first(self):
        days = [i.days_left for i in self.plan.now]
        self.assertEqual(days, sorted(days))

    def test_no_duplicate_rows(self):
        keys = [(i.crop, i.action) for i in self.plan.now + self.plan.soon + self.plan.later]
        self.assertEqual(len(keys), len(set(keys)))

    def test_year_boundary(self):
        plan = make_plan(date(2026, 12, 20), REGIONS["delhi"])
        onion = find(plan.now, "Onion", "transplant")
        self.assertEqual((onion.start, onion.end), (date(2026, 12, 9), date(2027, 1, 18)))
        self.assertEqual(plan.next_season.start, date(2027, 2, 21))

    def test_saplings_with_the_monsoon(self):
        plan = make_plan(date(2026, 7, 10), REGIONS["delhi"])
        self.assertTrue(plan.in_rains)
        self.assertIsNotNone(find(plan.now, "Tree saplings"))
        self.assertEqual(plan.current_season.name, "Kharif")
        self.assertIsNotNone(find(plan.now, "Okra", "sow"))


class PublishedCalendarTests(unittest.TestCase):
    """Spot checks against the sources named in regions.py and crops.py."""

    def test_lahore_onion_matches_punjab_advice(self):
        # Punjab agriculture department: onion nursery until end of November,
        # transplanting in December and January.
        plan = make_plan(date(2026, 11, 1), REGIONS["lahore"])
        nursery = find(plan.now, "Onion", "nursery")
        self.assertEqual(nursery.end, date(2026, 11, 29))
        transplant = find(plan.soon + plan.later, "Onion", "transplant")
        self.assertEqual((transplant.start.month, transplant.end.month), (12, 1))

    def test_lahore_summer_vegetables_in_feb_march(self):
        # Punjab agriculture department: summer vegetables February to March.
        plan = make_plan(date(2027, 3, 1), REGIONS["lahore"])
        okra = find(plan.now, "Okra", "sow")
        self.assertEqual(okra.start, date(2027, 2, 25))
        self.assertEqual(plan.current_season.name, "Summer vegetable")

    def test_sri_lanka_okra_matches_doa(self):
        # DOA: Yala early April to early May, Maha early September to early October.
        yala = find(make_plan(date(2027, 4, 15), REGIONS["colombo"]).now, "Okra", "sow")
        self.assertLessEqual(yala.start, date(2027, 4, 5))
        self.assertGreaterEqual(yala.end, date(2027, 5, 5))
        maha = find(make_plan(date(2026, 9, 15), REGIONS["colombo"]).now, "Okra", "sow")
        self.assertLessEqual(maha.start, date(2026, 9, 5))
        self.assertGreaterEqual(maha.end, date(2026, 10, 5))

    def test_lowland_sri_lanka_never_suggests_rabi_crops(self):
        crops = every_item_over_a_year(REGIONS["colombo"])
        for cool_crop in ("Cauliflower", "Peas", "Carrot", "Garlic", "Potato", "Ginger"):
            self.assertNotIn(cool_crop, crops)
        self.assertIn("Okra", crops)

    def test_dhaka_in_rains_with_rabi_next(self):
        plan = make_plan(date(2026, 10, 6), REGIONS["dhaka"])
        self.assertTrue(plan.in_rains)
        self.assertEqual((plan.rains.event, plan.rains.days), ("ends", 2))
        self.assertIsNone(plan.current_season)
        self.assertEqual((plan.next_season.name, plan.next_season.start), ("Rabi", date(2026, 10, 8)))


class SoutheastAsiaTests(unittest.TestCase):
    def test_bangkok_follows_tmd_seasons(self):
        # TMD: rainy mid-May to mid-October, then the cool season.
        plan = make_plan(date(2026, 10, 6), REGIONS["bangkok"])
        self.assertTrue(plan.in_rains)
        self.assertEqual(plan.rains.date, date(2026, 10, 15))
        self.assertEqual((plan.next_season.name, plan.next_season.start), ("Cool season", date(2026, 10, 15)))

    def test_lowland_bangkok_gets_no_rabi_crops_but_chiang_mai_does(self):
        self.assertNotIn("Cauliflower", every_item_over_a_year(REGIONS["bangkok"]))
        self.assertIn("Garlic", every_item_over_a_year(REGIONS["chiangmai"]))

    def test_manila_and_ho_chi_minh(self):
        manila = make_plan(date(2026, 6, 10), REGIONS["manila"])
        self.assertEqual(manila.current_season.name, "Wet season")
        self.assertEqual(find(manila.now, "Yardlong bean").local, "sitaw")
        hcm = make_plan(date(2026, 12, 10), REGIONS["hochiminh"])
        self.assertFalse(hcm.in_rains)
        self.assertEqual(hcm.current_season.name, "Dry season")
        self.assertEqual(find(hcm.now, "Watermelon").local, "dưa hấu")

    def test_pak_choi_only_in_southeast_asia(self):
        self.assertIn("Pak choi", every_item_over_a_year(REGIONS["hochiminh"]))
        self.assertNotIn("Pak choi", every_item_over_a_year(REGIONS["delhi"]))
        self.assertNotIn("Pak choi", every_item_over_a_year(custom_region("06-10", "10-05")))


class RainsTests(unittest.TestCase):
    def test_wrapping_rains(self):
        plan = make_plan(date(2027, 1, 10), REGIONS["anuradhapura"])
        self.assertTrue(plan.in_rains)
        self.assertEqual(plan.rains.date, date(2027, 1, 31))

    def test_two_rainy_seasons(self):
        plan = make_plan(date(2026, 10, 6), REGIONS["colombo"])
        self.assertEqual((plan.rains.name, plan.rains.event), ("inter-monsoon season", "ends"))
        plan = make_plan(date(2026, 9, 28), REGIONS["colombo"])
        self.assertFalse(plan.in_rains)
        self.assertEqual((plan.rains.name, plan.rains.days), ("inter-monsoon season", 3))

    def test_alert_before_the_rains(self):
        plan = make_plan(date(2026, 10, 6), REGIONS["chennai"])
        self.assertEqual(len(plan.alerts), 1)
        self.assertIn("northeast monsoon", plan.alerts[0])
        self.assertEqual(make_plan(date(2026, 8, 1), REGIONS["chennai"]).alerts, [])
        self.assertEqual(make_plan(date(2026, 11, 1), REGIONS["chennai"]).alerts, [])

    def test_skipped_crops_never_appear(self):
        self.assertNotIn("Ginger", every_item_over_a_year(REGIONS["chennai"]))


class CustomTests(unittest.TestCase):
    def test_custom_with_cool_winter(self):
        plan = make_plan(date(2026, 10, 20), custom_region("06-10", "10-05"))
        self.assertEqual(plan.current_season.name, "Winter")
        self.assertIsNotNone(find(plan.now, "Spinach"))

    def test_custom_without_cool_winter(self):
        region = custom_region("06-10", "10-05", cool=False)
        self.assertNotIn("Cauliflower", every_item_over_a_year(region))
        plan = make_plan(date(2026, 10, 20), region)
        self.assertEqual(plan.current_season.name, "Post-monsoon")
        self.assertIsNotNone(find(plan.now, "Okra"))

    def test_rains_that_cross_new_year(self):
        # Wet season November to April, as in parts of Indonesia.
        plan = make_plan(date(2027, 1, 10), custom_region("11-01", "04-15", cool=False))
        self.assertTrue(plan.in_rains)
        self.assertEqual(plan.rains.date, date(2027, 4, 15))


if __name__ == "__main__":
    unittest.main()
