import json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import infer  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"
FIX = Path(__file__).resolve().parent / "fixtures"
CRIT = json.loads((FIX / "two_watch_criteria.json").read_text())
RANK = json.loads((FIX / "two_watch_ranking.json").read_text())


class TestMetrics(unittest.TestCase):
    def test_tau_identity(self):
        x = {"a": 3, "b": 1, "c": 2}
        self.assertEqual(infer.kendall_tau_b(x, x), 1.0)

    def test_tau_reversed(self):
        self.assertEqual(infer.kendall_tau_b({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1}), -1.0)

    def test_single_tau_of_bracelets(self):
        taus = {k: t for t, k in infer.single(CRIT, RANK)}
        self.assertEqual(round(taus["F:n_bracelet"], 2), 0.86)

    def test_ties_fail_weighted(self):
        c = {"x": {"brit": 1, "adrien": 1, "teddy": 0}, "y": {"brit": 2, "adrien": 2, "teddy": 0}}
        self.assertEqual(infer.weighted_share(c, ("x", "y"), ["brit", "adrien", "teddy"]), 0.0)

    def test_weighted_share_reference_value(self):
        self.assertAlmostEqual(
            infer.weighted_share(CRIT, ("S:daily_driver", "W:sum_robustness"), RANK, n=400, seed=7),
            0.77, delta=0.03)

    def test_null_rate_shape(self):
        r = infer.null_rate(6, n_criteria=10, trials=5, seed=1)
        self.assertEqual(set(r), {1, 2, 3})
        self.assertTrue(all(0 <= v <= 1 for v in r.values()))


class TestLexicographic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lex = infer.lexicographic(CRIT, RANK, 2)

    def test_reproduces_two_watch_rule(self):
        self.assertIn(("F:n_wr100", "F:-max_thick"), self.lex[2])
        self.assertIn(("F:n_wr100", "F:-max_comp"), self.lex[2])

    def test_eight_minimal_length_two_rules(self):
        self.assertEqual(len(self.lex[2]), 8)

    def test_tied_pair_is_not_a_rule(self):
        c = {"x": {"a": 2, "b": 2, "c": 1}}
        self.assertEqual(infer.lexicographic(c, ["a", "b", "c"], 2), {1: [], 2: []})

    def test_minimal_excludes_extensions(self):
        c = {"x": {"a": 3, "b": 2, "c": 1}, "y": {"a": 1, "b": 2, "c": 3}}
        res = infer.lexicographic(c, ["a", "b", "c"], 2)
        self.assertEqual(res[1], [("x",)])
        self.assertEqual(res[2], [])


class TestCli(unittest.TestCase):
    def test_infer_writes_files_and_merges_numbers(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d)
            (run / "numbers.json").write_text(json.dumps({"keep": 1}))
            p = subprocess.run([sys.executable, "-I", str(SCRIPT), "infer", str(FIX / "two_watch_criteria.json"),
                                str(FIX / "two_watch_ranking.json"), "--run", d, "--max-len", "2"],
                               capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertTrue((run / "infer.json").exists())
            nums = json.loads((run / "numbers.json").read_text())
            self.assertEqual(nums["keep"], 1)
            self.assertEqual(nums["infer"]["rules"]["2"]["count"], 8)
            self.assertEqual(nums["infer"]["top_single"][0]["tau"], 0.86)

    def test_missing_subject_is_an_error(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "c.json").write_text(json.dumps({"x": {"a": 1}}))
            (Path(d) / "r.json").write_text(json.dumps(["a", "b"]))
            p = subprocess.run([sys.executable, "-I", str(SCRIPT), "infer", str(Path(d) / "c.json"),
                                str(Path(d) / "r.json"), "--run", d], capture_output=True, text=True)
            self.assertEqual(p.returncode, 2)


class TestNullComparable(unittest.TestCase):
    """Final review 8: the null draws as many random criteria as the real criterion set."""

    def test_null_uses_every_criterion_count(self):
        crit = {f"k{i}": {s: (i * 7 + j * 3) % 5 for j, s in enumerate("abcdef")} for i in range(45)}
        target = list("abcdef")
        calls = []
        real = infer.null_rate

        def spy(n_items, n_criteria=40, **kw):
            calls.append(n_criteria)
            return real(n_items, n_criteria, trials=2, **kw)
        infer.null_rate = spy
        try:
            res = infer.run(crit, target, max_len=2)
        finally:
            infer.null_rate = real
        self.assertEqual(calls, [45])
        self.assertEqual(res["null_n_criteria"], 45)
        self.assertEqual(res["n_criteria"], 45)

    def test_pruned_search_matches_brute_force(self):
        import itertools, random
        def brute(n_items, n_criteria, trials, seed, max_len):
            rnd = random.Random(seed)
            items = list(range(n_items))
            hits = {r: 0 for r in range(1, max_len + 1)}
            for _ in range(trials):
                rows = [[rnd.randint(1, 5) for _ in items] for _ in range(n_criteria)]
                for r in hits:
                    for combo in itertools.permutations(range(n_criteria), r):
                        vals = [tuple(rows[i][p] for i in combo) for p in items]
                        if len(set(vals)) == n_items and all(vals[i] > vals[i + 1] for i in range(n_items - 1)):
                            hits[r] += 1
                            break
            return {r: hits[r] / trials for r in hits}
        for n_items, n_crit, seed in ((4, 12, 1), (5, 20, 3), (6, 25, 7)):
            self.assertEqual(infer.null_rate(n_items, n_crit, trials=15, seed=seed),
                             brute(n_items, n_crit, 15, seed, 3), (n_items, n_crit, seed))


if __name__ == "__main__":
    unittest.main()
