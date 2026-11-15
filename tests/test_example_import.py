"""The shipped two-watch example: import into a dataset and registry, then build the parent."""
import contextlib
import io
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "teddy-collection"
sys.path.insert(0, str(PLUGIN / "lib"))
sys.path.insert(0, str(PLUGIN / "scripts"))
from teddycoll import dataset, importer, pages, publish, taxonomy  # noqa: E402
import teddy  # noqa: E402

TITLE = "Watch Shopping with Watch Content Creators in Our Store"
VID = "bDePE9oVcV4"
FFMPEG = shutil.which("ffmpeg")


class ImportBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": str(self.tmp / "home")})
        env.start()
        self.addCleanup(env.stop)

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = teddy.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()


class TestImport(ImportBase):
    def test_records_are_valid_and_complete(self):
        recs = json.loads((PLUGIN / "examples" / "two-watch-challenge" / "records.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(len(recs["videos"]), 1)
        self.assertEqual(recs["videos"][0]["title"], TITLE)
        self.assertEqual(recs["videos"][0]["duration"], 3007)
        roles = [a["role"] for a in recs["appearances"]]
        self.assertEqual((roles.count("picked"), roles.count("worn")), (12, 6))
        self.assertEqual(dataset.validate(recs), [])
        for a in recs["appearances"]:
            self.assertTrue(a.get("group"), a)
        for w in recs["watches"]:
            for p in w["photos"]:
                self.assertTrue((PLUGIN / "examples" / "two-watch-challenge" / p["path"]).is_file(), p)

    def test_import_twice_adds_nothing(self):
        r1 = importer.import_example("two-watch-challenge", url="https://example.com/a")
        def state():
            reg = publish.load_registry()
            for c in reg["children"]:
                c.pop("published")  # today's date; not part of idempotence
            return dataset.load(), reg
        snap = state()
        r2 = importer.import_example("two-watch-challenge", url="https://example.com/a")
        self.assertEqual(snap, state())
        self.assertEqual((len(snap[0]["videos"]), len(snap[0]["watches"]),
                          len(snap[0]["appearances"]), len(snap[1]["children"])), (1, 18, 18, 1))
        self.assertEqual(r1["watches"], r2["watches"])

    def test_appearance_timestamps_sort_by_time_not_text(self):
        ds = {"videos": [], "appearances": [], "watches": []}
        for ts in (["39:30"], ["9:05"]):
            dataset.add_appearance(ds, {"video_id": "v", "watch_id": "w", "role": "picked", "timestamps": ts})
        self.assertEqual(ds["appearances"][0]["timestamps"], ["9:05", "39:30"])

    def test_registry_entry(self):
        importer.import_example("two-watch-challenge", url="https://example.com/a")
        c = publish.registry_find(VID)
        self.assertEqual((c["url"], c["type"], c["video_ids"]), ("https://example.com/a", "contest", [VID]))
        self.assertEqual(c["taxonomy"], {"category": "two-watch", "version_id": "shipped:two-watch@1",
                                         "label": "provisional"})
        self.assertTrue((Path(c["build"]) / "index.html").is_file())
        taxonomy.get(c["taxonomy"]["version_id"])  # the version id resolves

    def test_without_url_registers_no_link_and_rerun_keeps_a_url(self):
        importer.import_example("two-watch-challenge")
        self.assertIsNone(publish.registry_find(VID)["url"])
        importer.import_example("two-watch-challenge", url="https://example.com/a")
        importer.import_example("two-watch-challenge")
        self.assertEqual(publish.registry_find(VID)["url"], "https://example.com/a")

    def test_own_entry_keeps_hashes_and_published_date_and_takes_new_url(self):
        importer.import_example("two-watch-challenge", url="https://example.com/a")
        reg = publish.load_registry()
        reg["children"][0].update(hashes={"overview": "abc"}, published="2026-01-01")
        publish._save_registry(reg)
        importer.import_example("two-watch-challenge", url="https://example.com/b")
        c = publish.registry_find(VID)
        self.assertEqual((c["hashes"], c["published"], c["url"]),
                         ({"overview": "abc"}, "2026-01-01", "https://example.com/b"))

    def test_existing_user_child_for_the_video_is_left_untouched(self):
        mine = self.tmp / "mybuild"
        mine.mkdir()
        publish.registry_add("child", [VID], "https://example.com/mine", mine, {"overview": "h"},
                             type="contest", taxonomy=None)
        before = publish.load_registry()
        code, out, err = self.cli("import-example", "two-watch-challenge", "--url", "https://example.com/a")
        self.assertEqual(code, 0)
        self.assertIn("notice", err)
        self.assertEqual(publish.load_registry(), before)
        self.assertEqual(len(dataset.load()["watches"]), 18)  # records still merged

    def test_prices_name_a_source_that_matches_their_type(self):
        recs = json.loads((PLUGIN / "examples" / "two-watch-challenge" / "records.json")
                          .read_text(encoding="utf-8"))
        for w in recs["watches"]:
            for p in w["price_history"]:
                self.assertIsNotNone(p["amount"])
                if p["source_type"] == "dealer":
                    self.assertNotIn("press.", p["url"])
                    self.assertNotIn("grand-seiko.com", p["url"])

    def test_unknown_example_exits_2(self):
        for bad in ("nope", "../two-watch-challenge", ""):
            code, _, err = self.cli("import-example", bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("error", err)

    def test_cli_import_prints_counts(self):
        code, out, _ = self.cli("import-example", "two-watch-challenge", "--url", "https://example.com/a")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual((res["watches"], res["appearances"], res["videos"]), (18, 18, 1))

    def test_refuses_a_bad_url_scheme(self):
        code, _, err = self.cli("import-example", "two-watch-challenge", "--url", "javascript:alert(1)")
        self.assertEqual(code, 2)
        self.assertEqual(dataset.load()["watches"], [])

    def test_no_owner_artifact_url_shipped(self):
        for f in list(PLUGIN.rglob("*")) + [ROOT / "README.md"]:
            if f.is_file() and f.suffix in (".py", ".json", ".html", ".md"):
                self.assertNotRegex(f.read_text(encoding="utf-8", errors="ignore"), r"claude\.ai/artifact/[A-Za-z0-9]{10,}", f)


@unittest.skipUnless(FFMPEG, "ffmpeg is needed to build pages")
class TestParent(ImportBase):
    def build(self, **kw):
        importer.import_example("two-watch-challenge", **kw)
        build = pages.build_parent()
        manifest = json.loads((build / "manifest.json").read_text(encoding="utf-8"))
        return (build / "index.html").read_text(encoding="utf-8"), manifest

    def test_import_then_parent_builds(self):
        html, manifest = self.build()
        self.assertIn(TITLE, html)
        self.assertEqual(html.count('<article class="wcard">'), 18)  # 12 picked + 6 worn
        self.assertEqual(manifest.get("missing_photos"), [])

    def test_parent_with_no_url_shows_the_title_unlinked(self):
        html, _ = self.build()
        kid = re.search(r'<section class="kind-group">.*?</section>', html, re.S).group(0)
        self.assertIn(TITLE, kid)
        self.assertNotIn("<a ", kid)
        self.assertNotIn("None", kid)

    def test_parent_with_url_links_the_child(self):
        html, _ = self.build(url="https://example.com/a")
        kid = re.search(r'<section class="kind-group">.*?</section>', html, re.S).group(0)
        self.assertIn('href="https://example.com/a"', kid)


if __name__ == "__main__":
    unittest.main()
