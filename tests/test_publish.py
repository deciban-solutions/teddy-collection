import json, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import dataset, pages, publish  # noqa: E402
from test_pages import FFMPEG, Home, appearance, make_image, video, watch  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"


class TestPublish(Home):
    def cli(self, *a):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *a], capture_output=True, text=True,
                              env={"TEDDY_COLLECTION_HOME": str(self.tmp / "home")})

    def fake_build(self, name="b"):
        b = self.tmp / name
        (b / "img").mkdir(parents=True)
        (b / "img" / "x.jpg").write_bytes(b"jpg")
        (b / "img" / "y.jpg").write_bytes(b"jpg2")
        (b / "index.html").write_text('<section class="view" id="v-overview"><img src="img/x.jpg">'
                                      '<img src="img/y.jpg"></section>', encoding="utf-8")
        (b / "manifest.json").write_text(json.dumps({"kind": "child", "video_ids": ["bDePE9oVcV4"],
                                                     "type": "list"}))
        return b

    def test_rerun_detected(self):
        b = self.fake_build()
        publish.registry_add("child", ["bDePE9oVcV4"], "https://claude.ai/artifact/x", b, {"v-overview": "h"},
                             type="list")
        found = publish.registry_find("bDePE9oVcV4")
        self.assertEqual(found["url"], "https://claude.ai/artifact/x")
        self.assertIsNone(publish.registry_find("other"))
        self.assertEqual(self.cli("check-new", "bDePE9oVcV4").returncode, 3)
        self.assertEqual(self.cli("check-new", "bDePE9oVcV4", "--rebuild").returncode, 0)
        self.assertEqual(self.cli("check-new", "fresh").returncode, 0)

    def test_registry_add_replaces_same_set_and_sets_parent(self):
        b = self.fake_build()
        publish.registry_add("child", ["a", "b"], "u1", b, {}, type="list")
        publish.registry_add("child", ["c"], "u2", b, {}, type="list")
        publish.registry_add("child", ["b", "a"], "u3", b, {}, type="list")
        kids = publish.load_registry()["children"]
        self.assertEqual([k["url"] for k in kids], ["u3", "u2"])
        publish.registry_add("parent", [], "pu", b, {})
        reg = publish.load_registry()
        self.assertEqual(reg["parent"]["url"], "pu")
        self.assertEqual(pages._load_registry(), reg)
        self.assertEqual(sorted(p.name for p in (self.tmp / "home").glob("*.tmp")), [])

    def test_registry_cli_add_find(self):
        b = self.fake_build()
        r = self.cli("registry", "add", "child", str(b), "--url", "https://x/y")
        self.assertEqual(r.returncode, 0, r.stderr)
        f = self.cli("registry", "find", "bDePE9oVcV4")
        self.assertEqual(f.returncode, 0)
        self.assertEqual(json.loads(f.stdout)["type"], "list")
        self.assertIn("v-overview", json.loads(f.stdout)["hashes"])

    def test_corrupt_registry_exits_2(self):
        (self.tmp / "home").mkdir(exist_ok=True)
        (self.tmp / "home" / "registry.json").write_text("{not json")
        r = self.cli("check-new", "x")
        self.assertEqual(r.returncode, 2)
        self.assertIn("registry.json", r.stderr)
        self.assertNotIn("Traceback", r.stderr)
        (self.tmp / "home" / "registry.json").write_text("[1]")
        with self.assertRaises(ValueError):
            publish.load_registry()

    def test_corrupt_registry_on_build_paths_exits_2(self):
        # Final review 13: invalid JSON already exited 2; a registry of the wrong shape (a child
        # or parent that is not an object) reached the build paths as a raw traceback.
        b = self.fake_build()
        self.save([video("v1", "2026-01-05")], [watch("a")], [appearance("v1", "a")])
        for bad in ("{not json", '{"children": [1, "x"]}', '{"parent": "oops", "children": []}'):
            (self.tmp / "home" / "registry.json").write_text(bad)
            for args in (("build-child", str(self.run_dir), "--type", "list", "--videos", "v1"),
                         ("build-parent",),
                         ("registry", "add", "child", str(b), "--url", "https://claude.ai/artifact/x"),
                         ("check-new", "v1")):
                r = self.cli(*args)
                self.assertEqual(r.returncode, 2, (bad, args, r.stderr[-300:]))
                self.assertIn("registry.json", r.stderr)
                self.assertNotIn("Traceback", r.stderr)

    def test_relative_build_resolved(self):
        b = self.fake_build()
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "publish-prepare", b.name],
                           capture_output=True, text=True, cwd=self.tmp,
                           env={"TEDDY_COLLECTION_HOME": str(self.tmp / "home")})
        self.assertTrue(Path(json.loads(r.stdout)["file_path"]).is_absolute(), r.stdout)
        import os
        old = os.getcwd()
        os.chdir(self.tmp)
        try:
            e = publish.registry_add("child", ["rel"], "u", b.name, {})
        finally:
            os.chdir(old)
        self.assertEqual(e["build"], str(b.resolve()))

    def test_files_map_relative_keys(self):
        b = self.fake_build()
        fm = publish.files_map(b)
        self.assertEqual(sorted(fm), ["img/x.jpg", "img/y.jpg"])
        for k, v in fm.items():
            self.assertFalse(k.startswith("/"))
            self.assertTrue(Path(v).is_absolute() and Path(v).is_file())
        out = json.loads(self.cli("publish-prepare", str(b)).stdout)
        self.assertEqual(out["file_path"], str(b / "index.html"))
        self.assertEqual(sorted(out["files"]), ["img/x.jpg", "img/y.jpg"])

    def test_publish_prepare_root_and_relative_files(self):
        # G13: a large publish can pass root + relative paths instead of the absolute map.
        b = self.fake_build()
        out = json.loads(self.cli("publish-prepare", str(b)).stdout)
        self.assertEqual(out["root"], str(b.resolve()))
        self.assertEqual(out["relative_files"], ["img/x.jpg", "img/y.jpg"])

    def test_series_candidates_cli(self):
        # G14: the Step 11.1 check is a subcommand, not an inline one-liner.
        self.save([video("old", "2025-01-01", title="What $500 Buys You in Watches in 2025"),
                   video("new", "2026-01-01", title="What $500 Buys You in Watches in 2026")], [], [])
        publish.registry_add("child", ["old"], "https://claude.ai/artifact/O", self.fake_build(), {})
        rec = self.tmp / "records.json"
        rec.write_text(json.dumps({"videos": [{"id": "new", "title": "What $500 Buys You in Watches in 2026"}]}))
        r = self.cli("series-candidates", str(rec))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual([c["video_id"] for c in json.loads(r.stdout)], ["old"])

    @unittest.skipUnless(FFMPEG, "ffmpeg needed")
    def test_parent_finds_photos_of_an_unregistered_run(self):
        # F12: a watch added by dataset-add before its child is registered still has its photo.
        run = self.tmp / "home" / "runs" / "20261115T000000_v1"
        (run / "img").mkdir(parents=True)
        make_image(run / "img" / "a.jpg", "400x300")
        self.save([video("v1", "2026-01-05")],
                  [watch("a", {"kind": "frame", "path": "img/a.jpg", "at": "1:00"})],
                  [appearance("v1", "a", 1)])
        b = pages.build_parent()
        self.assertEqual(json.loads((b / "manifest.json").read_text())["missing_photos"], [])

    def test_export_local_self_contained(self):
        b = self.fake_build()
        dest = publish.export_local(b, self.tmp / "out")
        html = (dest / "index.html").read_text(encoding="utf-8")
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("viewport-fit=cover", html)
        import re
        refs = re.findall(r'src="([^"]+)"', html)
        self.assertEqual(sorted(refs), ["img/x.jpg", "img/y.jpg"])
        for r in refs:
            self.assertTrue((dest / r).is_file(), r)

    @unittest.skipUnless(FFMPEG, "ffmpeg needed")
    def test_export_local_real_build(self):
        img = self.tmp / "p.jpg"
        make_image(img)
        self.save([video("v1", "2026-01-05")], [watch("a", photo={"path": str(img)}), watch("b")],
                  [appearance("v1", "a", 1), appearance("v1", "b", 2)])
        b = pages.build_child(self.run_dir, ["v1"], "list", {})
        dest = publish.export_local(b, self.tmp / "out")
        import re
        for r in re.findall(r'src="(img/[^"]+)"', (dest / "index.html").read_text(encoding="utf-8")):
            self.assertTrue((dest / r).is_file(), r)

    def test_series_candidates(self):
        self.save([video("old", "2025-01-05", title="What $500 Buys You in Watches in 2025"),
                   video("exp", "2025-02-05", title="What $2,000 Buys You in Watches in 2025"),
                   video("top", "2025-03-05", title="Top Watches of 2025"),
                   video("new", "2026-01-05", title="What $500 Buys You in Watches in 2026")],
                  [], [])
        b = self.fake_build()
        for vid in ("old", "exp", "top", "new"):
            publish.registry_add("child", [vid], f"u-{vid}", b, {}, type="list")
        got = publish.series_candidates({"id": "new", "title": "What $500 Buys You in Watches in 2026"})
        self.assertEqual([c["video_id"] for c in got], ["old"])
        self.assertEqual(publish.series_candidates({"id": "x", "title": "What $2,000 Buys You in Watches in 2026"})[0]["video_id"], "exp")
        self.assertEqual([c["video_id"] for c in publish.series_candidates({"id": "t", "title": "Top Watches of 2026"})], ["top"])
        self.assertEqual(publish.series_candidates({"id": "z", "title": "Something else 2026"}), [])


if __name__ == "__main__":
    unittest.main()
