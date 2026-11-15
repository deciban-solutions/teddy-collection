import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import dataset  # noqa: E402

FRAME = {"path": "p/f.jpg", "kind": "frame"}


def ds_with(video_cards=True, **wkw):
    w = {"id": "w1", "brand": "B", "model": "M", "reference": "1", "category": "dive",
         "confidence": "labelled_on_screen", "basis": "card shown", "photos": [FRAME]}
    w.update(wkw)
    return {"videos": [{"id": "v1", "on_screen_cards": video_cards}],
            "appearances": [{"video_id": "v1", "watch_id": "w1", "role": "picked"}],
            "watches": [w]}


class TestFamilyAndStance(unittest.TestCase):
    def test_family_record_has_no_reference(self):
        # G4/F3: a list names model families; the record says so instead of faking a reference.
        self.assertEqual(dataset.validate(ds_with(family=True, reference=None)), [])
        errs = dataset.validate(ds_with(family=True, reference="SRPD55"))
        self.assertTrue(any("family" in e for e in errs), errs)
        errs = dataset.validate(ds_with(family="yes", reference=None))
        self.assertTrue(any("family" in e for e in errs), errs)

    def test_verdict_stance_values(self):
        # F6: verdict.stance is one of positive, mixed, negative, none.
        ds = ds_with()
        ds["appearances"][0]["verdict"] = {"quote": "q", "stance": "positive"}
        self.assertEqual(dataset.validate(ds), [])
        ds["appearances"][0]["verdict"]["stance"] = "favourable"
        self.assertTrue(any("stance" in e for e in dataset.validate(ds)))


class TestConfidence(unittest.TestCase):
    def test_valid_passes(self):
        self.assertEqual(dataset.validate(ds_with()), [])

    def test_confidence_requires_basis(self):
        self.assertTrue(dataset.validate(ds_with(basis="")))
        self.assertTrue(dataset.validate(ds_with(basis="   ")))
        self.assertTrue(dataset.validate(ds_with(confidence="certain")))
        self.assertTrue(dataset.validate(ds_with(confidence=None)))

    def test_labelled_needs_frame_evidence(self):
        self.assertTrue(dataset.validate(ds_with(photos=[])))
        credited = {"path": "p/c.jpg", "kind": "credited", "credit": "x", "source_url": "u"}
        self.assertTrue(dataset.validate(ds_with(photos=[credited])))
        self.assertEqual(dataset.validate(ds_with(confidence="legible_on_dial", photos=[])), [])

    def test_wrist_only_video_cannot_be_labelled(self):
        errs = dataset.validate(ds_with(video_cards=False))
        self.assertTrue(any("on_screen_cards" in e for e in errs), errs)
        self.assertEqual(dataset.validate(ds_with(video_cards=False, confidence="legible_on_dial")), [])

    def test_labelled_watch_without_appearance_is_refused(self):
        ds = ds_with()
        ds["appearances"] = []
        self.assertTrue(any("no appearance" in e for e in dataset.validate(ds)))

    def test_appearance_with_unknown_video_is_refused(self):
        ds = ds_with()
        ds["appearances"][0]["video_id"] = "ghost"
        errs = dataset.validate(ds)
        self.assertTrue(any("unknown video_id" in e for e in errs), errs)
        ds = ds_with()
        ds["appearances"][0]["watch_id"] = "ghost"
        self.assertTrue(any("unknown watch_id" in e for e in dataset.validate(ds)))


if __name__ == "__main__":
    unittest.main()
