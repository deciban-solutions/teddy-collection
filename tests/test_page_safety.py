"""Task 9 review round 1: script breakout, URL schemes, fragment allow-list, CSS scoping,
bare-number scope and the router's bad-hash fallback."""
import json, re, shutil, sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import pages, sanitize  # noqa: E402
from test_pages import FFMPEG, Home, appearance, make_image, video, watch  # noqa: E402


def view(html, pid):
    return html.split(f'id="v-{pid}"', 1)[1].split('<section class="view"', 1)[0]


def script_of(html):
    return re.search(r"<script>(.*?)</script>", html, re.S).group(1)


class TestSafeUrl(unittest.TestCase):
    def test_schemes(self):
        self.assertEqual(sanitize.safe_url("https://a.example/x?y=1"), "https://a.example/x?y=1")
        self.assertEqual(sanitize.safe_url("http://a.example"), "http://a.example")
        for bad in ("javascript:alert(1)", " JavaScript:alert(1)", "data:text/html,x",
                    "vbscript:x", "//evil.example/x", "img/a.jpg", "", None, "java\tscript:x"):
            self.assertIsNone(sanitize.safe_url(bad), bad)

    def test_img_paths(self):
        self.assertEqual(sanitize.safe_url("img/a-1.jpg", allow_img=True), "img/a-1.jpg")
        for bad in ("img/../secret.jpg", "img/a/../../b.jpg", "/img/a.jpg", "https://x/a.jpg",
                    "data:image/png;base64,AAAA", "img/"):
            self.assertIsNone(sanitize.safe_url(bad, allow_img=True), bad)

    def test_js_string(self):
        s = sanitize.js_string('</script><img src=x onerror=alert(1)>&  ')
        for ch in ("<", ">", "&", " ", " "):
            self.assertNotIn(ch, s)
        self.assertEqual(json.loads(s), '</script><img src=x onerror=alert(1)>&  ')


class TestScriptBreakout(Home):
    def test_title_cannot_close_script(self):
        evil = "</script><img src=x onerror=alert(1)>"
        self.save([video("v1", "2026-01-05", title=evil)], [watch("a")], [appearance("v1", "a")])
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertEqual(html.count("</script>"), 1)
        self.assertNotIn("<img src=x", html)
        self.assertNotIn("</script><", script_of(html))


class TestDataUrls(Home):
    def test_unsafe_dataset_urls_render_without_links(self):
        w = watch("a", sources=[{"url": "javascript:alert(1)", "kind": "brand",
                                 "checked_at": "2026-11-14", "match": True},
                                {"url": "data:text/html,<b>x</b>", "kind": "dealer",
                                 "checked_at": "2026-11-14", "match": True}])
        self.save([video("v1", "2026-01-05", url="javascript:alert(2)")], [w],
                  [appearance("v1", "a")])
        reg = {"parent": {"url": "javascript:alert(3)", "updated": "x"},
               "children": [{"video_ids": ["v1"], "url": "data:text/html,x", "type": "list",
                             "published": "2026-11-14", "build": "", "hashes": {}}]}
        (self.tmp / "home" / "registry.json").write_text(json.dumps(reg))
        pages.build_child(self.run_dir, ["v1"], "list", {})
        parent = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        for html in (self.built(), parent):
            self.assertNotRegex(html.lower(), r'(href|src)="\s*(javascript|data|vbscript):')
        self.assertIn("Video v1", self.built())

    def test_credited_photo_bad_source_url(self):
        if not FFMPEG:
            self.skipTest("ffmpeg not installed")
        img = self.tmp / "c.jpg"
        make_image(img, "200x150")
        photo = {"path": str(img), "kind": "credited", "credit": "Press",
                 "source_url": "javascript:alert(1)"}
        self.save([video("v1", "2026-01-05")], [watch("a", photo)], [appearance("v1", "a")])
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertIn("Press", html)
        self.assertNotIn("javascript:", html)


