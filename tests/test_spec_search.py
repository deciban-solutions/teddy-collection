"""An unknown spec value must show it was searched for, and a known value from an earlier run
or the dataset is never dropped silently (feedback 2026-11-18: a peer's gmt_type recorded as
unknown after one source, downgrading an earlier run's value)."""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import specs  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"
TRIED = {"tried": ["heron mirabel gmt flyer", "https://example.org/miyota-9075"]}


def watch(value, search=None, wid="heron-mirabel"):
    w = {"id": wid, "confidence": "matched_to_specs", "basis": "x",
         "specs": {"gmt_type": value, "case_mm": 39}}
    if search is not None:
        w["spec_search"] = search
    return w


class TestUnknownErrors(unittest.TestCase):
    def test_known_value_passes(self):
        self.assertEqual(specs.unknown_errors([watch("flyer")], {}, "r"), [])

    def test_unknown_after_one_source_refused(self):
        for search in (None, {}, {"gmt_type": {"tried": ["one query"]}},
                       {"gmt_type": {"tried": ["same", " same "]}}):
            errs = specs.unknown_errors([watch("unknown", search)], {}, "r")
            self.assertTrue(any("spec_search.gmt_type.tried" in e for e in errs), search)

    def test_unknown_after_searching_passes(self):
        self.assertEqual(specs.unknown_errors([watch("unknown", {"gmt_type": TRIED})], {}, "r"), [])

    def test_null_and_dash_count_as_unknown(self):
        for v in (None, "n/a", "—", ""):
            self.assertTrue(specs.unknown_errors([watch(v)], {}, "r"), v)

    def test_downgrading_an_earlier_value_needs_a_reason(self):
        prior = {"heron-mirabel": {"gmt_type": "flyer"}}
        errs = specs.unknown_errors([watch("unknown", {"gmt_type": TRIED})], prior, "r")
        self.assertTrue(any("'flyer'" in e and "dropped_because" in e for e in errs))
        ok = {"gmt_type": {**TRIED, "dropped_because": "the brand page says caller"}}
        self.assertEqual(specs.unknown_errors([watch("unknown", ok)], prior, "r"), [])

    def test_bad_spec_search_shape(self):
        errs = specs.unknown_errors([watch("flyer", ["x"])], {}, "r")
        self.assertTrue(any("must be an object" in e for e in errs))


class TestPriorValues(unittest.TestCase):
    def test_reads_other_runs_not_this_one(self):
        with tempfile.TemporaryDirectory() as d:
            home = Path(d)
            old = os.environ.get("TEDDY_COLLECTION_HOME")
            os.environ["TEDDY_COLLECTION_HOME"] = str(home)
            self.addCleanup(lambda: os.environ.pop("TEDDY_COLLECTION_HOME") if old is None
                            else os.environ.__setitem__("TEDDY_COLLECTION_HOME", old))
            runs = home / "runs"
            (runs / "a").mkdir(parents=True)
            (runs / "b").mkdir()
            (runs / "a" / "peers.json").write_text(json.dumps({"watches": [watch("flyer")]}))
            (runs / "b" / "peers.json").write_text(json.dumps({"watches": [watch("caller")]}))
            got = specs.prior_values(exclude_run=runs / "b", ds={"watches": []})
            self.assertEqual(got["heron-mirabel"]["gmt_type"], "flyer")
            self.assertEqual(got["heron-mirabel"]["case_mm"], 39)


class TestDatasetAddRefuses(unittest.TestCase):
    def run_cli(self, w):
        recs = {"videos": [{"id": "v", "on_screen_cards": False}],
                "appearances": [{"video_id": "v", "watch_id": w["id"], "role": "reviewed"}],
                "watches": [w]}
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "home" / "runs" / "r1"
            run.mkdir(parents=True)
            f = run / "records.json"
            f.write_text(json.dumps(recs))
            env = {**os.environ, "TEDDY_COLLECTION_HOME": str(Path(d) / "home")}
            return subprocess.run([sys.executable, "-I", str(SCRIPT), "dataset-add", str(f)],
                                  env=env, capture_output=True, text=True)

    def test_unsearched_unknown_refused(self):
        r = self.run_cli(watch("unknown"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("spec_search.gmt_type.tried", r.stderr)

    def test_searched_unknown_accepted(self):
        r = self.run_cli(watch("unknown", {"gmt_type": TRIED}))
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
