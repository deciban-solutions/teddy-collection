"""Spec §10: a count on a page must equal the dataset; pages read numbers only from script output."""
import json, re, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import pages  # noqa: E402
from test_pages import Home, appearance, video, watch  # noqa: E402


def span(html, key):
    m = re.search(r'<span data-num="%s">([^<]*)</span>' % re.escape(key), html)
    return m and m.group(1)


class TestMetricsFromDataset(Home):
    def setUp(self):
        super().setUp()
        self.save([video("v1", "2026-01-05"), video("v2", "2025-05-05")],
                  [watch("a", confidence="labelled_on_screen"), watch("b"), watch("c"),
                   watch("z", confidence="inferred")],
                  [appearance("v1", "a"), appearance("v1", "b"), appearance("v1", "c"),
                   appearance("v2", "z")])

    def test_child_counts_match_dataset(self):
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = (self.run_dir / "build" / "index.html").read_text(encoding="utf-8")
        nums = json.loads((self.run_dir / "numbers.json").read_text())
        self.assertEqual(nums["data"]["watches"], 3)
        self.assertEqual(nums["data"]["by_confidence"]["labelled_on_screen"], 1)
        self.assertEqual(span(html, "data.watches"), "3")
        gallery = html.split('id="v-gallery"', 1)[1].split('<section class="view"', 1)[0]
        self.assertEqual(gallery.count('class="gcard"'), 3)

    def test_existing_numbers_kept(self):
        self.numbers({"viewers": {"n": 600}})
        pages.build_child(self.run_dir, ["v1"], "list", {})
        nums = json.loads((self.run_dir / "numbers.json").read_text())
        self.assertEqual(nums["viewers"], {"n": 600})

    def test_parent_counts_match_dataset(self):
        html = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        self.assertEqual(span(html, "parent.videos"), "2")
        self.assertEqual(span(html, "parent.watches"), "4")
        self.assertEqual(span(html, "parent.first_upload"), "2025-05-05")

    def test_generated_pages_have_no_bare_numbers(self):
        pages.build_child(self.run_dir, ["v1"], "contest", {})
        html = (self.run_dir / "build" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(pages.check_bare_numbers(html), [])


if __name__ == "__main__":
    unittest.main()
