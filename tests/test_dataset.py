import os, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import dataset  # noqa: E402


def watch(**kw):
    w = {"id": "rolex-submariner-124060", "brand": "Rolex", "model": "Submariner",
         "reference": "124060", "category": "dive", "specs": {},
         "confidence": "legible_on_dial", "basis": "reference printed on dial",
         "status_history": [], "price_history": [], "sources": [], "photos": []}
    w.update(kw)
    return w


def price(date, amount, source_type):
    return {"date": date, "amount": amount, "currency": "USD",
            "source_type": source_type, "url": "https://example.com/p"}


class TestUpsert(unittest.TestCase):
    def test_upsert_keeps_price_history(self):
        ds = {"videos": [], "appearances": [], "watches": []}
        dataset.upsert_watch(ds, watch(price_history=[price("2026-12-01", 7400, "list")]))
        dataset.upsert_watch(ds, watch(price_history=[price("2026-11-14", 7100, "dealer")]))
        self.assertEqual(len(ds["watches"]), 1)
        hist = ds["watches"][0]["price_history"]
        self.assertEqual([(h["date"], h["amount"]) for h in hist],
                         [("2026-11-14", 7100), ("2026-12-01", 7400)])

    def test_upsert_appends_status(self):
        ds = {"videos": [], "appearances": [], "watches": []}
        dataset.upsert_watch(ds, watch(status_history=[
            {"date": "2026-01-01", "status": "in_production", "source": "brand"}]))
        dataset.upsert_watch(ds, watch(status_history=[
            {"date": "2026-11-01", "status": "discontinued", "source": "brand"}]))
        st = [s["status"] for s in ds["watches"][0]["status_history"]]
        self.assertEqual(st, ["in_production", "discontinued"])

    def test_repeat_entry_not_duplicated(self):
        ds = {"videos": [], "appearances": [], "watches": []}
        w = watch(price_history=[price("2026-11-14", 7100, "dealer")])
        dataset.upsert_watch(ds, w)
        dataset.upsert_watch(ds, w)
        self.assertEqual(len(ds["watches"][0]["price_history"]), 1)

    def test_photos_dedupe_by_path_newest_wins(self):
        # G9: correcting a still's `at` (same path) must not leave two entries.
        ds = {"videos": [], "appearances": [], "watches": []}
        dataset.upsert_watch(ds, watch(photos=[{"kind": "frame", "path": "img/a.jpg", "at": "06:39"}]))
        dataset.upsert_watch(ds, watch(photos=[{"kind": "frame", "path": "img/a.jpg", "at": "06:44",
                                                "checked": True},
                                               {"kind": "frame", "path": "img/b.jpg", "at": "07:00"}]))
        self.assertEqual(ds["watches"][0]["photos"],
                         [{"kind": "frame", "path": "img/a.jpg", "at": "06:44", "checked": True},
                          {"kind": "frame", "path": "img/b.jpg", "at": "07:00"}])

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": d}):
                ds = dataset.load()
                self.assertEqual(ds, {"videos": [], "appearances": [], "watches": []})
                dataset.add_video(ds, {"id": "v1", "on_screen_cards": True})
                dataset.save(ds)
                self.assertEqual(dataset.load()["videos"][0]["id"], "v1")
                self.assertTrue((Path(d) / "dataset" / "videos.json").is_file())


class TestTimestampValidation(unittest.TestCase):
    def test_unparseable_timestamp_reported(self):
        # Final review 7: validate names the watch and the field.
        ds = {"videos": [{"id": "v1", "on_screen_cards": True}], "watches": [watch()],
              "appearances": [{"video_id": "v1", "watch_id": "rolex-submariner-124060",
                               "role": "listed", "timestamps": ["1:30", "intro", 95, "nan"]}]}
        errs = dataset.validate(ds)
        self.assertEqual(len(errs), 2, errs)
        self.assertIn("rolex-submariner-124060", errs[0])
        self.assertIn("timestamps", errs[0])
        self.assertIn("'intro'", errs[0])
        self.assertIn("'nan'", errs[1])

    def test_ts_key_uses_the_shared_parser(self):
        self.assertEqual(sorted(["intro", "39:30", "9:05", 61], key=dataset._ts_key),
                         [61, "9:05", "39:30", "intro"])


if __name__ == "__main__":
    unittest.main()
