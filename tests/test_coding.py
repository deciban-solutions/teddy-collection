import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import coding  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"
FIX = Path(__file__).resolve().parent / "fixtures"
SUBJECTS = {"a": ["Alpha", "Al"], "b": ["Beta"], "c": ["Gamma"]}


def coded(i, **kw):
    r = {"id": str(i), "relevant": True, "full_ranking": None, "best": [], "worst": [],
         "underrated": [], "overrated": [], "judge_stance": None, "reasons": [],
         "stated_criteria_quote": None}
    r.update(kw)
    return r


class TestKappa(unittest.TestCase):
    def test_kappa_known_value(self):
        p = [coded(i, judge_stance="agree" if i < 5 else "disagree") for i in range(10)]
        q = [coded(i, judge_stance="agree" if i < 4 or i == 9 else "disagree") for i in range(10)]
        # 8 of 10 agree (items 4 and 9 differ); 50/50 balance for both raters
        self.assertAlmostEqual(coding.agreement(p, q)["judge_stance"], 0.6)

    def test_best_compared_as_sorted_tuple_and_pe_one(self):
        p = [coded(i, best=["a", "b"]) for i in range(6)]
        q = [coded(i, best=["b", "a"]) for i in range(6)]
        self.assertEqual(coding.agreement(p, q)["best"], 1.0)


class TestAggregate(unittest.TestCase):
    def test_borda(self):
        rows = [coded(1, full_ranking=["a", "b", "c"]), coded(2, full_ranking=["b", "a", "c"])]
        out = coding.aggregate(rows, {}, subjects=["a", "b", "c"])
        self.assertEqual(out["borda"], {"a": 3, "b": 3, "c": 0})
        self.assertEqual(out["pairwise_wins"]["a>b"], 1)
        self.assertEqual(out["first_place"]["a"], 1)
        self.assertEqual(out["last_place"]["c"], 2)

    def test_once_per_comment_and_like_weight(self):
        rows = [coded(1, best=["a", "a"]), coded(2, best=["a"], judge_stance="agree")]
        out = coding.aggregate(rows, {"1": 4}, subjects=["a"])
        self.assertEqual(out["best"]["a"], 2)
        self.assertEqual(out["best_weighted"]["a"], 5 + 1)
        self.assertEqual(out["stance"]["agree"], 1)

    def test_fixture_cross_check(self):
        rows = []
        for n in ("coded_1.jsonl", "coded_2.jsonl"):
            rows += [json.loads(l) for l in (FIX / n).read_text().splitlines() if l.strip()]
        self.assertEqual(len(rows), 600)
        out = coding.aggregate(rows, {})
        self.assertEqual(out["best"], {"brit": 80, "adrien": 45, "teddy": 33,
                                       "marco": 42, "james": 59, "andrew": 83})
        self.assertEqual({k: out["stance"][k] for k in ("agree", "disagree", "mixed")},
                         {"agree": 58, "disagree": 69, "mixed": 12})


class TestFindings(unittest.TestCase):
    def test_unknown_subject_skipped_and_reported(self):
        rows = [coded(1, best=["a"]), coded(2, best=["Brit"]), coded(3, best=["a"])]
        out = coding.aggregate(rows, {}, subjects=["a", "b"])
        self.assertEqual(out["best"], {"a": 2, "b": 0})
        self.assertEqual(out["unknown_subjects"], [{"id": "2", "key": "Brit", "field": "best"}])

    def test_agreement_disjoint_ids(self):
        out = coding.agreement([coded(1)], [coded(2), coded(3)])
        self.assertTrue(out["no_overlap"])
        self.assertEqual(out["n"], 0)
        self.assertTrue(all(out.get(f) is None for f in coding.KAPPA_FIELDS))
        self.assertIsNone(out["best"])
        self.assertEqual(out["audit_ids_missing_from_primary"], 2)

    def test_agreement_partial_overlap(self):
        out = coding.agreement([coded(1), coded(2)], [coded(2), coded(9)])
        self.assertFalse(out["no_overlap"])
        self.assertEqual(out["audit_ids_missing_from_primary"], 1)

    def test_alias_word_boundary(self):
        with tempfile.TemporaryDirectory() as d:
            cs = [{"id": "x", "text": "really also", "like_count": 0, "parent": "root"},
                  {"id": "y", "text": "AL wins", "like_count": 0, "parent": "root"}]
            res = coding.prepare(cs, {"a": ["Al", ""]}, [""], Path(d), seed=1)
            self.assertEqual(res["n_candidates"], 1)