class TestFragmentAllowList(Home):
    def setUp(self):
        super().setUp()
        self.one_video()

    def build(self, html, page="viewers"):
        self.fragment(page, html)
        pages.build_child(self.run_dir, ["v1"], "list", {})
        return view(self.built(), page)

    def refused(self, html, name):
        self.fragment("viewers", html)
        with self.assertRaises(ValueError) as cm:
            pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertIn("viewers", str(cm.exception))
        self.assertIn(name, str(cm.exception))

    def test_event_handlers_dropped(self):
        body = self.build('<p onclick="alert(1)" ONMOUSEOVER=\'x()\' class="note">Hi</p>')
        self.assertIn('<p class="note">Hi</p>', body)
        self.assertNotIn("alert", body)
        self.assertNotIn("x()", body)

    def test_javascript_href_unlinked(self):
        body = self.build('<p><a href="javascript:alert(1)">click</a> '
                          '<a href="https://ok.example/">ok</a></p>')
        self.assertNotIn("javascript:", body)
        self.assertIn("click", body)
        self.assertIn('href="https://ok.example/"', body)

    def test_refused_elements(self):
        for tag in ("iframe", "object", "embed", "link", "meta", "form", "input", "button",
                    "base", "script", "svg"):
            self.refused(f"<p>x</p><{tag} src=\"https://e.example\"></{tag}>", tag)

    def test_unknown_element_refused(self):
        self.refused("<marquee>x</marquee>", "marquee")

    def test_single_quoted_external_src_refused(self):
        self.refused("<img src='https://evil.example/a.jpg' alt='x'>", "img")

    def test_srcset_dropped(self):
        if not FFMPEG:
            self.skipTest("ffmpeg not installed")
        (self.run_dir / "img").mkdir()
        make_image(self.run_dir / "img" / "w.jpg", "200x150")
        body = self.build('<img src="img/w.jpg" srcset="https://evil.example/a.jpg 2x" alt="w">')
        self.assertNotIn("srcset", body)
        self.assertNotIn("evil.example", body)
        self.assertIn('src="img/frag-w.jpg"', body)

    def test_parent_path_img_refused(self):
        self.refused('<img src="img/../../secret.jpg" alt="x">', "img")

    def test_style_attrs_dropped(self):
        body = self.build('<div style="background:url(https://e.example/a.png)">a</div>'
                          '<div STYLE="color: red">b</div>')
        self.assertNotIn("url(", body)
        self.assertNotIn("style=", body.lower())

    def test_text_is_reescaped(self):
        body = self.build("<p>a &lt;script&gt; b &amp; c</p>")
        self.assertIn("a &lt;script&gt; b &amp; c", body)

    def test_allowed_markup_kept(self):
        body = self.build('<section><h2>T</h2><table><tr><td data-spec>x</td></tr></table>'
                          '<details><summary>s</summary><p><em>e</em><br></p></details></section>')
        for frag in ("<h2>T</h2>", "<td data-spec", "<summary>s</summary>", "<br>"):
            self.assertIn(frag, body)


class TestFragmentCss(Home):
    def setUp(self):
        super().setUp()
        self.one_video()

    def styles(self):
        return re.search(r"<style>(.*?)</style>", self.built(), re.S).group(1)

    def test_style_block_refused(self):
        for css in ('<style media="screen">.zz { color: red }</style>',
                    "<style>@import url(https://e.example/x.css); p{}</style>",
                    "<STYLE>p{}</STYLE>"):
            self.fragment("viewers", css + '<p class="zz">a</p>')
            with self.assertRaises(ValueError) as cm:
                pages.build_child(self.run_dir, ["v1"], "list", {})
            self.assertIn("viewers", str(cm.exception))
            self.assertIn("style", str(cm.exception).lower())

    def test_at_rules_scoped_and_keyframes_prefixed(self):
        css = ("@supports (display: grid) { .g { display: grid } }"
               "@container (min-width: 400px) { .c { color: red } }"
               "@layer base { .l { color: blue } }"
               "@keyframes spin { from { opacity: 0 } to { opacity: 1 } }"
               ".s { animation: spin 1s; }")
        out = sanitize.scope_css(css, "viewers")
        for sel in ("#v-viewers .g", "#v-viewers .c", "#v-viewers .l", "#v-viewers .s"):
            self.assertIn(sel, out)
        self.assertIn("@keyframes viewers-spin", out)
        self.assertIn("animation: viewers-spin 1s", out)
        self.assertNotIn("#v-viewers from", out)


class TestBareNumberScope(Home):
    def test_dataset_text_with_percent_builds(self):
        self.save([video("v1", "2026-01-05", title="100% Worth It")],
                  [watch("a", basis="dial reads 100% legible")], [appearance("v1", "a")])
        pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertIn("100% Worth It", self.built())
        pages.build_parent()

    def test_fragment_percent_still_fails(self):
        self.save([video("v1", "2026-01-05", title="100% Worth It")], [watch("a")],
                  [appearance("v1", "a")])
        self.fragment("viewers", "<p>62% agreed</p>")
        with self.assertRaises(pages.BareNumberError) as cm:
            pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertIn("viewers", str(cm.exception))

    def test_template_prose_checked(self):
        self.one_video()
        tpl = pages.TEMPLATES / "pages" / "viewers.html"
        tmp = self.tmp / "templates"
        shutil.copytree(pages.TEMPLATES, tmp)
        p = tmp / "pages" / "viewers.html"
        p.write_text(tpl.read_text(encoding="utf-8").replace("Viewer pulse", "Viewer pulse, 50% coded"),
                     encoding="utf-8")
        old = pages.TEMPLATES
        pages.TEMPLATES = tmp
        self.addCleanup(setattr, pages, "TEMPLATES", old)
        with self.assertRaises(pages.BareNumberError):
            pages.build_child(self.run_dir, ["v1"], "list", {})


