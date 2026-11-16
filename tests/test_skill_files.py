"""The /teddy skill and its references: paths, frontmatter, CLI calls, hand-off rule."""
import argparse
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "teddy-collection"
SKILL_DIR = PLUGIN / "skills" / "teddy"
SKILL = SKILL_DIR / "SKILL.md"
SETUP = PLUGIN / "skills" / "teddy-setup" / "SKILL.md"
sys.path.insert(0, str(PLUGIN / "lib"))
sys.path.insert(0, str(PLUGIN / "scripts"))
import teddy  # noqa: E402
from teddycoll import pages, sanitize  # noqa: E402

PAGE_SPECS = ("shared", "contest", "review", "list", "related-set")


def _text(p):
    return p.read_text(encoding="utf-8")


def _subparsers(parser):
    """{name: subparser} for the parser's sub-command action, or {} if it has none."""
    for a in parser._actions:
        if isinstance(a, argparse._SubParsersAction):
            return dict(a.choices)
    return {}


def _positional_choices(parser):
    for a in parser._actions:
        if not a.option_strings and a.choices and not isinstance(a, argparse._SubParsersAction):
            return set(a.choices)
    return set()


class TestSkillFiles(unittest.TestCase):
    def test_every_reference_exists(self):
        named = set(re.findall(r"references/[A-Za-z0-9_./-]+\.(?:md|html|json)", _text(SKILL)))
        self.assertTrue(named, "SKILL.md names no reference files")
        for rel in sorted(named):
            self.assertTrue((SKILL_DIR / rel).is_file(), f"SKILL.md names missing {rel}")
        for name in ("priming.md", "video-types.md", "scoring-rubric.md", "coding-brief.md",
                     "taxonomy-drafting.md"):
            self.assertIn(f"references/{name}", named, f"SKILL.md never points to {name}")
        for spec in PAGE_SPECS:
            self.assertTrue((SKILL_DIR / "references" / "page-specs" / f"{spec}.md").is_file(), spec)

    def test_frontmatter(self):
        for f in (SKILL, SETUP):
            m = re.match(r"---\n(.*?)\n---\n", _text(f), re.S)
            self.assertIsNotNone(m, f"{f} has no frontmatter")
            fields = dict(re.findall(r"^([a-z_]+):\s*(.+)$", m.group(1), re.M))
            self.assertTrue(fields.get("name", "").strip(), f"{f}: no name")
            self.assertTrue(fields.get("description", "").strip(), f"{f}: no description")
        self.assertEqual(re.search(r"^name:\s*(\S+)", _text(SKILL), re.M).group(1), "teddy")

    def test_cli_calls_exist(self):
        top = _subparsers(teddy.build_parser())
        calls = re.findall(r"teddy\.py\"?\s+([a-z][a-z-]*)(?:\s+([a-z][a-z-]*))?", _text(SKILL))
        self.assertTrue(calls, "SKILL.md names no teddy.py calls")
        # shortened forms in backticks (`frames resize <img>`, `registry find …`) are checked too
        calls += [c for c in re.findall(r"`([a-z][a-z-]*)(?: ([a-z][a-z-]*))?[ `]", _text(SKILL))
                  if c[0] in top]
        for sub, action in calls:
            self.assertIn(sub, top, f"teddy.py {sub} is not a registered subcommand")
            nested = _subparsers(top[sub]) or _positional_choices(top[sub])
            if nested and action and action in nested:
                continue
            if nested and action and sub in ("frames", "coding", "freeze", "registry", "taxonomy"):
                self.fail(f"teddy.py {sub} {action}: {action!r} is not one of {sorted(nested)}")
        self.assertIn("import-example", _text(SKILL))

    def test_names_no_outside_skills(self):
        # a friend who installs the plug-in has no /fact-check or /analyze,
        # so neither the skill nor the README may offer or mention them
        files = list(PLUGIN.rglob("*.md")) + [ROOT / "README.md"]
        for f in files:
            self.assertNotRegex(_text(f), r"/(?:fact-check|analyze)\b", str(f))

    def test_page_specs_cover_built_pages(self):
        spec_text = {s: _text(SKILL_DIR / "references" / "page-specs" / f"{s}.md") for s in PAGE_SPECS}
        for vtype in pages.TYPE_PAGES:
            for key in pages.page_set(vtype, related=True):
                where = spec_text["shared"] + spec_text[vtype] + spec_text["related-set"]
                self.assertIn(f"`{key}`", where, f"no page spec names page {key} for {vtype}")
        for cls in sanitize.FRAGMENT_CLASSES:
            self.assertIn(f"`{cls}`", spec_text["shared"], f"shared.md does not list class {cls}")
        # Final review 8: the baseline's size is read from numbers, never typed as 40.
        for spec in ("contest", "list"):
            self.assertIn("infer.null_n_criteria", spec_text[spec])
            self.assertNotIn("40 random criteria", spec_text[spec])

    def test_stills_checked_by_eye_before_dataset_add(self):
        # G1: the look is mandatory; it is recorded as "checked": true on the photo.
        text = _text(SKILL)
        step3 = text[text.index("## Step 3"):text.index("## Step 4")]
        self.assertIn('"checked": true', step3)
        self.assertRegex(step3, r"(?i)open \(read\) every (chosen )?still")
        self.assertIn("checked by eye", text)

    def _section(self, start, end):
        text = _text(SKILL)
        return text[text.index(start):text.index(end)]

    def test_blocked_sources_and_rechecks(self):
        # G2/F4, F5/G3, G16: unread is not a mismatch; recheck only the failures.
        step4 = self._section("## Step 4", "## Step 5")
        self.assertIn("source blocked, unread", step4)
        self.assertIn("`unreadable`", step4)
        self.assertIn("`partial`", step4)
        self.assertIn("--only", step4)
        self.assertRegex(step4, r"press release, then (an open )?dealer")

    def test_budget_counts_fetches(self):
        # F18/G16: fetch volume draws rate limits; a 429 host is skipped for the run.
        budgets = self._section("## Budgets", "## Rules that hold throughout")
        self.assertRegex(budgets, r"(?i)at most 30 page fetches")
        self.assertRegex(budgets, r"429[^.]*skip")

    def test_named_watches_always_recorded(self):
        # F19: a watch the video names is a `mentioned` appearance with a photo, a named
        # peer is always in the landscape, and the price band binds only added peers.
        specs = SKILL_DIR / "references" / "page-specs"
        for name in ("review", "list", "contest"):
            t = _text(specs / f"{name}.md")
            self.assertRegex(t, r"(?is)names?[^.]*always recorded[^.]*`mentioned`", name)
            self.assertRegex(t, r"(?i)a frame if the video shows it, else a credited photo", name)
        review = _text(specs / "review.md")
        self.assertRegex(review, r"(?i)a peer the video names is always in the landscape")
        self.assertRegex(review, r"(?i)price band applies only to the peers this run adds")
        step8 = self._section("## Step 8", "## Step 9")
        self.assertIn("subject-check", step8)
        self.assertRegex(step8, r"(?i)keyed by (the )?watch id")

    def test_peer_prices_unread_or_foreign(self):
        # F8: a matched peer with no readable price stays; foreign prices stay unconverted.
        review = _text(SKILL_DIR / "references" / "page-specs" / "review.md")
        self.assertRegex(review, r"(?i)no readable price stays[^.]*\"not read\"")
        self.assertRegex(review, r"(?i)unconverted, with the currency named")

    def test_reader_wording_video_analysis(self):
        # F20: what the user and readers see says "video analysis", not "child set".
        step11 = self._section("## Step 11", "anything the run could not do.")
        self.assertNotRegex(step11, r"(?i)\"superseded by\"[^.]*child set")
        give = [l for l in step11.splitlines() if "Give the user" in l]
        self.assertTrue(give)
        self.assertIn("video analysis", give[0])
        self.assertNotIn("child", give[0])

    def test_viewer_pulse_by_type(self):
        # F9/G7, F10/G8, F11: the page reads the type's own stance counts and treats a
        # null kappa as "too few to measure".
        shared = _text(SKILL_DIR / "references" / "page-specs" / "shared.md")
        for key in ("viewers.verdict_stance", "viewers.sentiment", "viewers.selection_stance",
                    "viewers.missing", "coding_agreement.n_nonempty", "viewers.reasons.other"):
            self.assertIn(key, shared)
        self.assertRegex(shared, r"(?i)too few to measure")

    def test_first_run_publishes_parent_once(self):
        # F12: no parent-first publish; the child is published, the parent built once, and
        # the child republished with its back-link on a first run.
        step10 = self._section("## Step 10", "## Step 11")
        self.assertNotRegex(step10, r"(?i)build and publish the parent first")
        step11 = self._section("## Step 11", "anything the run could not do.")
        self.assertRegex(step11, r"(?i)first run")
        self.assertIn("freeze verify <run>/build <run>/hashes.json", step11)
        self.assertIn("series-candidates", step11)
        self.assertNotIn("series_candidates(v)", step11)

    def test_read_before_update_only_when_needed(self):
        # F13/G12: no read of an artifact this session published; the parent relies on
        # the Artifact tool's refusal to hand back the live version.
        pub = self._section("## Publishing a build", "## Run files")
        self.assertRegex(pub, r"(?i)this session did not publish")
        self.assertRegex(pub, r"(?i)parent[^.]*always rebuilt from the registry")
        self.assertIn("relative_files", pub)

    def test_additions_schema_documented(self):
        # F7: the additions file's shape, with an example.
        t = _text(SKILL_DIR / "references" / "taxonomy-drafting.md")
        for key in ("`layers`", "`spec_fields`", "`coherence`", "`teddy_principles`", "`paradigm`"):
            self.assertIn(key, t)
        self.assertIn('"spec_fields": {', t)

    def test_step3_per_type_and_confidence_grade(self):
        # F2/G5: which segment to sheet per type; F3/G4: what confidence grades, and families;
        # F6: the verdict stance values; G6: a list's category.
        step3 = self._section("## Step 3", "## Step 4")
        for t in ("contest", "review", "list"):
            self.assertRegex(step3, rf"(?i)\*\*{t}\*\*")
        self.assertIn("metadata.json", step3)
        self.assertIn("--every 3", step3)
        self.assertRegex(step3, r"(?i)confidence grades the reference")
        self.assertIn('"family": true', step3)
        self.assertIn("`positive`, `mixed`, `negative` or `none`", step3)
        step6 = self._section("## Step 6", "## Step 7")
        self.assertRegex(step6, r"(?i)for a list, the run's category is the list's theme")

    def test_list_prices(self):
        # G17: a list records the video's price first and reads at most one price source per brand.
        lst = _text(SKILL_DIR / "references" / "page-specs" / "list.md")
        self.assertRegex(lst, r"(?i)at most one price source per brand")
        self.assertRegex(lst, r"(?i)snippet")

    def test_coders_count_stated(self):
        # F17: the dispatch heading and the count agree.
        step8 = self._section("## Step 8", "## Step 9")
        self.assertIn("Send the two primary coders and the audit coder together (three subagents)", step8)

    def test_user_facing_text_says_video_analysis(self):
        # F20 extended (review minor 6): README, CLI help, the import notice and the
        # check-new stop message say "video analysis", not "child set".
        import contextlib, io
        rx = re.compile(r"(?i)child[ -]?sets?\b")
        readme = _text(ROOT / "README.md")
        self.assertIsNone(rx.search(readme), rx.search(readme) and readme[rx.search(readme).start() - 60:][:120])
        parser = teddy.build_parser()
        helps = [parser.format_help()] + [p.format_help() for p in _subparsers(parser).values()]
        for h in helps:
            self.assertIsNone(rx.search(h), h)
        self.assertIsNone(rx.search(_text(PLUGIN / "lib" / "teddycoll" / "importer.py").split("notice = (", 1)[1][:200]))
        line = [l for l in _text(SKILL).splitlines() if "Exit 3 means" in l][0]
        self.assertIsNone(rx.search(line), line)

    def test_dispatches_are_primed(self):
        text = _text(SKILL)
        blocks = re.findall(r"(?ms)^\s*> \*\*Dispatch[^\n]*\n(?:\s*>[^\n]*\n)*", text)
        self.assertTrue(blocks, "SKILL.md has no dispatch prompts")
        for b in blocks:
            self.assertIn("references/priming.md", b, b)
            self.assertRegex(b, r"(?i)\bmodel:\s*(sonnet|opus|haiku)", b)