class TestTypeVariants(unittest.TestCase):
    """F9/G7: reviews ask whether commenters agree with the verdict; lists ask what was left out."""

    def test_brief_fields_by_type(self):
        contest = coding.render_brief(SUBJECTS, "contest")
        review = coding.render_brief(SUBJECTS, "review")
        lst = coding.render_brief(SUBJECTS, "list")
        self.assertIn('"judge_stance"', contest)
        self.assertNotIn('"verdict_stance"', contest)
        self.assertIn('"verdict_stance"', review)
        self.assertIn('"sentiment"', review)
        self.assertNotIn('"judge_stance"', review)
        self.assertIn('"missing"', lst)
        self.assertIn('"selection_stance"', lst)
        self.assertNotIn('"judge_stance"', lst)
        for b in (contest, review, lst):
            self.assertNotIn("{{", b)

    def test_prepare_type_from_type_json(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "type.json").write_text(json.dumps({"type": "review"}))
            cs = [{"id": "1", "text": "Alpha is great", "parent": "root"}]
            subj = run / "subjects.json"
            subj.write_text(json.dumps(SUBJECTS))
            cm = run / "comments.json"
            cm.write_text(json.dumps(cs))
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "coding", "prepare", "--run",
                                str(run / "coding"), "--comments", str(cm), "--subjects", str(subj),
                                "--seed", "1"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('"verdict_stance"', (run / "coding" / "BRIEF.md").read_text())

    def test_aggregate_review_fields(self):
        rows = [coded(1, verdict_stance="agrees", sentiment={"a": "like"}),
                coded(2, verdict_stance="disagrees", sentiment={"a": "dislike", "b": "like"}),
                coded(3, verdict_stance="agrees", sentiment={"a": "like", "zz": "like"})]
        out = coding.aggregate(rows, {}, subjects=["a", "b"])
        self.assertEqual(out["verdict_stance"], {"agrees": 2, "disagrees": 1})
        self.assertEqual(out["sentiment"]["a"], {"like": 2, "dislike": 1, "mixed": 0})
        self.assertEqual(out["sentiment"]["b"]["like"], 1)
        self.assertIn({"id": "3", "key": "zz", "field": "sentiment"}, out["unknown_subjects"])

    def test_aggregate_list_missing_by_brand(self):
        rows = [coded(1, selection_stance="disputes",
                      missing=[{"brand": "Orient", "model": "Bambino"}, {"brand": "orient", "model": None}]),
                coded(2, selection_stance="disputes", missing=["Orient Kamasu", "Casio"]),
                coded(3, selection_stance="agrees", missing=[{"brand": "Glycine", "model": "Combat"}])]
        out = coding.aggregate(rows, {}, subjects=["a"])
        self.assertEqual(out["selection_stance"], {"disputes": 2, "agrees": 1})
        self.assertEqual(out["missing"], {"orient": 2, "casio": 1, "glycine": 1})
        self.assertEqual(out["missing_names"]["orient"], ["Orient Bambino", "Orient Kamasu", "orient"])

    def test_other_reasons_folded(self):
        # F11: free-text codes fold into one citable `other`; the raw codes are kept apart.
        rows = [coded(1, reasons=["value_price", "other:busy dial"]),
                coded(2, reasons=["other:dial_ugly", "other:busy dial"]),
                coded(3, reasons=["Too Big"])]
        out = coding.aggregate(rows, {}, subjects=["a"])
        self.assertEqual(out["reasons"], {"value_price": 1, "other": 3})
        self.assertEqual(out["reasons_other"], ["Too Big", "other:busy dial", "other:dial_ugly"])


class TestSparseKappa(unittest.TestCase):
    """F10/G8: a kappa over near-empty codings is null, not 1.00 or 0.00."""

    def test_sparse_field_is_null_with_counts(self):
        p = [coded(i, worst=["a"] if i < 2 else []) for i in range(20)]
        q = [coded(i, worst=["a"] if i < 2 else []) for i in range(20)]
        out = coding.agreement(p, q)
        self.assertIsNone(out["worst"])
        self.assertEqual(out["n_nonempty"]["worst"], {"primary": 2, "audit": 2})
        self.assertIsNone(out["judge_stance"])
        self.assertEqual(out["relevant"], 1.0)

    def test_dense_field_kept(self):
        p = [coded(i, best=["a"] if i % 2 else ["b"]) for i in range(12)]
        self.assertEqual(coding.agreement(p, p)["best"], 1.0)

    def test_type_stance_fields(self):
        p = [coded(i, verdict_stance="agrees" if i % 2 else "disagrees") for i in range(12)]
        out = coding.agreement(p, p)
        self.assertEqual(out["verdict_stance"], 1.0)
        self.assertNotIn("selection_stance", out)


