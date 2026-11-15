import json, subprocess, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import freeze, pages  # noqa: E402
from test_pages import Home, appearance, video, watch  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"


class TestFrozen(Home):
    def build(self):
        self.save([video("v1", "2026-01-05")], [watch("a"), watch("b")],
                  [appearance("v1", "a", 1), appearance("v1", "b", 2)])
        self.fragment("overview", "<p>The short answer is plain.</p>")
        return pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_banner_does_not_break_freeze(self):
        b = self.build()
        rec = freeze.record(b)
        self.assertTrue(rec)
        freeze.set_banner(b, '<div class="note"><p>Updated <b>today</b>.</p></div>')
        freeze.set_today(b, "<p>Price now $400.</p>")
        self.assertIn("Updated", (b / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(freeze.verify(b, rec), [])
        freeze.set_today(b, "<p>Changed.</p>", "overview")
        self.assertEqual(freeze.verify(b, rec), [])

    def test_body_edit_breaks_freeze(self):
        b = self.build()
        rec = freeze.record(b)
        f = b / "index.html"
        f.write_text(f.read_text(encoding="utf-8").replace("short answer is plain",
                                                           "short answer is murky"), encoding="utf-8")
        self.assertEqual(freeze.verify(b, rec), ["v-overview"])

    def test_script_and_style_refused(self):
        b = self.build()
        for bad in ("<script>x</script>", "<STYLE>p{}</STYLE>"):
            with self.assertRaises(ValueError):
                freeze.set_banner(b, bad)
            with self.assertRaises(ValueError):
                freeze.set_today(b, bad)

    def test_unbalanced_injection_refused(self):
        b = self.build()
        rec = freeze.record(b)
        for bad in ("<div>open", "stray</div>", "</section><section>x", "<section>x", "</div><div>"):
            with self.assertRaises(ValueError, msg=bad):
                freeze.set_banner(b, bad)
            with self.assertRaises(ValueError, msg=bad):
                freeze.set_today(b, bad)
        self.assertEqual(freeze.verify(b, rec), [])
        freeze.set_banner(b, "<div><div>ok</div></div>")
        self.assertEqual(freeze.verify(b, rec), [])

    def test_banner_and_today_pass_the_fragment_allow_list(self):
        # Final review 4: banner and today HTML get the fragments' allow-list.
        b = self.build()
        rec = freeze.record(b)
        freeze.set_banner(b, '<p>See <a href="javascript:alert(1)">this</a> '
                             '<a href="https://a.example/" onclick="x()">that</a>'
                             '<img src="img/x.jpg" onerror="alert(2)" alt="x"></p>')
        html = (b / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("javascript:", html)
        self.assertNotIn("onerror", html)
        self.assertNotIn("onclick", html)
        self.assertIn('<a href="https://a.example/">that</a>', html)
        for bad in ('<iframe src="https://e.example/"></iframe>', "<p><iframe></iframe></p>",
                    '<img src="https://e.example/x.png">'):
            with self.assertRaises(ValueError, msg=bad):
                freeze.set_today(b, bad)
        self.assertEqual(freeze.verify(b, rec), [])

    def test_no_views_and_no_slots_fail_loudly(self):
        d = self.tmp / "bare"
        d.mkdir()
        (d / "index.html").write_text("<p>nothing</p>")
        with self.assertRaises(ValueError):
            freeze.record(d)
        with self.assertRaises(ValueError):
            freeze.verify(d, {})
        (d / "index.html").write_text('<section class="view" id="v-a">x</section>')
        self.assertTrue(freeze.record(d))
        with self.assertRaises(ValueError):
            freeze.set_banner(d, "<p>hi</p>")
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "freeze", "banner", str(d), str(d / "index.html")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_view_open_attribute_variants(self):
        d = self.tmp / "var"
        d.mkdir()
        (d / "index.html").write_text("<section id='v-a' class='x view active'><div data-banner></div>"
                                      "<div data-today></div>body</section>")
        self.assertEqual(list(freeze.record(d)), ["v-a"])

    def test_cli_record_verify_banner(self):
        b = self.build()
        run = lambda *a: subprocess.run([sys.executable, "-I", str(SCRIPT), *a], capture_output=True,
                                        text=True, env={"TEDDY_COLLECTION_HOME": str(self.tmp / "home")})
        r = run("freeze", "record", str(b))
        self.assertEqual(r.returncode, 0, r.stderr)
        hashes = self.tmp / "h.json"
        hashes.write_text(r.stdout)
        note = self.tmp / "note.html"
        note.write_text("<p>hello</p>")
        self.assertEqual(run("freeze", "banner", str(b), str(note)).returncode, 0)
        self.assertEqual(run("freeze", "today", str(b), "all", str(note)).returncode, 0)
        self.assertEqual(run("freeze", "verify", str(b), str(hashes)).returncode, 0)
        f = b / "index.html"
        f.write_text(f.read_text(encoding="utf-8").replace("plain", "vague"), encoding="utf-8")
        v = run("freeze", "verify", str(b), str(hashes))
        self.assertEqual(v.returncode, 1)
        self.assertIn("v-overview", v.stderr)


if __name__ == "__main__":
    unittest.main()