class TestRouter(Home):
    def test_bad_hash_falls_back(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        js = script_of(self.built())
        self.assertRegex(js, r"try\s*\{[^}]*decodeURIComponent")
        self.assertIn("catch", js)



class TestRound2(Home):
    """Task 9 re-review findings A-D."""

    def setUp(self):
        super().setUp()
        self.one_video()

    def refused(self, html, *needles):
        self.fragment("viewers", html)
        with self.assertRaises(ValueError) as cm:
            pages.build_child(self.run_dir, ["v1"], "list", {})
        msg = str(cm.exception)
        self.assertIn("viewers", msg)
        for n in needles:
            self.assertIn(n, msg)
        return msg

    def build(self, html):
        self.fragment("viewers", html)
        pages.build_child(self.run_dir, ["v1"], "list", {})
        return self.built()

    # A: style breakout
    def test_style_breakout_probe_refused(self):
        self.refused("<style>p{x:</style/><script>alert(1)</script>}</style><p>ok</p>")

    def test_style_breakout_variants_refused(self):
        for end in ("</STYLE >", "</style x>", "</style/>", "</style\n>"):
            self.refused(f"<style>p{{x:{end}<img src=x onerror=alert(1)>}}</style><p>ok</p>")

    def test_script_anywhere_refused(self):
        self.refused("<style>p{content:'<ScRiPt'}</style><p>a</p>", "script")

    def test_lt_in_css_refused(self):
        self.refused("<style>p::after{content:'<b>'}</style><p>a</p>", "<")

    # B: data-src traversal and src name validation
    def test_data_src_not_treated_as_image(self):
        outside = self.tmp / "abs"
        outside.mkdir()
        (outside / "outside.jpg").write_bytes(b"\xff\xd8secret")
        html = self.build(f'<p data-src="img/{outside}/outside.jpg">x</p>')
        self.assertFalse(list((self.run_dir / "build").rglob("*outside*")))
        self.assertNotIn("secret", "".join(p.read_bytes().decode("latin-1")
                                           for p in (self.run_dir / "build").rglob("*.jpg")))
        self.assertIn("x</p>", html)

    def test_src_dotdot_refused(self):
        self.refused('<img src="img/../x.jpg" alt="x">', "img")

    def test_src_subfolder_refused(self):
        self.refused('<img src="img/a/b.jpg" alt="x">', "img")

    # C: attributes dropped from fragments
    def test_promoted_attributes_dropped(self):
        html = self.build('<table background="https://e.example/a.png"><tr><td>a</td></tr></table>'
                          '<a href="https://ok.example/" ping="https://e.example/p">l</a>'
                          '<div data-zoom="https://e.example/z.jpg">z</div><a name="n">n</a>')
        body = view(html, "viewers")
        for attr in ("background=", "ping=", "data-zoom=", "name="):
            self.assertNotIn(attr, body, attr)

    # D: fragment CSS
    def test_css_external_url_refused(self):
        self.refused("<style>p{background:url(https://evil.example/x)}</style><p>a</p>", "style")
        self.refused("<style>p{background:url('//evil.example/x')}</style><p>a</p>", "style")
        self.refused('<style>p{background-image:image-set("https://evil.example/x" 1x)}</style><p>a</p>')

    def test_css_escaped_at_rule_refused(self):
        self.refused(r"<style>@\69mport 'https://evil.example/x.css'; p{}</style><p>a</p>")

    def test_css_quoted_at_text_unchanged(self):
        out = sanitize.scope_css('.a{content:"@foo bar";}', "viewers")
        self.assertIn('content:"@foo bar";', out)
        self.assertIn("#v-viewers .a", out)
        out = sanitize.scope_css(".b{content:'{ not a block }'}", "viewers")
        self.assertIn("content:'{ not a block }'", out)


class TestRound3(Home):
    """Task 9 re-review round 3: fragments carry no CSS (D'), class values restricted."""

    def setUp(self):
        super().setUp()
        self.one_video()

    def build(self, html):
        self.fragment("viewers", html)
        pages.build_child(self.run_dir, ["v1"], "list", {})
        return view(self.built(), "viewers")

    def test_desync_probes_refused(self):
        probes = [r"<style>a{color:red; /* ' */ } p{background:u\72l(https://evil.example/x)} b{content:'x'}</style><p>ok</p>",
                  "<style>a{color:red; /* ' */ } p{background-image:image-set('https://evil.example/x' 1x)} "
                  "b{content:'x'}</style><p>ok</p>"]
        for html in probes:
            self.fragment("viewers", html)
            with self.assertRaises(ValueError) as cm:
                pages.build_child(self.run_dir, ["v1"], "list", {})
            self.assertIn("viewers", str(cm.exception))

    def test_inline_style_probes_lose_style(self):
        body = self.build(r'<p style="background:u\72l(https://e/x)">a</p>'
                          "<p style=\"background-image:image-set('https://e/x' 1x)\">b</p>")
        self.assertNotIn("style=", body)
        self.assertNotIn("https://e/x", body)
        self.assertIn(">a</p>", body)

    def test_class_values(self):
        body = self.build('<p class="note">a</p><p class="a;b">b</p><p class="callout wide">c</p>')
        self.assertIn('<p class="note">a</p>', body)
        self.assertIn("<p>b</p>", body)
        self.assertIn('<p class="callout wide">c</p>', body)

    def test_fragment_classes_defined_in_shell(self):
        shell = (pages.TEMPLATES / "shell.html").read_text(encoding="utf-8")
        self.assertTrue(sanitize.FRAGMENT_CLASSES)
        for c in sanitize.FRAGMENT_CLASSES:
            self.assertRegex(shell, r"\.view (\S+ )?[\w.]*\." + re.escape(c) + r"\b", c)


class TestFinalReviewSanitizer(unittest.TestCase):
    """Final review 3, 11, 12 (and ledger Task 9 must-fix items)."""

    def clean(self, html):
        return sanitize.clean_fragment("t", html)

    def test_unmatched_end_tags_dropped(self):
        # 3: a stray </div> or </section> would close the view early.
        self.assertEqual(self.clean("<p>a</p></div></section><p>b</p>"), "<p>a</p><p>b</p>")
        self.assertEqual(self.clean("<div><p>x</div>"), "<div><p>x</p></div>")

    def test_open_tags_closed_at_end(self):
        self.assertEqual(self.clean("<section><div><p>x"), "<section><div><p>x</p></div></section>")

    def test_balanced_input_unchanged(self):
        html = '<div class="note"><p>a <b>b</b><br>c</p><ul><li>x</li></ul></div>'
        self.assertEqual(self.clean(html), html)

    def test_attribute_allow_list(self):
        # 11: per-tag allow-list; attributionsrc, ping, onclick and unknown attributes go.
        out = self.clean('<a href="https://a.example/" attributionsrc="https://t.example/" '
                         'ping="https://t.example/p" onclick="x()" foo="bar" title="t">l</a>')
        self.assertEqual(out, '<a href="https://a.example/" title="t">l</a>')
        out = self.clean('<img src="img/a.jpg" alt="A" width="10" height="5" loading="lazy" '
                         'attributionsrc="" decoding="async">')
        self.assertEqual(out, '<img src="img/a.jpg" alt="A" width="10" height="5">')
        out = self.clean('<p href="https://a.example/" datetime="2026" data-num="k" '
                         'data-zoom="img/a.jpg" data-x="1" colspan="2" data-spec>x</p>')
        self.assertEqual(out, '<p data-num="k" colspan="2" data-spec="">x</p>')
        self.assertEqual(self.clean('<time datetime="2026-11-15">d</time>'),
                         '<time datetime="2026-11-15">d</time>')

    def test_cite_url_rules(self):
        self.assertEqual(self.clean('<q cite="https://a.example/">x</q>'),
                         '<q cite="https://a.example/">x</q>')
        self.assertEqual(self.clean('<blockquote cite="javascript:alert(1)">x</blockquote>'),
                         "<blockquote>x</blockquote>")
        self.assertEqual(self.clean('<abbr cite="https://a.example/" title="T">x</abbr>'),
                         '<abbr cite="https://a.example/" title="T">x</abbr>')
        self.assertEqual(self.clean('<p cite="https://a.example/">x</p>'), "<p>x</p>")

    def test_shell_class_names_refused(self):
        # 12: fragment classes come from FRAGMENT_CLASSES only, so no shell name passes.
        for shell_cls in ("view", "side", "main", "brand", "zoom", "zoomable", "shell"):
            self.assertEqual(self.clean(f'<div class="{shell_cls}">x</div>'), "<div>x</div>", shell_cls)
        self.assertEqual(self.clean('<div class="note view wide">x</div>'),
                         '<div class="note wide">x</div>')


class TestRouterTopLevelViews(Home):
    def test_router_selects_main_views_only(self):
        # 12: a nested .view can never be treated as a page by the router.
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        js = script_of(self.built())
        self.assertIn("querySelectorAll('.main > .view')", js)
        self.assertIn("closest('.main > .view')", js)
        self.assertNotIn("querySelectorAll('.view')", js)


if __name__ == "__main__":
    unittest.main()
