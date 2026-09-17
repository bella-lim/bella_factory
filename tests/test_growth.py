import unittest
from dataclasses import replace

from scout.models import ValidationError
from scout.pipeline import build_candidate, create_batch, record_growth_batch
from scout.publish import apply_publish_result
from scout.growth import (
    band_for_ratio, build_metrics_record, compute_baseline,
    compute_money_performance, compute_performance, generate_feedback,
    guard_published, validate_metrics,
)
from tests.test_pipeline_and_storage import agent_raw
from tests.test_creator import valid_threads


def make_published_candidate(db=None, name_suffix=""):
    raw = agent_raw()
    if name_suffix:
        raw["name"] = raw["name"] + name_suffix
    candidate = build_candidate(raw, "2026-09-13")
    db = db if db is not None else {}
    db[candidate.id] = candidate.to_dict()
    result = create_batch(db, [{"candidate_id": candidate.id, "content": {"threads": valid_threads()}}], "2026-09-13")
    assert not result["errors"], result["errors"]
    updated = apply_publish_result(db, candidate.id, "threads", {
        "status": "PUBLISHED", "post_id": "1", "url": "https://threads.net/x",
        "error": None, "published_at": "2026-09-13T00:00:00Z",
    })
    return db, updated


def metrics(views=1000, conversions=0, **overrides):
    base = {"platform": "threads", "views": views, "likes": 10, "comments": 2, "shares": 1,
            "saves": 3, "clicks": 5, "product_clicks": 2, "conversions": conversions, "revenue": 0}
    base.update(overrides)
    return base


