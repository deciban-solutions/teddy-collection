"""Plain-language labels for the taxonomy pages: say what the checklist is for, in words a
reader knows, and say how far a version has been checked."""
import re, sys, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "teddy-collection"
sys.path.insert(0, str(PLUGIN / "lib"))
from teddycoll import pages, render  # noqa: E402

TPL = PLUGIN / "templates" / "pages"
SPECS = PLUGIN / "skills" / "teddy" / "references" / "page-specs"


def lede(name):
    return re.search(r'<p class="lede">(.*?)</p>', (TPL / name).read_text(), re.S).group(1)


class TestTitles(unittest.TestCase):
    def test_page_titles(self):
        self.assertEqual(pages.PAGE_META["taxonomy"][0], "Buyer's checklist")
        self.assertIn("checklist", pages.PAGE_META["scorecard"][1])
        self.assertEqual(pages.PAGE_META["taxonomy-library"][0], "Checklist library")

    def test_taxonomy_template_says_what_it_is_for(self):
        text = (TPL / "taxonomy.html").read_text()
        self.assertIn("<h1>Buyer's checklist</h1>", text)
        self.assertIn("measures", lede("taxonomy.html"))
        self.assertNotIn("concepts", lede("taxonomy.html"))

    def test_scorecard_and_library_ledes(self):
        self.assertIn("checklist", lede("scorecard.html"))
        self.assertIn("<h1>Checklist library</h1>", (TPL / "taxonomy-library.html").read_text())


class TestTaxonomyUsed(unittest.TestCase):
    TAX = {"category": "gmt", "version_id": "shipped:gmt@2", "label": "compiled"}
    WARRANT = {"ratified": True, "ratified_by": "the builder", "catch_power": 1.0,
               "ratified_on": "2026-12-01", "not_enforced_here": ["fair_value"],
               "freeze_commit": "abc1234"}

    def test_provisional_is_explained(self):
        html = render.taxonomy_used({"category": "gmt", "version_id": "user:gmt@1.1",
                                     "label": "provisional"})
        self.assertIn("Checklist used", html)
        self.assertIn("drafted", html)
        self.assertIn("not been compiled or ratified", html)

    def test_compiled_and_ratified(self):
        html = render.taxonomy_used(self.TAX, self.WARRANT)
        self.assertIn("frozen pre-registration", html)
        self.assertIn("ratified by the builder", html)
        self.assertIn("every planted flaw", html)
        self.assertIn("fair value", html)

    def test_compiled_partial_catch(self):
        html = render.taxonomy_used(self.TAX, {**self.WARRANT, "catch_power": 0.5})
        self.assertIn("some of the planted flaws", html)

    def test_compiled_not_ratified(self):
        html = render.taxonomy_used(self.TAX, {**self.WARRANT, "ratified": False,
                                               "ratified_by": None})
        self.assertIn("not yet ratified", html)

    def test_compiled_without_warrant(self):
        self.assertIn("records no warrant", render.taxonomy_used(self.TAX))

    def test_role_is_escaped(self):
        html = render.taxonomy_used(self.TAX, {**self.WARRANT, "ratified_by": "<b>x</b>"})
        self.assertNotIn("<b>x</b>", html)


class TestReviewFixesRender(unittest.TestCase):
    W = TestTaxonomyUsed.WARRANT

    def test_no_freeze_no_freeze_clause(self):  # M6
        html = render.taxonomy_used(TestTaxonomyUsed.TAX, {**self.W, "freeze_commit": None})
        self.assertNotIn("frozen pre-registration", html)

    def test_judged_in_compile_disclosed(self):  # I1
        html = render.taxonomy_used(TestTaxonomyUsed.TAX,
                                    {**self.W, "not_validated_in_compile": ["zone_pattern"]})
        self.assertIn("zone pattern", html)
        self.assertIn("Judged in the compile too", html)

    def test_branch_of_compiled_base(self):  # M8
        html = render.taxonomy_used({"category": "gmt", "version_id": "user:gmt@2.1",
                                     "label": "provisional", "derived_from": "shipped:gmt@2",
                                     "base_label": "compiled"})
        self.assertIn("<b>provisional</b> branch of the compiled shipped:gmt@2", html)
        self.assertNotIn("drafted it from published sources", html)

    def test_library_card_says_how_checked(self):  # M9
        t = {"id": "shipped:gmt@2", "category": "gmt", "label": "compiled", "created": "x",
             "paradigm": "p", "change_log": [], "warrant": self.W}
        self.assertIn("ratified by the builder", render.taxonomy_library([(0, t)]))
        self.assertIn("No checklists", render.taxonomy_library([]))


class TestNotExportedRender(unittest.TestCase):
    def test_left_out_concepts_named_with_reasons(self):
        w = {**TestTaxonomyUsed.WARRANT, "not_exported": [
            {"key": "page_value_dominance", "kind": "must", "reason": "judges the whole page"}]}
        html = render.taxonomy_used(TestTaxonomyUsed.TAX, w)
        self.assertIn("Left out of the plug-in", html)
        self.assertIn("page value dominance (must hold: judges the whole page)", html)


class TestPageSpecs(unittest.TestCase):
    def test_taxonomy_table_uses_plain_headings(self):
        text = (SPECS / "contest.md").read_text()
        section = text[text.index("## `taxonomy`"):text.index("## `wearers`")]
        for h in ("What this page is for", "What it means", "How strict", "Based on", "Tested by"):
            self.assertIn(h, section)
        self.assertNotIn("evidence class (", section)

    def test_scorecard_row_says_how_strict(self):
        text = (SPECS / "review.md").read_text()
        self.assertIn("how strict it is", text)


if __name__ == "__main__":
    unittest.main()