class TestPrepare(unittest.TestCase):
    def comments(self):
        cs = [{"id": f"c{i}", "text": f"I love Alpha number {i}", "like_count": i, "parent": "root"}
              for i in range(20)]
        cs.append({"id": "off", "text": "nothing here", "like_count": 0, "parent": "root"})
        cs.append({"id": "kw", "text": "the crown is nice", "like_count": 0, "parent": "root"})
        cs.append({"id": "r1", "text": "al agree", "like_count": 0, "parent": "c1"})
        return cs

    def run_prepare(self, run, seed=7):
        return coding.prepare(self.comments(), SUBJECTS, ["crown"], Path(run),
                              chunk=8, audit_n=5, seed=seed)

    def test_filter_chunks_reply_context_brief(self):
        with tempfile.TemporaryDirectory() as d:
            res = self.run_prepare(d)
            self.assertEqual(res["n_candidates"], 22)  # 20 + keyword + reply; "off" dropped
            chunks = sorted(Path(d).glob("chunk_*.jsonl"))
            self.assertEqual(len(chunks), 3)
            rows = [json.loads(l) for c in chunks for l in c.read_text().splitlines()]
            self.assertNotIn("off", [r["id"] for r in rows])
            reply = next(r for r in rows if r["id"] == "r1")
            self.assertEqual(reply["parent_text"], "I love Alpha number 1")
            brief = (Path(d) / "BRIEF.md").read_text()
            self.assertIn("| a | Alpha, Al |", brief)
            self.assertIn('"a", "b", "c"', brief)
            self.assertNotIn("{{", brief)

    def test_audit_sample_deterministic(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2, \
                tempfile.TemporaryDirectory() as d3:
            ids = lambda d: [json.loads(l)["id"] for l in
                             (Path(d) / "audit_sample.jsonl").read_text().splitlines()]
            self.run_prepare(d1, 7); self.run_prepare(d2, 7); self.run_prepare(d3, 8)
            self.assertEqual(ids(d1), ids(d2))
            self.assertEqual(len(ids(d1)), 5)
            self.assertNotEqual(ids(d1), ids(d3))


class TestCli(unittest.TestCase):
    def test_aggregate_and_agreement_merge_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "numbers.json").write_text(json.dumps({"keep": {"x": 1}}))
            f = run / "coded.jsonl"
            f.write_text("\n".join(json.dumps(r) for r in
                                   [coded(1, best=["a"], judge_stance="agree", full_ranking=["a", "b", "c"])]))
            env = {**os.environ}
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "coding", "aggregate",
                                "--run", d, "--coded", str(f)], env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            r = subprocess.run([sys.executable, "-I", str(SCRIPT), "coding", "agreement",
                                "--run", d, "--primary", str(f), "--audit", str(f)],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            nums = json.loads((run / "numbers.json").read_text())
            self.assertEqual(nums["keep"], {"x": 1})
            self.assertEqual(nums["viewers"]["best"]["a"], 1)
            self.assertIsNone(nums["coding_agreement"]["best"])  # one row: too sparse
            self.assertEqual(nums["coding_agreement"]["n_nonempty"]["best"], {"primary": 1, "audit": 1})


class TestFinalReviewCoding(unittest.TestCase):
    """Final review 5, 16, 17, 19, 22."""

    def test_ranking_omitting_one_subject_puts_it_last(self):
        # 5: a full_ranking of n-1 subjects implies the omitted one is last.
        out = coding.aggregate([coded(1, full_ranking=["a", "b"])], {}, subjects=["a", "b", "c"])
        self.assertEqual(out["n_rankings"], 1)
        self.assertEqual(out["last_place"], {"a": 0, "b": 0, "c": 1})
        self.assertEqual(out["pairwise_wins"], {"a>b": 1, "a>c": 1, "b>c": 1})
        self.assertEqual(out["borda"], {"a": 2, "b": 1, "c": 0})

    def test_missing_multi_word_brands(self):
        # 17: "Grand Seiko" is not "grand"; the brand field, then a multi-word list, decides.
        rows = [coded(1, missing=[{"brand": "Grand Seiko", "model": "SBGA211"}]),
                coded(2, missing=["Grand Seiko Snowflake"]),
                coded(3, missing=["Patek Philippe Calatrava", {"brand": "A. Lange & Söhne", "model": None}]),
                coded(4, missing=["Lange 1", {"brand": "Patek", "model": "5711"}]),
                coded(5, missing=[{"brand": None, "model": "Tag Heuer Carrera"}, "Seiko 5"])]
        out = coding.aggregate(rows, {}, subjects=["a"])
        self.assertEqual(out["missing"], {"grand-seiko": 2, "patek-philippe": 2,
                                          "a-lange-sohne": 2, "tag-heuer": 1, "seiko": 1})
        self.assertNotIn("grand", out["missing"])

    def test_bare_string_alias_is_one_alias(self):
        # 19: {"a": "Alpha"} must not be iterated letter by letter.
        subj = coding.normalize_subjects({"a": "Alpha", "b": ["Beta", "B2"], "c": None})
        self.assertEqual(subj, {"a": ["Alpha"], "b": ["Beta", "B2"], "c": []})
        with tempfile.TemporaryDirectory() as d:
            cs = [{"id": "1", "text": "pretty", "parent": "root"},
                  {"id": "2", "text": "Alpha wins", "parent": "root"}]
            res = coding.prepare(cs, {"a": "Alpha"}, [], Path(d), seed=1)
            self.assertEqual(res["n_candidates"], 1)
            self.assertIn("| a | Alpha |", (Path(d) / "BRIEF.md").read_text())

    def test_review_brief_states_the_verdict(self):
        # 22: coders need the presenter's verdict to code verdict_stance.
        v = [{"watch": "Rolex Perpetual Padellone", "stance": "positive",
              "quote": "This is the best Rolex of the year."}]
        brief = coding.render_brief(SUBJECTS, "review", verdicts=v)
        self.assertIn("Rolex Perpetual Padellone", brief)
        self.assertIn("positive", brief)
        self.assertIn("This is the best Rolex of the year.", brief)
        self.assertNotIn("{{", brief)
        none = coding.render_brief(SUBJECTS, "review")
        self.assertIn("not recorded", none)
        self.assertNotIn("{{", coding.render_brief(SUBJECTS, "contest", verdicts=v))
        self.assertNotIn("best Rolex", coding.render_brief(SUBJECTS, "contest", verdicts=v))


class TestPrepareCli(unittest.TestCase):
    """Final review 16 and 22 through the CLI."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name) / "run"
        self.run.mkdir()
        self.home = Path(self.tmp.name) / "home"
        (self.run / "subjects.json").write_text(json.dumps(SUBJECTS))
        (self.run / "comments.json").write_text(json.dumps([{"id": "1", "text": "Alpha", "parent": "root"}]))

    def prepare(self, *extra):
        env = {**os.environ, "TEDDY_COLLECTION_HOME": str(self.home)}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "coding", "prepare", "--run",
                               str(self.run / "coding"), "--comments", str(self.run / "comments.json"),
                               "--subjects", str(self.run / "subjects.json"), "--seed", "1", *extra],
                              capture_output=True, text=True, env=env)

    def test_missing_type_json_warns_and_is_recorded(self):
        # 16: the contest fallback is said on stderr and recorded in numbers.json.
        r = self.prepare()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("warning", r.stderr)
        self.assertIn("type.json", r.stderr)
        self.assertEqual(json.loads(r.stdout)["type_source"], "fallback")
        nums = json.loads((self.run / "numbers.json").read_text())
        self.assertEqual(nums["coding_prepare"]["type"], "contest")
        self.assertEqual(nums["coding_prepare"]["type_source"], "fallback")

    def test_type_json_no_warning(self):
        (self.run / "type.json").write_text(json.dumps({"type": "list"}))
        r = self.prepare()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("warning", r.stderr)
        self.assertEqual(json.loads(r.stdout)["type_source"], "type.json")

    def test_review_verdict_copied_from_dataset(self):
        # 22: the reviewed watch's verdict.quote and stance come from the dataset.
        (self.run / "type.json").write_text(json.dumps({"type": "review"}))
        (self.run / "records.json").write_text(json.dumps({"videos": [{"id": "v1"}]}))
        ds = self.home / "dataset"
        ds.mkdir(parents=True)
        (ds / "videos.json").write_text(json.dumps([{"id": "v1"}, {"id": "v2"}]))
        (ds / "watches.json").write_text(json.dumps([
            {"id": "w1", "brand": "Rolex", "model": "Perpetual Padellone"},
            {"id": "w2", "brand": "Rolex", "model": "1908"},
            {"id": "w3", "brand": "Omega", "model": "Other"}]))
        (ds / "appearances.json").write_text(json.dumps([
            {"video_id": "v1", "watch_id": "w1", "role": "reviewed",
             "verdict": {"stance": "positive", "quote": "Rolex at its most playful."}},
            {"video_id": "v1", "watch_id": "w2", "role": "mentioned"},
            {"video_id": "v2", "watch_id": "w3", "role": "reviewed",
             "verdict": {"stance": "negative", "quote": "Another video's verdict."}}]))
        r = self.prepare()
        self.assertEqual(r.returncode, 0, r.stderr)
        brief = (self.run / "coding" / "BRIEF.md").read_text()
        self.assertIn("Rolex Perpetual Padellone", brief)
        self.assertIn("Rolex at its most playful.", brief)
        self.assertIn("positive", brief)
        self.assertNotIn("Another video", brief)
        self.assertNotIn("1908", brief)


if __name__ == "__main__":
    unittest.main()