class TestTrial3SkillText(unittest.TestCase):
    """Final fix wave, section D (trial 3 findings H1, H3, H2, H5)."""

    def step(self, n):
        text = _text(SKILL)
        return text[text.index(f"## Step {n}"):text.index(f"## Step {n + 1}")]

    def test_review_sheets_around_named_watches(self):
        # 20 (H1): a review also sheets ten seconds either side of each other named watch.
        review = next(l for l in self.step(3).splitlines() if l.strip().startswith("- **review**"))
        self.assertIn("ten seconds either side", review)
        self.assertIn("names another watch", review)

    def test_landscape_peer_defined(self):
        # 21 (H3): a peer is a watch the video sets against the reviewed one.
        spec = _text(SKILL_DIR / "references" / "page-specs" / "review.md")
        self.assertIn("sets against the reviewed watch", spec)
        self.assertRegex(spec, r"named only as history[^.]*`mentioned`[^.]*gallery[^.]*not a landscape peer")
        self.assertRegex(spec, r"(?i)which named watches it left out, and why")

    def test_frame_identity_checked_against_a_reference(self):
        # 23 (H2): narration does not identify a frame.
        step5 = self.step(5)
        self.assertIn("not necessarily that watch", step5)
        self.assertIn("reference photo or the on-screen card", step5)

    def test_failing_user_branch_gets_a_new_minor_version(self):
        # 24 (H5)
        text = _text(SKILL_DIR / "references" / "taxonomy-drafting.md")
        self.assertRegex(text, r"fails `taxonomy check`.*next minor version.*rather than editing")


if __name__ == "__main__":
    unittest.main()