class GuardPublishedTests(unittest.TestCase):
    def test_refuses_unpublished_candidate(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        with self.assertRaises(ValidationError):
            guard_published(candidate)

    def test_allows_published_candidate(self):
        _, candidate = make_published_candidate()
        guard_published(candidate)  # should not raise

    def test_refuses_when_publish_failed_not_published(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        candidate = replace(candidate, publish_status={"threads": {"status": "FAILED"}})
        with self.assertRaises(ValidationError):
            guard_published(candidate)


class MetricsValidationTests(unittest.TestCase):
    def test_accepts_unknown_value(self):
        self.assertEqual(validate_metrics({"views": "UNKNOWN"}), [])

    def test_accepts_nonnegative_number(self):
        self.assertEqual(validate_metrics({"views": 100, "conversions": 0}), [])

    def test_rejects_negative_number(self):
        self.assertTrue(validate_metrics({"views": -1}))

    def test_rejects_unknown_field(self):
        self.assertTrue(validate_metrics({"made_up_metric": 1}))

    def test_rejects_bool_as_number(self):
        self.assertTrue(validate_metrics({"views": True}))

    def test_build_metrics_record_fills_defaults_and_timestamp(self):
        record = build_metrics_record({"platform": "threads", "views": 500})
        self.assertEqual(record["views"], 500)
        self.assertEqual(record["likes"], "UNKNOWN")
        self.assertIsNotNone(record["measured_at"])


class BandBoundaryTests(unittest.TestCase):
    def test_bands_at_boundaries(self):
        self.assertEqual(band_for_ratio(0.69), "UNDERPERFORM")
        self.assertEqual(band_for_ratio(0.7), "NORMAL")
        self.assertEqual(band_for_ratio(1.49), "NORMAL")
        self.assertEqual(band_for_ratio(1.5), "WINNER")
        self.assertEqual(band_for_ratio(2.99), "WINNER")
        self.assertEqual(band_for_ratio(3.0), "HOT")
        self.assertEqual(band_for_ratio(4.99), "HOT")
        self.assertEqual(band_for_ratio(5.0), "BREAKOUT")
        self.assertEqual(band_for_ratio(100), "BREAKOUT")


class BaselineTests(unittest.TestCase):
    def test_insufficient_history_gives_none_baseline(self):
        db, c1 = make_published_candidate()
        db, c2 = make_published_candidate(db, "-2")
        # Only 1 comparable post (c2) recorded when computing for c1 -> below MIN_BASELINE_SAMPLE_SIZE (3)
        growth = dict(c2.growth)
        growth["24H"] = {"metrics": metrics(views=2000), "performance": {}, "money_performance": {}, "feedback": {}}
        c2 = replace(c2, growth=growth)
        db[c2.id] = c2.to_dict()

        baseline, sample_size = compute_baseline(db, "threads", "24H", "views", c1.id)
        self.assertIsNone(baseline)
        self.assertEqual(sample_size, 1)

    def test_sufficient_history_computes_median(self):
        db, c1 = make_published_candidate()
        for i, v in enumerate([1000, 2000, 3000]):
            db, cx = make_published_candidate(db, f"-{i}")
            growth = dict(cx.growth)
            growth["24H"] = {"metrics": metrics(views=v), "performance": {}, "money_performance": {}, "feedback": {}}
            cx = replace(cx, growth=growth)
            db[cx.id] = cx.to_dict()

        baseline, sample_size = compute_baseline(db, "threads", "24H", "views", c1.id)
        self.assertEqual(baseline, 2000)
        self.assertEqual(sample_size, 3)


class PerformanceComputationTests(unittest.TestCase):
    def test_unknown_when_baseline_missing(self):
        db, c1 = make_published_candidate()
        perf = compute_performance(db, c1, "24H", metrics(views=1000))
        self.assertIsNone(perf["ratio"])
        self.assertEqual(perf["band"], "UNKNOWN")

    def test_ratio_computed_against_baseline(self):
        db, c1 = make_published_candidate()
        for i, v in enumerate([1000, 1000, 1000]):
            db, cx = make_published_candidate(db, f"-{i}")
            growth = dict(cx.growth)
            growth["24H"] = {"metrics": metrics(views=v), "performance": {}, "money_performance": {}, "feedback": {}}
            cx = replace(cx, growth=growth)
            db[cx.id] = cx.to_dict()

        perf = compute_performance(db, c1, "24H", metrics(views=2000))
        self.assertEqual(perf["ratio"], 2.0)
        self.assertEqual(perf["band"], "WINNER")


class MoneyPerformanceTests(unittest.TestCase):
    def test_conversions_positive_is_money_winner(self):
        perf = {"band": "NORMAL"}
        result = compute_money_performance(metrics(conversions=5), perf)
        self.assertEqual(result["money_verdict"], "MONEY WINNER")
        self.assertEqual(result["content_verdict"], "VIRAL NORMAL")

    def test_conversions_zero_is_money_failure(self):
        perf = {"band": "HOT"}
        result = compute_money_performance(metrics(conversions=0), perf)
        self.assertEqual(result["money_verdict"], "MONEY FAILURE")

    def test_conversions_unknown_is_money_unknown(self):
        perf = {"band": "UNKNOWN"}
        result = compute_money_performance(metrics(conversions="UNKNOWN"), perf)
        self.assertEqual(result["money_verdict"], "MONEY UNKNOWN")
        self.assertEqual(result["content_verdict"], "VIRAL UNKNOWN")


class FeedbackTests(unittest.TestCase):
    def test_high_content_money_failure_asks_for_cta_change(self):
        fb = generate_feedback({"band": "HOT"}, {"money_verdict": "MONEY FAILURE"})
        self.assertIn("CTA", fb["creator_note"])
        self.assertIsNotNone(fb["generated_at"])

    def test_low_content_money_winner_keeps_niche(self):
        fb = generate_feedback({"band": "UNDERPERFORM"}, {"money_verdict": "MONEY WINNER"})
        self.assertIn("유지", fb["scout_note"])

    def test_every_band_money_combo_has_a_rule(self):
        for band in ("UNDERPERFORM", "NORMAL", "WINNER", "HOT", "BREAKOUT", "UNKNOWN"):
            for verdict in ("MONEY WINNER", "MONEY FAILURE", "MONEY UNKNOWN"):
                fb = generate_feedback({"band": band}, {"money_verdict": verdict})
                self.assertIn("scout_note", fb)
                self.assertIn("money_note", fb)
                self.assertIn("creator_note", fb)


class RecordGrowthBatchTests(unittest.TestCase):
    def test_refuses_unpublished_candidate(self):
        candidate = build_candidate(agent_raw(), "2026-09-13")
        db = {candidate.id: candidate.to_dict()}
        result = record_growth_batch(db, [{"candidate_id": candidate.id, "window": "24H", "metrics": metrics()}])
        self.assertEqual(len(result["errors"]), 1)
        self.assertEqual(len(result["recorded"]), 0)

    def test_records_and_computes_for_published_candidate(self):
        db, candidate = make_published_candidate()
        result = record_growth_batch(db, [{"candidate_id": candidate.id, "window": "24H", "metrics": metrics(views=500)}])
        self.assertEqual(len(result["recorded"]), 1)
        updated = result["recorded"][0]
        self.assertIn("24H", updated.growth)
        self.assertEqual(updated.growth["24H"]["metrics"]["views"], 500)
        self.assertIn("money_verdict", updated.growth["24H"]["money_performance"])

    def test_bad_window_is_reported_as_error(self):
        db, candidate = make_published_candidate()
        result = record_growth_batch(db, [{"candidate_id": candidate.id, "window": "3H", "metrics": metrics()}])
        self.assertEqual(len(result["errors"]), 1)

    def test_missing_candidate_is_reported_as_error(self):
        result = record_growth_batch({}, [{"candidate_id": "nope", "window": "24H", "metrics": metrics()}])
        self.assertEqual(len(result["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
