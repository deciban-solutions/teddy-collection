import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "scripts" / "teddy.py"


def records(cards):
    return {"videos": [{"id": "v", "on_screen_cards": cards}],
            "appearances": [{"video_id": "v", "watch_id": "w", "role": "picked"}],
            "watches": [{"id": "w", "confidence": "labelled_on_screen", "basis": "x",
                         "photos": [{"kind": "frame", "path": "a"}]}]}


class TestDatasetAddCli(unittest.TestCase):
    def run_cli(self, recs):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "records.json"
            f.write_text(json.dumps(recs))
            env = {**os.environ, "TEDDY_COLLECTION_HOME": str(Path(d) / "home")}
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "dataset-add", str(f)],
                               env=env, capture_output=True, text=True)
            written = sorted((Path(d) / "home" / "dataset").glob("*.json"))
            return r, written

    def test_wrist_only_refused_and_nothing_written(self):
        r, written = self.run_cli(records(False))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("on_screen_cards", r.stderr)
        self.assertEqual(written, [])

    def test_valid_records_written(self):
        r, written = self.run_cli(records(True))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(written), 3)


if __name__ == "__main__":
    unittest.main()
