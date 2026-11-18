import sys, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_taxonomy_labels import Base, crit, tax  # noqa: E402
from teddycoll import taxonomy  # noqa: E402


class TestVersions(Base):
    def test_old_versions_resolve(self):
        self.ship(tax(version="1"))
        self.ship(tax(version="2", **{"id": "shipped:dive@2"}))
        self.assertEqual(taxonomy.get("shipped:dive@1")["version"], "1")
        self.assertEqual(taxonomy.resolve("dive")["id"], "shipped:dive@2")

    def test_numeric_not_lexical(self):
        for n in ("2", "10"):
            self.ship(tax(version=n, **{"id": f"shipped:dive@{n}"}))
        self.assertEqual(taxonomy.resolve("dive")["id"], "shipped:dive@10")

    def test_user_branch_wins_and_minor_numeric(self):
        self.ship(tax(version="1"))
        self.ship(tax(version="2", **{"id": "shipped:dive@2"}))
        self.assertEqual(taxonomy.resolve("dive")["id"], "shipped:dive@2")
        ids = [taxonomy.branch("shipped:dive@2", {}, "r") for _ in range(10)]
        self.assertEqual(ids[-1], "user:dive@2.10")
        self.assertEqual(taxonomy.resolve("dive")["id"], "user:dive@2.10")
        self.assertEqual(taxonomy.resolve("dive")["version"], "2.10")

    def test_branch_of_older_shipped_yields_to_newer_shipped(self):
        self.ship(tax(version="1"))
        old = taxonomy.branch("shipped:dive@1", {}, "r")
        self.assertEqual(taxonomy.resolve("dive")["id"], old)
        self.ship(tax(version="2", **{"id": "shipped:dive@2"}))
        self.assertEqual(taxonomy.resolve("dive")["id"], "shipped:dive@2")
        self.assertEqual(taxonomy.get(old)["id"], old)  # still in the library by id

    def test_user_draft_without_shipped(self):
        t = tax(version="0.1", **{"id": "user:dive@0.1"})
        (Path(taxonomy.USER_DIR) / "dive@0.1.json").write_text(__import__("json").dumps(t))
        self.assertEqual(taxonomy.resolve("dive")["id"], "user:dive@0.1")

    def test_unknown(self):
        with self.assertRaises(KeyError):
            taxonomy.resolve("nothing")
        with self.assertRaises(ValueError):
            taxonomy.get("dive@1")


class TestSpecFields(Base):
    """F7: a branch can add spec_fields, and a rule may read only listed fields."""

    def test_rule_field_must_be_listed(self):
        t = tax()
        t["layers"]["watch"].append(crit(key="thin", rule="thickness_mm <= 10",
                                         p=[{"thickness_mm": 9}], f=[{"thickness_mm": 12}]))
        errs = taxonomy.validate(t)
        self.assertTrue(any("thickness_mm" in e and "spec_fields" in e for e in errs), errs)
        t["spec_fields"]["thickness_mm"] = "number: mm"
        self.assertEqual(taxonomy.validate(t), [])

    def test_branch_adds_spec_fields(self):
        self.ship(tax())
        additions = {"layers": {"watch": [crit(key="thin", rule="thickness_mm <= 10",
                                               p=[{"thickness_mm": 9}], f=[{"thickness_mm": 12}])]},
                     "spec_fields": {"thickness_mm": "number: case thickness in mm"}}
        new = taxonomy.branch("shipped:dive@1", additions, "thin")
        t = taxonomy.get(new)
        self.assertEqual(sorted(t["spec_fields"]), ["thickness_mm", "water_resistance_m"])

    def test_branch_without_spec_field_refused(self):
        self.ship(tax())
        additions = {"layers": {"watch": [crit(key="thin", rule="thickness_mm <= 10",
                                               p=[{"thickness_mm": 9}], f=[{"thickness_mm": 12}])]}}
        with self.assertRaisesRegex(ValueError, "thickness_mm"):
            taxonomy.branch("shipped:dive@1", additions, "thin")


class TestPlantedChecks(Base):
    def test_planted_checks(self):
        self.assertEqual(taxonomy.run_checks(tax()), [])
        swapped = tax()
        swapped["layers"]["watch"] = [crit(p=[{"water_resistance_m": 50}],
                                           f=[{"water_resistance_m": 200}])]
        self.assertEqual(len(taxonomy.run_checks(swapped)), 2)

    def test_unsafe_rules_error(self):
        spec = {"a": 5, "b": [1]}
        for rule in ("a.real > 1", "a[0] > 1", "(lambda: a)() > 1", "[i for i in b] == b",
                     "().__class__ == a", "-a > 1"):
            with self.assertRaises(ValueError, msg=rule) as cm:
                taxonomy.evaluate(rule, spec)
            self.assertIn("disallowed expression element", str(cm.exception), rule)
        with self.assertRaises(ValueError):
            taxonomy.evaluate("unknown_field > 1", spec)

    def test_negative_constants_and_short_circuit(self):
        self.assertTrue(taxonomy.evaluate("x >= -4", {"x": -3}))
        self.assertFalse(taxonomy.evaluate("x >= -4.5", {"x": -5}))
        self.assertFalse(taxonomy.evaluate("a and b", {"a": False}))
        self.assertTrue(taxonomy.evaluate("a or b", {"a": True}))
        with self.assertRaises(ValueError):
            taxonomy.evaluate("a and b", {"a": True})

    def test_run_checks_rejects_malformed(self):
        t = tax()
        t["layers"]["watch"] = [crit(p=["notadict"], f=[])]
        self.assertTrue(taxonomy.run_checks(t))
        t["layers"]["watch"] = [crit(rule=5, p=[{"a": 1}], f=[])]
        self.assertTrue(taxonomy.run_checks(t))

    def test_deterministic_needs_both_planted_cases(self):
        for p, f in (([], [{"water_resistance_m": 1}]), ([{"water_resistance_m": 200}], [])):
            t = tax()
            t["layers"]["watch"] = [crit(p=p, f=f)]
            self.assertTrue(any("planted" in e for e in taxonomy.validate(t)), (p, f))

    def test_category_slug(self):
        with self.assertRaises(ValueError):
            taxonomy.parse_id("user:../../x@1.1")
        with self.assertRaises(ValueError):
            taxonomy.get("shipped:Dive Watch@1")
        self.assertTrue(taxonomy.validate(tax(cat="../x", id="shipped:../x@1")))

    def test_operators(self):
        spec = {"m": "quartz", "d": 40, "ok": True}
        for rule, want in [("m in ['quartz', 'auto']", True), ("d > 38 and d <= 40", True),
                           ("not ok or d < 10", False), ("m not in ('quartz',)", False),
                           ("38 < d < 39", False), ("m == 'quartz'", True)]:
            self.assertEqual(taxonomy.evaluate(rule, spec), want, rule)


if __name__ == "__main__":
    unittest.main()
