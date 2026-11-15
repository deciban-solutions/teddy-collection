import json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import dataset, pages, taxonomy  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"
FFMPEG = shutil.which("ffmpeg")


def video(vid, date, type_="list", **kw):
    v = {"id": vid, "url": f"https://youtu.be/{vid}", "title": f"Video {vid}",
         "upload_date": date, "type": type_, "on_screen_cards": True}
    v.update(kw)
    return v


def watch(wid, photo=None, **kw):
    w = {"id": wid, "brand": "Brand", "model": f"Model {wid}", "reference": wid.upper(),
         "category": "dive", "specs": {}, "confidence": "matched_to_specs",
         "basis": "matched to brand page", "status_history": [], "price_history": [],
         "sources": [{"url": f"https://example.com/{wid}", "kind": "brand",
                      "checked_at": "2026-11-14", "match": True}],
         "photos": [photo] if photo else []}
    w.update(kw)
    return w


def appearance(vid, wid, rank=None, price=None, **kw):
    a = {"video_id": vid, "watch_id": wid, "timestamps": [90], "role": "listed", "rank": rank}
    if price is not None:
        a["price_quoted"] = {"amount": price, "currency": "USD"}
    a.update(kw)
    return a


def make_image(path, size="1920x1080"):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"color=c=gray:s={size}", "-vf", "noise=alls=100:allf=t+u",
                    "-frames:v", "1", "-q:v", "2", str(path)], check=True)


