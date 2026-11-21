import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_stats  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
MONTHS = "DJFMAMJJASON"  # Dec 2025 .. Nov 2026


def bars(svg_text):
    root = ET.fromstring(svg_text)
    return [el for el in root.iter(f"{SVG_NS}rect") if el.get("class") == "bar"]


class MonthsTest(unittest.TestCase):
    def test_month_buckets_order_and_labels(self):
        days = [("2025-11-30", 9), ("2025-12-05", 3), ("2026-01-10", 2), ("2026-01-11", 1), ("2026-11-21", 7)]
        got = build_stats.month_buckets(days, date(2026, 11, 22))
        self.assertEqual("".join(label for label, _ in got), MONTHS)
        self.assertEqual([v for _, v in got], [3, 3, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7])

    def test_short_history_less_than_12_months(self):
        got = build_stats.month_buckets([("2026-10-02", 4), ("2026-11-01", 1)], date(2026, 11, 22))
        self.assertEqual(len(got), 12)
        self.assertEqual([v for _, v in got], [0] * 10 + [4, 1])

    def test_render_activity_all_zero_months(self):
        kpis = [("0", "contributions · 12 mo"), ("0", "contributions this year"), ("0", "active days · 12 mo"),
                ("0", "longest streak · days")]
        svg = build_stats.render_activity(kpis, [(m, 0) for m in MONTHS], ROOT)
        found = bars(svg)
        self.assertEqual(len(found), 12)
        for bar in found:
            self.assertGreaterEqual(float(bar.get("height")), 2)


class KpiTest(unittest.TestCase):
    DAYS = [("2026-01-01", 1), ("2026-01-02", 2), ("2026-01-03", 0), ("2026-01-04", 5), ("2026-01-05", 1),
            ("2026-01-06", 1)]

    def test_longest_streak_and_active_days(self):
        self.assertEqual(build_stats.active_days(self.DAYS), 5)
        self.assertEqual(build_stats.longest_streak(self.DAYS), 3)

    def test_kpi_fallback(self):
        weak = build_stats.kpis(134, 120, 1, 0, self.DAYS)
        self.assertEqual(weak, [("134", "contributions · 12 mo"), ("120", "contributions this year"),
                                ("5", "active days · 12 mo"), ("3", "longest streak · days")])
        strong = build_stats.kpis(134, 120, 20, 2, self.DAYS)
        self.assertEqual(strong[2:], [("20", "pull requests"), ("2", "organizations")])


class LanguagesTest(unittest.TestCase):
    def test_merge_languages(self):
        per_repo = list(json.loads((FIXTURES / "languages.json").read_text()).values())
        got = build_stats.merge_languages(per_repo)
        self.assertEqual([(name, size) for name, size, _ in got],
                         [("Python", 1500), ("TypeScript", 300), ("Jupyter", 200), ("C / C++", 100),
                          ("JavaScript", 100), ("Shell", 50)])  # ties sorted by name
        svg = build_stats.render_languages(got, ROOT)
        root = ET.fromstring(svg)
        pcts = [float(t.text.rstrip("%")) for t in root.iter(f"{SVG_NS}text") if t.get("class") == "lp"]
        self.assertAlmostEqual(sum(pcts), 100.0, delta=0.3)

    def test_fetch_languages_skips_missing_repo(self):
        def fake_urlopen(req, timeout=0):
            if "missing" in req.full_url:
                raise urllib.error.HTTPError(req.full_url, 404, "Not Found", None, None)
            return io.BytesIO(b'{"Python": 10}')

        err = io.StringIO()
        with mock.patch("build_stats.urllib.request.urlopen", fake_urlopen), redirect_stderr(err):
            got = build_stats.fetch_languages(["owner/ok", "owner/missing"], "t0ken")
        self.assertEqual(got, [{"Python": 10}])
        self.assertIn("owner/missing", err.getvalue())


class MainTest(unittest.TestCase):
    def test_main_without_token_exits_nonzero_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True), \
                redirect_stderr(io.StringIO()):
            out = Path(tmp) / "dist"
            self.assertEqual(build_stats.main(["--out", str(out)]), 1)
            self.assertFalse(out.exists())

    def test_main_fails_when_no_language_data(self):
        profile = {"days": [("2026-11-21", 7)], "total_12mo": 7, "total_ytd": 7, "prs": 20, "orgs": 2}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {"GITHUB_TOKEN": "t0ken"}), \
                mock.patch("build_stats.fetch_profile", return_value=profile), \
                mock.patch("build_stats.fetch_languages", return_value=[]), redirect_stderr(io.StringIO()):
            out = Path(tmp) / "dist"
            self.assertEqual(build_stats.main(["--out", str(out)]), 1)
            self.assertFalse(out.exists())

    def test_fetch_profile_parses_graphql(self):
        payload = (FIXTURES / "graphql_ok.json").read_bytes()
        with mock.patch("build_stats.urllib.request.urlopen", return_value=io.BytesIO(payload)):
            got = build_stats.fetch_profile("someone", "t0ken", date(2026, 11, 22))
        self.assertEqual((got["total_12mo"], got["total_ytd"], got["prs"], got["orgs"]), (14, 12, 20, 2))
        self.assertEqual(got["days"][-1], ("2026-11-21", 7))


if __name__ == "__main__":
    unittest.main()
