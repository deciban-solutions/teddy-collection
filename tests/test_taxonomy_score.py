import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import taxonomy  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"


def det(key, rule):
    return {"key": key, "statement": "s", "kind": "more_is_better", "evidence_class": "practitioner",
            "check": {"type": "deterministic", "rule": rule,
                      "planted": {"pass": [{}], "fail": [{}]}}, "sources": []}


TAX = {"id": "shipped:dive@1", "category": "dive", "version": "1", "label": "provisional",
       "paradigm": "p", "created": "2026-11-15", "change_log": [],
       "layers": {"wearer": [], "watch": [
           det("depth", "water_resistance_m >= 200"),
           det("bezel", "'unidirectional' in bezel or 'digital' in bezel"),
           det("crown", "'Screw' in crown"),
           {"key": "legible", "statement": "s", "kind": "must", "evidence_class": "deductive",
            "check": {"type": "judged"}, "sources": []}]}}


class TestScore(unittest.TestCase):
    def score(self, specs):
        return taxonomy.score(TAX, {"id": "w", "specs": specs})

    def test_marks_every_deterministic_criterion(self):
        got = self.score({"water_resistance_m": 300, "bezel": "unidirectional", "crown": "screw-down"})
        self.assertEqual(got, {"watch.depth": "y", "watch.bezel": "y", "watch.crown": "y"})
        self.assertEqual(self.score({"water_resistance_m": 100, "bezel": "fixed", "crown": "push-pull"}),
                         {"watch.depth": "n", "watch.bezel": "n", "watch.crown": "n"})

    def test_missing_field_not_assessable(self):
        got = self.score({"water_resistance_m": 300})
        self.assertEqual(got["watch.bezel"], "not assessable")
        self.assertEqual(got["watch.crown"], "not assessable")
        self.assertEqual(got["watch.depth"], "y")
        self.assertEqual(taxonomy.score(TAX, {"id": "w"})["watch.depth"], "not assessable")

    def test_none_and_unknown_not_assessable(self):
        got = self.score({"water_resistance_m": "unknown", "bezel": None, "crown": "Unknown"})
        self.assertEqual(set(got.values()), {"not assessable"})

    def test_mixed_case(self):
        got = self.score({"water_resistance_m": 200, "bezel": "Unidirectional Ceramic", "crown": "SCREW-DOWN"})
        self.assertEqual(got, {"watch.depth": "y", "watch.bezel": "y", "watch.crown": "y"})
        dress = dict(TAX, layers={"watch": [det("cx", "complications == ['date']")]})
        self.assertEqual(taxonomy.score(dress, {"specs": {"complications": ["Date"]}}), {"watch.cx": "y"})

    def test_wrong_type_not_assessable(self):
        got = self.score({"water_resistance_m": "200 m", "bezel": 5, "crown": "screw-down"})
        self.assertEqual(got["watch.depth"], "not assessable")
        self.assertEqual(got["watch.bezel"], "not assessable")
        self.assertEqual(got["watch.crown"], "y")

    def test_evaluate_unchanged(self):
        with self.assertRaises(ValueError):
            taxonomy.evaluate("bezel == 'x'", {})
        self.assertFalse(taxonomy.evaluate("'Screw' in crown", {"crown": "screw-down"}))

    def test_shipped_dive_with_sparse_record(self):
        got = taxonomy.score(taxonomy.get("shipped:dive@1"), {"specs": {"water_resistance_m": 300}})
        self.assertEqual(got["watch.iso_minimum_depth"], "y")
        self.assertEqual(got["watch.timing_bezel"], "not assessable")


class TestScoreCLI(unittest.TestCase):
    def run_cli(self, *args, home=None):
        env = dict(os.environ, TEDDY_COLLECTION_HOME=home) if home else None
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "taxonomy", "score", *args],
                              capture_output=True, text=True, env=env)

    def test_cli_file_and_category(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "tax.json").write_text(json.dumps(TAX), encoding="utf-8")
            recs = {"watches": [{"id": "a", "specs": {"water_resistance_m": 300, "bezel": "Digital"}}]}
            (d / "records.json").write_text(json.dumps(recs), encoding="utf-8")
            r = self.run_cli(str(d / "tax.json"), str(d / "records.json"), "a")
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertEqual(out["taxonomy"], "shipped:dive@1")
            self.assertEqual(out["marks"], {"watch.depth": "y", "watch.bezel": "y",
                                            "watch.crown": "not assessable"})
            for which in ("shipped:dive@1", "dive"):
                r = self.run_cli(which, str(d / "records.json"), "a", home=str(d / "home"))
                self.assertEqual(r.returncode, 0, r.stderr)
                out = json.loads(r.stdout)
                self.assertEqual(out["taxonomy"], "shipped:dive@1")
                self.assertEqual(out["marks"]["watch.timing_bezel"], "y")
            r = self.run_cli(str(d / "tax.json"), str(d / "records.json"), "nope")
            self.assertEqual(r.returncode, 1)
            self.assertIn("nope", r.stderr)


class TestNotAssessableValues(unittest.TestCase):
    """Final review 14: unknown-like strings and booleans in numeric fields are not assessable."""

    def score(self, specs, tax=TAX):
        return taxonomy.score(tax, {"id": "w", "specs": specs})

    def test_unknown_like_strings(self):
        for v in ("unknown", "n/a", "N/A", "na", "?", "-", "\u2014", "", "  ", " Unknown "):
            got = self.score({"water_resistance_m": 300, "bezel": v, "crown": v})
            self.assertEqual(got["watch.bezel"], "not assessable", repr(v))
            self.assertEqual(got["watch.crown"], "not assessable", repr(v))
            self.assertEqual(got["watch.depth"], "y")

    def test_boolean_in_numeric_field(self):
        for v in (True, False):
            self.assertEqual(self.score({"water_resistance_m": v})["watch.depth"], "not assessable", v)
        declared = {**TAX, "spec_fields": {"lume": "number: lume grade"},
                    "layers": {"watch": [det("lume", "lume == 1")]}}
        self.assertEqual(self.score({"lume": True}, declared)["watch.lume"], "not assessable")
        boolean_rule = {**TAX, "layers": {"watch": [det("date", "has_date == True")]}}
        self.assertEqual(self.score({"has_date": True}, boolean_rule)["watch.date"], "y")


if __name__ == "__main__":
    unittest.main()