class Home(unittest.TestCase):
    """A throwaway data home, empty taxonomy dirs, and a run folder."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": str(self.tmp / "home")})
        env.start()
        self.addCleanup(env.stop)
        old = (taxonomy.SHIPPED_DIR, taxonomy.USER_DIR)
        taxonomy.SHIPPED_DIR, taxonomy.USER_DIR = self.tmp / "shipped", self.tmp / "user"
        self.addCleanup(lambda: setattr(taxonomy, "SHIPPED_DIR", old[0]))
        self.addCleanup(lambda: setattr(taxonomy, "USER_DIR", old[1]))
        self.run_dir = self.tmp / "run"
        self.run_dir.mkdir()

    def save(self, videos, watches, appearances):
        dataset.save({"videos": videos, "watches": watches, "appearances": appearances})

    def fragment(self, page, html):
        d = self.run_dir / "fragments"
        d.mkdir(exist_ok=True)
        (d / f"{page}.html").write_text(html, encoding="utf-8")

    def numbers(self, nums):
        (self.run_dir / "numbers.json").write_text(json.dumps(nums), encoding="utf-8")

    def one_video(self):
        self.save([video("v1", "2026-01-05")], [watch("a"), watch("b")],
                  [appearance("v1", "a", 1), appearance("v1", "b", 2)])

    def built(self):
        return (self.run_dir / "build" / "index.html").read_text(encoding="utf-8")


class TestNumbers(unittest.TestCase):
    def test_num_spans_filled(self):
        out = pages.fill_numbers('<p>τ = <span data-num="tau_judges_expert">x</span></p>',
                                 {"tau_judges_expert": 0.47})
        self.assertIn('<span data-num="tau_judges_expert">0.47</span>', out)
        self.assertNotIn(">x<", out)

    def test_dotted_keys_and_formats(self):
        nums = {"viewers": {"stance": {"agree": 12}}, "infer": {"single": [{"tau": 0.4666}]},
                "label": "n/a"}
        out = pages.fill_numbers('<span data-num="viewers.stance.agree">?</span> '
                                 '<span data-num="infer.single.0.tau">?</span> '
                                 '<span data-num="label">?</span>', nums)
        self.assertIn(">12<", out)
        self.assertIn(">0.47<", out)
        self.assertIn(">n/a<", out)

    def test_unknown_num_key_fails(self):
        with self.assertRaises(KeyError):
            pages.fill_numbers('<span data-num="nope">x</span>', {"other": 1})
        with self.assertRaises(KeyError):
            pages.fill_numbers('<span data-num="infer.single.3.tau">x</span>',
                               {"infer": {"single": []}})

    def test_bare_number_checker(self):
        bad = ["<p>The judges agreed, τ = 0.47.</p>", "<p>Some 47% of viewers agreed.</p>",
               "<p>Agreement κ 0.61.</p>", "<p>κ=0.61</p>", "<span>47 %</span>"]
        for html in bad:
            self.assertTrue(pages.check_bare_numbers(html), html)
        ok = ['<p>τ = <span data-num="t">0.47</span></p>',
              '<p><span data-num="p">47</span>% agreed</p>',
              "<blockquote>“I'd say 90% of people”</blockquote>",
              "<p><code>tau = 0.47</code> and <code>50%</code></p>",
              '<table><tr><td data-spec>100%</td></tr></table>',
              "<style>.x{width:100%}</style><p>fine</p>"]
        for html in ok:
            self.assertEqual(pages.check_bare_numbers(html), [], html)


class TestChildBuild(Home):
    def test_bare_number_in_fragment_fails_build(self):
        self.one_video()
        self.fragment("overview", "<p>Viewers agreed 62% of the time.</p>")
        with self.assertRaises(pages.BareNumberError):
            pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_unknown_key_in_fragment_fails_build(self):
        self.one_video()
        self.fragment("viewers", '<p><span data-num="viewers.missing">x</span></p>')
        with self.assertRaises(KeyError):
            pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_router_anchor(self):
        self.one_video()
        self.fragment("teddy-criteria", '<p>Claim <a href="#ref-1">[1]</a> and '
                      '<a href="#ref-2">[2]</a>.</p><ol class="refs"><li id="ref-1">A</li>'
                      '<li id="ref-2">B</li></ol>')
        self.fragment("sources", '<p>See <a href="#ref-1">[1]</a>.</p>'
                      '<ol class="refs"><li id="ref-1">C</li></ol>')
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertIn("addEventListener('hashchange'", html)
        self.assertIn("closest('.main > .view')", html)
        refs = re.findall(r'href="#([\w-]*ref-\d+)"', html)
        self.assertGreaterEqual(len(refs), 3)
        ids = re.findall(r'\bid="([^"]+)"', html)
        for r in refs:
            self.assertIn(r, ids)
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids would tie the router")

    def test_artifact_contract(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertTrue(html.lstrip().startswith("<title>"))
        for tag in ("<!doctype", "<html", "<head", "<body"):
            self.assertNotRegex(html.lower(), re.escape(tag) + r"[\s>]")
        self.assertNotRegex(html, r'<img[^>]+src="https?:')
        self.assertIn("fonts.googleapis.com", html)
        self.assertIn('@media (prefers-color-scheme: dark)', html)
        self.assertIn(':root[data-theme="dark"]', html)

    def test_freeze_slots_in_every_view(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "contest", {})
        html = self.built()
        sections = re.findall(r'<section class="view"[^>]*>\s*(<div data-banner></div>)?\s*'
                              r'(<div data-today></div>)?', html)
        self.assertEqual(len(sections), 8)
        for banner, today in sections:
            self.assertTrue(banner and today)

    def test_page_sets_and_missing_notice(self):
        self.one_video()
        expected = {
            "contest": ["overview", "gallery", "criteria-inference", "taxonomy", "wearers",
                        "viewers", "teddy-criteria", "sources"],
            "review": ["overview", "gallery", "landscape", "taxonomy", "scorecard",
                       "viewers", "teddy-criteria", "sources"],
            "list": ["overview", "gallery", "landscape", "list-criteria", "left-out",
                     "viewers", "teddy-criteria", "sources"],
        }
        for t, views in expected.items():
            pages.build_child(self.run_dir, ["v1"], t, {})
            html = self.built()
            self.assertEqual(re.findall(r'<section class="view" id="v-([\w-]+)"', html), views)
            self.assertIn("not produced in this run", html)
        with self.assertRaises(ValueError):
            pages.build_child(self.run_dir, ["v1"], "brand", {})

    def test_overview_states_type_and_footer_names_source(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "review", {})
        html = self.built()
        self.assertIn("Single-watch review", html)
        self.assertIn("override", html.lower())
        self.assertEqual(html.count('class="page-foot"'), 8)
        self.assertIn("frames from the video unless", html)
        self.assertIn("https://youtu.be/v1", html)

    def test_commercial_note_on_criteria_pages(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "contest", {})
        html = self.built()
        body = html.split('id="v-teddy-criteria"', 1)[1].split('<section class="view"', 1)[0]
        self.assertIn("authorized dealer for over 35 brands", body)

    def test_commercial_note_once_on_every_commercial_page(self):
        self.one_video()
        for pid in ("taxonomy", "wearers", "scorecard"):
            self.assertIn(pid, pages._COMMERCIAL)
        for vtype in pages.TYPE_PAGES:
            pages.build_child(self.run_dir, ["v1"], vtype, {})
            html = self.built()
            for key in pages.page_set(vtype, False):
                n = self._view(html, key).count("authorized dealer for over 35 brands")
                self.assertEqual(n, 1 if key in pages._COMMERCIAL else 0, f"{vtype}/{key}")

    def _view(self, html, pid):
        return html.split(f'id="v-{pid}"', 1)[1].split('<section class="view"', 1)[0]

    def test_taxonomy_version_shown(self):
        self.one_video()
        (self.run_dir / "taxonomy.json").write_text(json.dumps(
            {"category": "dive", "version_id": "user:dive@2.1", "label": "provisional"}))
        pages.build_child(self.run_dir, ["v1"], "review", {})
        html = self.built()
        for pid in ("overview", "taxonomy"):
            body = self._view(html, pid)
            self.assertIn("user:dive@2.1", body, pid)
            self.assertIn('class="badge provisional">provisional<', body, pid)
            self.assertNotIn("not recorded for this run", body, pid)

    def test_taxonomy_version_missing_note(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "contest", {})
        html = self.built()
        for pid in ("overview", "taxonomy"):
            self.assertIn("Taxonomy version not recorded for this run", self._view(html, pid), pid)

    def test_taxonomy_bad_label_refused(self):
        self.one_video()
        (self.run_dir / "taxonomy.json").write_text(json.dumps(
            {"category": "dive", "version_id": "shipped:dive@1", "label": "ratified"}))
        with self.assertRaises(ValueError):
            pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_fragment_scripts_refused(self):
        self.one_video()
        self.fragment("viewers", "<script>alert(1)</script>")
        with self.assertRaises(ValueError):
            pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_child_links_parent(self):
        self.one_video()
        reg = {"parent": {"url": "https://claude.ai/artifact/PARENT123", "updated": "2026-11-14"},
               "children": []}
        (self.tmp / "home" / "registry.json").write_text(json.dumps(reg))
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertIn('href="https://claude.ai/artifact/PARENT123"', html)
        self.assertIn("← The collection", html)

    def test_backlink_added_after_freeze_keeps_hashes(self):
        # F12: on a first run the child is rebuilt with its parent link after it is frozen.
        from teddycoll import freeze
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        hashes = freeze.record(self.run_dir / "build")
        self.assertNotIn("artifact/P", self.built())
        (self.tmp / "home" / "registry.json").write_text(json.dumps(
            {"parent": {"url": "https://claude.ai/artifact/P"}, "children": []}))
        pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertIn("https://claude.ai/artifact/P", self.built())
        self.assertEqual(freeze.verify(self.run_dir / "build", hashes), [])

    def test_later_day_rebuild_verifies(self):
        # Review minor 3: the built date sits in every view's footer, but it is not hashed.
        from datetime import date as real_date
        from teddycoll import freeze

        class Tomorrow(real_date):
            @classmethod
            def today(cls):
                return real_date(2031, 1, 2)
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        hashes = freeze.record(self.run_dir / "build")
        with mock.patch.object(pages, "date", Tomorrow):
            pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertIn("2031-01-02", self.built())
        self.assertEqual(freeze.verify(self.run_dir / "build", hashes), [])

    def test_no_parent_link_without_registry(self):
        self.one_video()
        pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertNotIn("The collection</a>", self.built())

    def test_related_set_adds_what_changed(self):
        self.save([video("old", "2025-01-01"), video("new", "2026-01-01")],
                  [watch("a"), watch("b")],
                  [appearance("old", "a", 1), appearance("new", "a", 1), appearance("new", "b", 2)])
        pages.build_child(self.run_dir, ["new", "old"], "list", {})
        html = self.built()
        self.assertIn('id="v-what-changed"', html)
        nums = json.loads((self.run_dir / "numbers.json").read_text())
        self.assertEqual(nums["what_changed"]["older"], "old")
        self.assertEqual(nums["what_changed"]["counts"]["added"], 1)

    def test_credited_photo_shows_credit(self):
        if not FFMPEG:
            self.skipTest("ffmpeg not installed")
        img = self.tmp / "c.png"
        make_image(img, "400x300")
        photo = {"path": str(img), "kind": "credited", "credit": "Brand press photo",
                 "source_url": "https://brand.example/a"}
        self.save([video("v1", "2026-01-05")], [watch("a", photo)], [appearance("v1", "a", 1)])
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertIn("Brand press photo", html)
        self.assertIn('href="https://brand.example/a"', html)
        srcs = re.findall(r'<img[^>]+src="(img/[^"]+)"', html)
        self.assertTrue(srcs)
        for s in srcs:
            self.assertTrue((self.run_dir / "build" / s).is_file(), s)
            self.assertTrue(s.endswith(".jpg"))
        self.assertIn("<dialog", html)


class TestSubjectCheck(Home):
    """F19: every watch the comments are coded against is recorded for THIS run's videos
    (an appearance) or is one of its peers."""

    def subjects(self, d):
        (self.run_dir / "coding").mkdir(exist_ok=True)
        (self.run_dir / "coding" / "subjects.json").write_text(json.dumps(d))

    def padellone_run(self):
        # an earlier video in the collection recorded an IWC and several GMT/quartz watches
        self.save([video("ex", "2026-01-01", "contest"), video("v1", "2026-09-15", "review")],
                  [watch("iwc-iw503702", brand="IWC", model="Portugieser Perpetual Calendar"),
                   watch("grand-seiko-sbgm221", brand="Grand Seiko", model="Elegance GMT"),
                   watch("seiko-quartz", brand="Seiko", model="Quartz Diver, black dial"),
                   watch("rolex-perpetual-padellone-m53505-0002", brand="Rolex",
                         model="Perpetual Padellone, Everose gold", reference="M53505-0002")],
                  [appearance("ex", "iwc-iw503702"), appearance("ex", "grand-seiko-sbgm221"),
                   appearance("ex", "seiko-quartz"),
                   appearance("v1", "rolex-perpetual-padellone-m53505-0002", role="reviewed")])
        (self.run_dir / "peers.json").write_text(json.dumps({"watches": [
            {"id": "rolex-sky-dweller-m336935-0003", "brand": "Rolex", "model": "Rolex Sky-Dweller"}]}))

    def test_trial_1_still_flags_rolex_1908(self):
        self.padellone_run()
        self.subjects({"rolex-perpetual-padellone-m53505-0002": [], "padellone_everose": ["everose"],
                       "rolex_sky_dweller": ["sky-dweller"], "rolex_1908": ["1908", "cellini"]})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), ["rolex_1908"])
        with self.assertRaisesRegex(ValueError, "rolex_1908"):
            pages.build_child(self.run_dir, ["v1"], "review", {})

    def test_watch_of_another_video_does_not_count(self):
        # Review Important 1: the imported example's IWC must not satisfy a key this run names.
        self.padellone_run()
        self.subjects({"iwc_portugieser": ["portugieser", "iwc"]})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), ["iwc_portugieser"])

    def test_common_word_keys_do_not_match_unrelated_watches(self):
        self.padellone_run()
        self.subjects({"gmt": ["gmt"], "quartz": ["quartz"], "dial": ["dial"]})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), ["gmt", "quartz", "dial"])

    def test_key_words_alone_do_not_match(self):
        # no token matching on the key: only an exact id or a whole-word alias phrase
        self.padellone_run()
        self.subjects({"rolex_padellone": []})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), ["rolex_padellone"])

    def test_alias_phrase_whole_word(self):
        self.padellone_run()
        self.subjects({"p": ["rose"]})   # "rose" is inside "Everose", not a whole word
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), ["p"])
        self.subjects({"p": ["perpetual padellone"], "r": ["M53505-0002"]})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), [])

    def test_bare_string_alias(self):
        # Final review 19: a string alias is one alias, not a list of letters.
        self.padellone_run()
        self.subjects({"rolex_sky_dweller": "sky-dweller"})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), [])

    def test_videos_from_records_json(self):
        self.padellone_run()
        (self.run_dir / "records.json").write_text(json.dumps({"videos": [{"id": "v1"}],
                                                              "watches": [], "appearances": []}))
        self.subjects({"iwc_portugieser": ["iwc"], "padellone": ["padellone"]})
        self.assertEqual(pages.subject_check(self.run_dir), ["iwc_portugieser"])

    def test_all_matched_builds(self):
        self.one_video()
        self.subjects({"a": [], "model_b": ["model b"]})
        self.assertEqual(pages.subject_check(self.run_dir, ["v1"]), [])
        pages.build_child(self.run_dir, ["v1"], "list", {})

    def test_contest_subjects_are_people_not_checked(self):
        self.one_video()
        self.subjects({"marco": [], "brit": []})
        pages.build_child(self.run_dir, ["v1"], "contest", {})

    def test_cli_exit_codes(self):
        self.one_video()
        self.subjects({"a": [], "rolex_1908": ["1908"]})
        env = {**os.environ, "TEDDY_COLLECTION_HOME": str(self.tmp / "home")}
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "subject-check", str(self.run_dir),
                            "--videos", "v1"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(json.loads(r.stdout)["unmatched"], ["rolex_1908"])
        self.assertIn("rolex_1908", r.stderr)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), "build-child", str(self.run_dir),
                            "--type", "list", "--videos", "v1"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("rolex_1908", r.stderr)


class TestGalleryText(unittest.TestCase):
    def test_family_row_and_list_specs(self):
        # G4: family rows are labelled; F14/G10: list specs read as words, not Python reprs.
        from teddycoll import render
        w = {"id": "f", "brand": "Tissot", "model": "PRX", "reference": None, "family": True,
             "specs": {"complications": ["date", "day"], "case_mm": 40}, "confidence": "labelled_on_screen",
             "basis": "card"}
        html = render.gallery_card(w, {"role": "listed"}, None, None, {"url": "https://youtu.be/x"})
        self.assertIn("model family; no single reference", html)
        self.assertIn("complications: date, day", html)
        self.assertNotIn("[", html.split("<dt>Specs</dt>")[1].split("</dd>")[0])


class TestSourceResults(unittest.TestCase):
    def test_source_result_wording(self):
        # G2/F5: the page says which sources were blocked and which matched only partly.
        from teddycoll import render
        w = {"sources": [{"url": "https://a.example/x", "kind": "brand", "match": False,
                          "result": "unreadable", "status": 403},
                         {"url": "https://b.example/y", "kind": "press", "match": True,
                          "result": "partial", "match_level": "partial"}]}
        html = render.sources_table([{**w, "brand": "R", "model": "P", "basis": "b"}], "<p>m</p>")
        self.assertIn("blocked (403), unread", html)
        self.assertIn("core reference number matched", html)
        self.assertIn("partial match", render.source_links(w))
        w["sources"][1]["match"] = False
        w["sources"][1]["result"] = "no_match"
        self.assertIn("blocked, unread", render.source_links(w))


@unittest.skipUnless(FFMPEG, "ffmpeg not installed")
class TestSizeBudget(Home):
    def setUp(self):
        super().setUp()
        src = self.tmp / "src"
        src.mkdir()
        watches, apps = [], []
        for i in range(24):
            p = src / f"f{i}.jpg"
            make_image(p)
            watches.append(watch(f"w{i}", {"path": str(p), "kind": "frame"}))
            apps.append(appearance("v1", f"w{i}", i + 1))
        self.save([video("v1", "2026-01-05")], watches, apps)

    def total(self):
        return sum(f.stat().st_size for f in (self.run_dir / "build").rglob("*") if f.is_file())

    def manifest(self):
        return json.loads((self.run_dir / "build" / "manifest.json").read_text())

    def test_page_size_budget(self):
        pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertLessEqual(self.total(), 16 * 1024 * 1024)
        self.assertEqual(len(list((self.run_dir / "build" / "img").glob("*.jpg"))), 24)
        self.assertIn("downsized", self.manifest())
        out = subprocess.run(["ffmpeg", "-i", str(next((self.run_dir / "build" / "img").glob("*.jpg")))],
                             capture_output=True, text=True).stderr
        w, h = map(int, re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", out).groups())
        self.assertLessEqual(max(w, h), 900)

    def test_downsizes_to_700_when_over(self):
        pages.build_child(self.run_dir, ["v1"], "list", {})
        at_900 = self.total()
        self.assertFalse(self.manifest()["downsized"])
        budget = int(at_900 * 0.8)
        with mock.patch.object(pages, "SIZE_BUDGET", budget):
            pages.build_child(self.run_dir, ["v1"], "list", {})
        self.assertTrue(self.manifest()["downsized"])
        self.assertLessEqual(self.total(), budget)

    def test_raises_when_still_over(self):
        with mock.patch.object(pages, "SIZE_BUDGET", 1000):
            with self.assertRaises(ValueError):
                pages.build_child(self.run_dir, ["v1"], "list", {})


class TestParent(Home):
    def test_timeline_by_upload_date(self):
        self.save([video("late", "2025-03-01", title="Later video"),
                   video("early", "2024-06-01", title="Earlier video")], [], [])
        out = pages.build_parent()
        html = (out / "index.html").read_text(encoding="utf-8")
        body = html.split('id="v-timeline"', 1)[1]
        self.assertLess(body.index("Earlier video"), body.index("Later video"))
        self.assertLess(body.index("2024"), body.index("2025"))

    def test_parent_views_and_index(self):
        self.save([video("v1", "2025-03-01", "contest"), video("v2", "2024-01-01", "list")],
                  [watch("a", status_history=[{"date": "2026-01-01", "status": "discontinued",
                                               "source": "brand"}])],
                  [appearance("v1", "a"), appearance("v2", "a")])
        reg = {"parent": None, "children": [
            {"video_ids": ["v1"], "url": "https://claude.ai/artifact/C1", "type": "contest",
             "published": "2026-11-14", "build": "/x", "hashes": {}},
            {"video_ids": ["v2"], "url": "https://claude.ai/artifact/C2", "type": "list",
             "published": "2026-11-14", "build": "/y", "hashes": {}}]}
        (self.tmp / "home" / "registry.json").write_text(json.dumps(reg))
        html = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r'<section class="view" id="v-([\w-]+)"', html),
                         ["overview", "timeline", "watch-index", "taxonomy-library", "child-list"])
        idx = html.split('id="v-watch-index"', 1)[1].split('<section class="view"', 1)[0]
        self.assertEqual(idx.count('class="wcard"'), 1)
        self.assertIn("discontinued", idx.lower())
        self.assertIn("https://claude.ai/artifact/C1", idx)
        self.assertIn("https://claude.ai/artifact/C2", idx)
        kids = html.split('id="v-child-list"', 1)[1]
        self.assertLess(kids.index("Contest"), kids.index("List"))
        self.assertIn("Teddy's selection of the watch world, not the watch world", html)

    def test_parent_masthead_is_not_the_channel(self):
        # F15/G11: the channel is named as the source, not used as the site's masthead.
        self.one_video()
        html = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        self.assertIn("<title>Watch videos, analysed</title>", html)
        self.assertNotIn("<h1>Teddy Baldassarre collection</h1>", html)
        for h1 in re.findall(r"<h1>(.*?)</h1>", html):
            self.assertNotIn("Teddy Baldassarre", h1)
        brand = re.search(r'<a class="brand".*?</a>', html, re.S).group(0)
        self.assertNotIn("Teddy Baldassarre", brand)
        self.assertNotIn("Teddy Baldassarre · collection", html)
        self.assertIn("Teddy Baldassarre YouTube videos", html)  # the source line

    def test_no_child_set_wording(self):
        # F20: readers see "Video analyses"; the watch index labels its links "Appears in".
        self.save([video("v1", "2025-03-01", "list"), video("v2", "2024-01-01", "list")],
                  [watch("a"), watch("b")], [appearance("v1", "a"), appearance("v2", "b")])
        reg = {"parent": {"url": "https://claude.ai/artifact/P"}, "children": [
            {"video_ids": ["v1"], "url": "https://claude.ai/artifact/C1", "type": "list",
             "published": "2026-11-14", "build": "/x", "hashes": {}}]}
        (self.tmp / "home" / "registry.json").write_text(json.dumps(reg))
        parent = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        pages.build_child(self.run_dir, ["v1"], "list", {})
        for html in (parent, self.built()):
            self.assertIsNone(re.search(r"(?i)child[ -]?sets?\b", html),
                              re.search(r"(?i).{40}child[ -]?sets?\b.{20}", html))
        self.assertIn("<h1>Video analyses</h1>", parent)
        self.assertIn("<dt>Appears in</dt>", parent)
        self.assertIn("not yet in a published video analysis", parent)

    def test_taxonomy_library_labels(self):
        taxonomy.SHIPPED_DIR.mkdir()
        t = {"id": "shipped:dive@1", "category": "dive", "version": "1", "label": "provisional",
             "paradigm": "p", "created": "2026-11-14",
             "change_log": [{"date": "2026-11-14", "reason": "first draft"}],
             "layers": {"watch": []}}
        (taxonomy.SHIPPED_DIR / "dive@1.json").write_text(json.dumps(t))
        self.save([], [], [])
        html = (pages.build_parent() / "index.html").read_text(encoding="utf-8")
        lib = html.split('id="v-taxonomy-library"', 1)[1].split('<section class="view"', 1)[0]
        self.assertIn("shipped:dive@1", lib)
        self.assertIn("provisional", lib.lower())
        self.assertNotIn(">compiled<", lib.lower())
        self.assertIn("first draft", lib)


class TestDiff(Home):
    def test_diff_videos(self):
        refs_old, refs_new = ["a", "b", "c", "d", "e"], ["a", "b", "c", "f", "g"]
        watches = [watch(r) for r in sorted(set(refs_old + refs_new))]
        apps = [appearance("old", r, i, 500 if r == "a" else None) for i, r in enumerate(refs_old)]
        apps += [appearance("new", r, i, 550 if r == "a" else None) for i, r in enumerate(refs_new)]
        self.save([video("old", "2025-01-01"), video("new", "2026-01-01")], watches, apps)
        d = pages.diff_videos("old", "new")
        self.assertEqual(sorted(d["added"]), ["f", "g"])
        self.assertEqual(sorted(d["dropped"]), ["d", "e"])
        self.assertEqual(d["counts"], {"added": 2, "dropped": 2, "shared": 3, "price_moves": 1})
        self.assertEqual(len(d["price_moves"]), 1)
        m = d["price_moves"][0]
        self.assertEqual((m["watch_id"], m["from"]["amount"], m["to"]["amount"], m["currency"]),
                         ("a", 500, 550, "USD"))
        self.assertEqual(m["delta"], 50)


class TestCli(Home):
    def cli(self, *args):
        env = {**os.environ, "TEDDY_COLLECTION_HOME": str(self.tmp / "home")}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args],
                              env=env, capture_output=True, text=True)

    def test_build_child_and_parent_cli(self):
        self.one_video()
        r = self.cli("build-child", str(self.run_dir), "--type", "list", "--videos", "v1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.run_dir / "build" / "index.html").is_file())
        self.assertIn("missing_fragments", json.loads(r.stdout))
        r = self.cli("build-parent")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(Path(json.loads(r.stdout)["build"], "index.html").is_file())

    def test_unchecked_gallery_photo_warns(self):
        # G1: a still nobody looked at is named on stderr and in the manifest.
        if not FFMPEG:
            self.skipTest("ffmpeg not installed")
        (self.run_dir / "img").mkdir()
        make_image(self.run_dir / "img" / "a.jpg", "400x300")
        make_image(self.run_dir / "img" / "b.jpg", "400x300")
        self.save([video("v1", "2026-01-05")],
                  [watch("a", {"kind": "frame", "path": "img/a.jpg", "at": "1:00", "checked": True}),
                   watch("b", {"kind": "frame", "path": "img/b.jpg", "at": "1:10"})],
                  [appearance("v1", "a", 1), appearance("v1", "b", 2)])
        r = self.cli("build-child", str(self.run_dir), "--type", "list", "--videos", "v1")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["unchecked_photos"], ["b"])
        self.assertIn("warning: photo not checked by eye: b", r.stderr)
        self.assertNotIn("checked by eye: a", r.stderr)

    def test_build_child_cli_bare_number_exit_2(self):
        self.one_video()
        self.fragment("overview", "<p>τ = 0.5</p>")
        r = self.cli("build-child", str(self.run_dir), "--type", "list", "--videos", "v1")
        self.assertEqual(r.returncode, 2)
        self.assertIn("τ", r.stderr)


class TestBadTimestamps(Home):
    """Final review 7: an unparseable timestamp renders as its raw text with no link."""

    def test_render_helpers(self):
        from teddycoll import render
        self.assertEqual(render.ts_label("1:05"), "1:05")
        self.assertEqual(render.ts_label("about 2 min"), "about 2 min")
        self.assertEqual(render.ts_link("https://youtu.be/x", "about 2 min"), "about 2 min")
        self.assertEqual(render.ts_link("https://youtu.be/x", "nan"), "nan")
        self.assertEqual(render.ts_link("https://youtu.be/x", None), "None")
        self.assertIn("t=65", render.ts_link("https://youtu.be/x", "1:05"))

    def test_gallery_builds_with_bad_timestamp(self):
        self.save([video("v1", "2026-01-05")], [watch("a"), watch("b")],
                  [appearance("v1", "a", timestamps=["intro", "0:40"]),
                   appearance("v1", "b", timestamps=["0:20"])])
        pages.build_child(self.run_dir, ["v1"], "list", {})
        html = self.built()
        self.assertIn(">intro<", html.replace("<dd>intro", ">intro<"))
        self.assertNotIn("t=intro", html)
        gal = html.split('id="v-gallery"', 1)[1]
        self.assertLess(gal.index("Model b"), gal.index("Model a"))  # 0:20 before 0:40


if __name__ == "__main__":
    unittest.main()
