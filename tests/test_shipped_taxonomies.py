import ast, json, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import taxonomy  # noqa: E402

SHIPPED = ROOT / "plugins" / "teddy-collection" / "taxonomies" / "shipped"
EXPECTED = ("two-watch", "dive", "chronograph", "dress", "gmt", "value")


def load(cat):
    return json.loads((SHIPPED / f"{cat}@1.json").read_text(encoding="utf-8"))


def criteria(t):
    return [c for crits in t["layers"].values() for c in crits]


class TestShippedTaxonomies(unittest.TestCase):
    def test_shipped_set_is_complete(self):
        self.assertEqual(sorted(p.stem for p in SHIPPED.glob("*.json")),
                         sorted(f"{c}@1" for c in EXPECTED))

    def test_shipped_valid(self):
        for cat in EXPECTED:
            with self.subTest(cat=cat):
                t = load(cat)
                self.assertEqual(taxonomy.validate(t), [])
                self.assertEqual(taxonomy.run_checks(t), [])
                self.assertEqual(t["id"], f"shipped:{cat}@1")
                self.assertEqual(t["label"], "provisional")
                self.assertIn("buyer", t["paradigm"])
                registry = {s["url"]: s for s in t["sources"]}
                for s in t["sources"]:
                    for k in ("url", "title", "publisher", "date", "checked"):
                        self.assertIn(k, s, f"{cat}: source {s.get('url')} lacks {k}")
                    self.assertTrue(s["url"].startswith("https://"), s["url"])
                cited = set()
                for c in criteria(t):
                    self.assertTrue(c["sources"], f"{cat}.{c['key']} has no source")
                    for u in c["sources"]:
                        self.assertIn(u, registry, f"{cat}.{c['key']} cites unlisted {u}")
                    cited.update(c["sources"])
                    if c["check"]["type"] == "deterministic":
                        tree = ast.parse(c["check"]["rule"], mode="eval")
                        for field in {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}:
                            self.assertIn(field, t["spec_fields"],
                                          f"{cat}.{c['key']} reads undocumented field {field}")
                for f in t.get("coherence", []):
                    for u in f["sources"]:
                        self.assertIn(u, registry, f"{cat}: coherence cites unlisted {u}")
                    cited.update(f["sources"])
                if "brief" in t:
                    cited.add(t["brief"]["url"])
                self.assertEqual(cited, set(registry), f"{cat}: registry and citations differ")
                keys = [c["key"] for c in criteria(t)]
                self.assertEqual(len(keys), len(set(keys)), f"{cat}: duplicate keys")

    def test_researched_sets_have_six_criteria(self):
        for cat in EXPECTED[1:]:
            with self.subTest(cat=cat):
                self.assertGreaterEqual(len(criteria(load(cat))), 6)

    def test_two_watch_counts(self):
        t = load("two-watch")
        self.assertEqual([len(t["layers"][k]) for k in ("wearer", "watch", "pair")], [6, 9, 7])
        self.assertEqual(len(t["sources"]), 10)

    def test_teddy_principles_are_dated_and_linked(self):
        for cat in EXPECTED:
            with self.subTest(cat=cat):
                for p in load(cat).get("teddy_principles", []):
                    self.assertRegex(p["video"], r"^[A-Za-z0-9_-]{11}$")
                    self.assertRegex(p["timestamp"], r"^\d+:\d\d$")
                    m, s = p["timestamp"].split(":")
                    self.assertTrue(p["url"].endswith(f"v={p['video']}&t={int(m) * 60 + int(s)}s"),
                                    p["url"])

    def test_resolves_through_library(self):
        for cat in EXPECTED:
            with self.subTest(cat=cat):
                self.assertEqual(taxonomy.get(f"shipped:{cat}@1")["category"], cat)


if __name__ == "__main__":
    unittest.main()
