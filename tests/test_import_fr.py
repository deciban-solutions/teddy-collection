"""import_fr: a formalized-reasoner compile becomes a `compiled` taxonomy, with nothing defaulted.

The compile supplies three files: its spec.json, a sidecar written for the plug-in (each
criterion's layer and plug-in rule with planted cases), and optionally the ratification record.
The importer refuses, with every reason at once, anything it would otherwise have to guess.
"""
import copy, io, json, sys, tempfile, unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "scripts"))
from teddycoll import taxonomy  # noqa: E402

SPEC = {
    "slice": "gmt-selection",
    "culture": "A GMT watch this buyer will wear, chosen on verified specs and fair value.",
    "paradigm": {"culture": "A GMT watch this buyer will wear, chosen on verified specs and fair value.",
                 "stance": ["Evidence first", "Value-aware"],
                 "non_negotiables": ["never score a spec no source verifies"]},
    "owner_desiderata": [
        {"id": "D1", "statement": "Shows a second zone", "kind": "constraining", "source": "A"},
        {"id": "D2", "statement": "Scratch resistance", "kind": "value", "source": "D"},
        {"id": "D3", "statement": "Matches the buyer's zone use", "kind": "adaptive", "source": "E"},
        {"id": "D4", "statement": "Fair price", "kind": "value", "source": "C"},
    ],
    "concepts": [
        {"name": "Second time zone", "canon": "second_time_zone", "kind": "static",
         "description": "Shows a second zone on a 24-hour scale.", "serves": ["D1"]},
        {"name": "Sapphire crystal", "canon": "sapphire_crystal", "kind": "static",
         "description": "Sapphire resists scratches.", "serves": ["D2", "D1"]},
        {"name": "Zone pattern", "canon": "zone_pattern", "kind": "static",
         "description": "How the buyer uses a second zone.", "serves": ["D3"]},
        {"name": "Fair value", "canon": "fair_value", "kind": "static",
         "description": "Priced at or below same-spec peers.", "serves": ["D4"]},
        {"name": "Dropped idea", "canon": "dropped_idea", "kind": "static",
         "description": "Rejected in the compile.", "serves": ["D2"]},
    ],
    "accepted": ["second_time_zone", "sapphire_crystal", "fair_value"],
    "rejected": ["dropped_idea"],
    "edges": [{"from": "zone_pattern", "to": "second_time_zone", "warrant": "hypothesis"},
              {"from": "fair_value", "to": "sapphire_crystal", "warrant": "validated"}],
    "coherence_factors": [
        {"name": "traveller_needs_flyer", "scope": ["wearer.zone_pattern", "watch.gmt_type"],
         "kind": "identity", "enforcement": "machine_gate",
         "rationale": "A traveller is served by a flyer GMT.", "validated": True},
        {"name": "looks_match_use", "scope": ["watch.style"], "kind": "hedonic",
         "enforcement": "judged_review", "rationale": "Style suits the occasion.", "validated": True},
    ],
    "debt": [{"id": "d1", "resolved": False}, {"id": "d2", "resolved": True},
             {"id": "d3", "resolved": False}],
    "freeze_commit": "abc1234",
    "prereg": "docs/prereg-gmt-compile.md",
}

CHECKS = {
    "spec_fields": {"complications": "list of lower-case strings",
                    "crystal_material": "string: sapphire, mineral or acrylic"},
    "ratifier_role": "the builder",
    "criteria": {
        "second_time_zone": {"layer": "watch", "rule": "'gmt' in complications",
                             "planted": {"pass": [{"complications": ["gmt", "date"]}],
                                         "fail": [{"complications": ["date"]}]},
                             "sources": ["https://example.org/gmt-guide"]},
        "sapphire_crystal": {"layer": "watch", "rule": "crystal_material == 'sapphire'",
                             "planted": {"pass": [{"crystal_material": "sapphire"}],
                                         "fail": [{"crystal_material": "mineral"}]}},
        "zone_pattern": {"layer": "wearer"},
        "fair_value": {"layer": "watch"},
    },
}

RATIFIED = {"ratified": True, "instrument": "construction-validity (coherence_ratify)",
            "slice": "gmt-selection", "freeze_commit": "abc1234",
            "catch_power": 1.0, "caught": ["p1", "p2", "p3"], "false_positive_on_coherent": [],
            "graded": "2026-12-01T10:00:00Z", "ratifier": "author (A. Person)"}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def files(self, spec=SPEC, checks=CHECKS, rat=RATIFIED):
        paths = []
        for name, obj in (("spec.json", spec), ("checks.json", checks), ("rat.json", rat)):
            if obj is None:
                paths.append(None)
                continue
            p = self.d / name
            p.write_text(json.dumps(obj), encoding="utf-8")
            paths.append(p)
        return paths

    def imp(self, spec=SPEC, checks=CHECKS, rat=RATIFIED):
        s, c, r = self.files(spec, checks, rat)
        return taxonomy.import_fr(s, c, category="gmt", version="2", ratification_json=r)

    def refused(self, **kw):
        with self.assertRaises(taxonomy.ImportRefused) as cm:
            self.imp(**kw)
        return " | ".join(cm.exception.reasons)

    @staticmethod
    def crit(t, key):
        for layer, crits in t["layers"].items():
            for c in crits:
                if c["key"] == key:
                    return layer, c
        raise KeyError(key)


class TestImport(Base):
    def test_valid_compiled_taxonomy(self):
        t = self.imp()
        self.assertEqual(t["id"], "shipped:gmt@2")
        self.assertEqual(t["label"], "compiled")
        self.assertEqual(taxonomy.validate(t), [])
        self.assertEqual(taxonomy.run_checks(t), [])

    def test_kind_is_the_strictest_served(self):
        self.assertEqual(self.crit(self.imp(), "second_time_zone")[1]["kind"], "must")
        # serves D2 (value) and D1 (constraining): constraining wins
        self.assertEqual(self.crit(self.imp(), "sapphire_crystal")[1]["kind"], "must")
        self.assertEqual(self.crit(self.imp(), "fair_value")[1]["kind"], "more_is_better")
        self.assertEqual(self.crit(self.imp(), "zone_pattern")[1]["kind"], "evidence_settled")

    def test_evidence_class_is_the_weakest_served(self):
        t = self.imp()
        self.assertEqual(self.crit(t, "second_time_zone")[1]["evidence_class"], "deductive")
        self.assertEqual(self.crit(t, "sapphire_crystal")[1]["evidence_class"], "practitioner")
        self.assertEqual(self.crit(t, "fair_value")[1]["evidence_class"], "research")
        self.assertEqual(self.crit(t, "zone_pattern")[1]["evidence_class"], "contested")

    def test_layers_checks_and_sources_come_from_the_sidecar(self):
        t = self.imp()
        layer, c = self.crit(t, "zone_pattern")
        self.assertEqual(layer, "wearer")
        self.assertEqual(c["check"]["type"], "judged")
        layer, c = self.crit(t, "second_time_zone")
        self.assertEqual((layer, c["check"]["type"]), ("watch", "deterministic"))
        self.assertEqual(c["sources"], ["https://example.org/gmt-guide"])
        self.assertEqual(c["serves"], ["D1"])
        self.assertEqual(t["spec_fields"], CHECKS["spec_fields"])

    def test_rejected_concepts_are_dropped_and_logged(self):
        t = self.imp()
        with self.assertRaises(KeyError):
            self.crit(t, "dropped_idea")
        self.assertIn("dropped_idea", json.dumps(t["change_log"]))

    def test_coherence_factors_carried(self):
        names = {f["name"]: f for f in self.imp()["coherence"]}
        self.assertEqual(set(names), {"traveller_needs_flyer", "looks_match_use"})
        self.assertEqual(names["traveller_needs_flyer"]["enforcement"], "machine_gate")

    def test_paradigm_text_is_the_stance(self):
        self.assertTrue(self.imp()["paradigm"].startswith("A GMT watch this buyer will wear"))

    def test_warrant(self):
        w = self.imp()["warrant"]
        self.assertEqual(w["source_slice"], "gmt-selection")
        self.assertEqual(w["freeze_commit"], "abc1234")
        self.assertEqual(w["prereg"], "docs/prereg-gmt-compile.md")
        self.assertTrue(w["ratified"])
        self.assertEqual(w["ratified_by"], "the builder")
        self.assertEqual(w["catch_power"], 1.0)
        self.assertEqual(w["ratified_on"], "2026-12-01")
        self.assertEqual(w["unresolved_debt"], 2)
        self.assertEqual(w["edges"], {"total": 2, "validated": 1})
        # validated in the compile but with no plug-in rule: disclosed, not silently judged
        self.assertIn("fair_value", w["not_enforced_here"])
        self.assertIn("traveller_needs_flyer", w["not_enforced_here"])
        self.assertNotIn("looks_match_use", w["not_enforced_here"])

    def test_ratifier_name_is_never_copied(self):
        self.assertNotIn("A. Person", json.dumps(self.imp()))

    def test_no_ratification_record_is_unratified(self):
        w = self.imp(rat=None)["warrant"]
        self.assertFalse(w["ratified"])
        self.assertIsNone(w["ratified_by"])

    def test_failed_ratification_is_unratified(self):
        for bad in ({**RATIFIED, "ratified": False}, {**RATIFIED, "catch_power": 0.0},
                    {**RATIFIED, "false_positive_on_coherent": ["c1"]}):
            self.assertFalse(self.imp(rat=bad)["warrant"]["ratified"], bad)

    def test_coherence_factors_are_carried_but_not_claimed_as_enforced(self):
        # the scorer sees only the watch record, so no coherence factor is scored yet
        t = self.imp()
        self.assertIn("traveller_needs_flyer", t["warrant"]["not_enforced_here"])
        self.assertIn("coherence", t["warrant"]["not_enforced_note"])


    def test_validate_checks_the_warrant(self):
        t = self.imp()
        t["warrant"] = "trust me"
        self.assertTrue(taxonomy.validate(t))
        t = self.imp()
        t["label"] = "provisional"
        self.assertTrue(taxonomy.validate(t))


class TestRefusals(Base):
    def test_missing_paradigm(self):
        spec = {k: v for k, v in SPEC.items() if k != "paradigm"}
        self.assertIn("paradigm", self.refused(spec=spec))

    def test_missing_freeze(self):
        spec = {k: v for k, v in SPEC.items() if k != "freeze_commit"}
        self.assertIn("freeze_commit", self.refused(spec=spec))

    def test_concept_without_sidecar_entry(self):
        checks = copy.deepcopy(CHECKS)
        del checks["criteria"]["fair_value"]
        self.assertIn("fair_value", self.refused(checks=checks))

    def test_concept_serving_nothing(self):
        spec = copy.deepcopy(SPEC)
        spec["concepts"][3]["serves"] = []
        self.assertIn("fair_value", self.refused(spec=spec))

    def test_serves_unknown_desideratum(self):
        spec = copy.deepcopy(SPEC)
        spec["concepts"][3]["serves"] = ["D9"]
        self.assertIn("D9", self.refused(spec=spec))

    def test_rule_that_fails_its_planted_cases(self):
        checks = copy.deepcopy(CHECKS)
        checks["criteria"]["sapphire_crystal"]["planted"]["fail"] = [{"crystal_material": "sapphire"}]
        self.assertIn("sapphire_crystal", self.refused(checks=checks))

    def test_rule_without_planted_cases(self):
        checks = copy.deepcopy(CHECKS)
        del checks["criteria"]["sapphire_crystal"]["planted"]
        self.assertIn("sapphire_crystal", self.refused(checks=checks))

    def test_rule_reading_an_unlisted_field(self):
        checks = copy.deepcopy(CHECKS)
        checks["criteria"]["sapphire_crystal"]["rule"] = "crystal == 'sapphire'"
        checks["criteria"]["sapphire_crystal"]["planted"] = {
            "pass": [{"crystal": "sapphire"}], "fail": [{"crystal": "mineral"}]}
        self.assertIn("crystal", self.refused(checks=checks))

    def test_unsafe_rule(self):
        checks = copy.deepcopy(CHECKS)
        checks["criteria"]["sapphire_crystal"]["rule"] = "__import__('os').system('true')"
        self.assertIn("sapphire_crystal", self.refused(checks=checks))

    def test_unvalidated_coherence_factor(self):
        spec = copy.deepcopy(SPEC)
        spec["coherence_factors"][0]["validated"] = False
        self.assertIn("traveller_needs_flyer", self.refused(spec=spec))

    def test_bad_layer(self):
        checks = copy.deepcopy(CHECKS)
        checks["criteria"]["zone_pattern"]["layer"] = "wrist"
        self.assertIn("zone_pattern", self.refused(checks=checks))

    def test_ratified_without_a_role(self):
        checks = {k: v for k, v in CHECKS.items() if k != "ratifier_role"}
        self.assertIn("ratifier_role", self.refused(checks=checks))

    def test_all_reasons_reported_together(self):
        spec = {k: v for k, v in SPEC.items() if k not in ("paradigm", "freeze_commit")}
        text = self.refused(spec=spec)
        self.assertIn("paradigm", text)
        self.assertIn("freeze_commit", text)

    def test_bad_category_or_version(self):
        s, c, r = self.files()
        with self.assertRaises(taxonomy.ImportRefused):
            taxonomy.import_fr(s, c, category="GMT watches", version="2", ratification_json=r)
        with self.assertRaises(taxonomy.ImportRefused):
            taxonomy.import_fr(s, c, category="gmt", version="2.1", ratification_json=r)


class TestCli(Base):
    def run_cli(self, *argv):
        import teddy
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            rc = teddy.main(["taxonomy", "import-fr", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_cli_imports_and_writes(self):
        s, c, r = self.files()
        dest = self.d / "gmt@2.json"
        rc, out, _ = self.run_cli(str(s), "--checks", str(c), "--ratification", str(r),
                                  "--category", "gmt", "--version", "2", "--out", str(dest))
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(dest.read_text())["id"], "shipped:gmt@2")
        self.assertEqual(json.loads(out)["id"], "shipped:gmt@2")

    def test_cli_refusal_lists_reasons(self):
        spec = {k: v for k, v in SPEC.items() if k != "freeze_commit"}
        s, c, _ = self.files(spec=spec)
        rc, _, err = self.run_cli(str(s), "--checks", str(c), "--category", "gmt", "--version", "2")
        self.assertEqual(rc, 2)
        self.assertIn("freeze_commit", err)

    def test_cli_requires_checks_category_version(self):
        s, _, _ = self.files()
        rc, _, err = self.run_cli(str(s))
        self.assertEqual(rc, 2)
        self.assertIn("--checks", err)


if __name__ == "__main__":
    unittest.main()


class TestReviewFixes(Base):
    """Findings from the 2026-11-16 review, each pinned."""

    def test_branching_a_compiled_taxonomy(self):  # C1
        shipped = self.d / "shipped"
        shipped.mkdir()
        old = (taxonomy.SHIPPED_DIR, taxonomy.USER_DIR)
        taxonomy.SHIPPED_DIR, taxonomy.USER_DIR = shipped, self.d / "user"
        self.addCleanup(lambda: (setattr(taxonomy, "SHIPPED_DIR", old[0]),
                                 setattr(taxonomy, "USER_DIR", old[1])))
        (shipped / "gmt@2.json").write_text(json.dumps(self.imp()))
        new = taxonomy.branch("shipped:gmt@2", {"paradigm": "x"}, "r")
        b = taxonomy.get(new)
        self.assertEqual(b["label"], "provisional")
        self.assertNotIn("warrant", b)
        self.assertEqual(b["change_log"][-1]["derived_from"], "shipped:gmt@2")
        self.assertTrue(b["change_log"][-1]["base_ratified"])

    def test_judged_concepts_are_disclosed(self):  # I1
        w = self.imp()["warrant"]
        self.assertEqual(w["not_validated_in_compile"], ["zone_pattern"])

    def test_record_must_be_bound_to_the_compile(self):  # I2
        other = {k: v for k, v in RATIFIED.items() if k not in ("slice", "freeze_commit")}
        self.assertIn("ratification", self.refused(rat=other))
        self.assertIn("ratification", self.refused(rat={**RATIFIED, "slice": "citywalk"}))

    def test_record_bound_by_hash_in_sidecar(self):  # I2
        import hashlib
        other = {k: v for k, v in RATIFIED.items() if k not in ("slice", "freeze_commit")}
        s, c, r = self.files(rat=other)
        checks = {**CHECKS, "ratification_sha256": hashlib.sha256(r.read_bytes()).hexdigest()}
        c.write_text(json.dumps(checks))
        t = taxonomy.import_fr(s, c, category="gmt", version="2", ratification_json=r)
        self.assertTrue(t["warrant"]["ratified"])
        self.assertEqual(len(t["warrant"]["ratification_sha256"]), 64)

    def test_role_is_from_an_allow_list(self):  # I3
        self.assertIn("ratifier_role", self.refused(checks={**CHECKS, "ratifier_role": "author (A. Person)"}))

    def test_ratifier_name_anywhere_is_refused(self):  # I3
        spec = copy.deepcopy(SPEC)
        spec["concepts"][0]["description"] = "Checked by Person."
        self.assertIn("name", self.refused(spec=spec))

    def test_unreached_disallowed_syntax_is_refused(self):  # I4
        checks = copy.deepcopy(CHECKS)
        checks["criteria"]["sapphire_crystal"]["rule"] = (
            "(crystal_material == 'x' and crystal_material + 1 > 2) or crystal_material == 'sapphire'")
        self.assertIn("BinOp", self.refused(checks=checks))

    def test_validate_refuses_disallowed_syntax(self):  # I4
        t = self.imp()
        t["layers"]["watch"][0]["check"]["rule"] = "complications[0] == 'gmt' or 'gmt' in complications"
        self.assertTrue(any("Subscript" in e for e in taxonomy.validate(t)))

    def test_wrong_types_refuse_not_crash(self):  # I5, M4
        bad_specs = []
        for path, value in ((("concepts",), SPEC["concepts"] + ["oops"]),
                            (("accepted",), [{"canon": "x"}]),
                            (("owner_desiderata",), 5), (("edges",), 3), (("debt",), "x"),
                            (("coherence_factors",), {"a": 1})):
            s = copy.deepcopy(SPEC); s[path[0]] = value; bad_specs.append(s)
        for i, field, value in ((0, "canon", ["x"]), (0, "serves", [["D1"]])):
            s = copy.deepcopy(SPEC); s["concepts"][i][field] = value; bad_specs.append(s)
        s = copy.deepcopy(SPEC); del s["concepts"][0]["canon"]; bad_specs.append(s)
        for s in bad_specs:
            self.refused(spec=s)
        c = copy.deepcopy(CHECKS); c["criteria"]["zone_pattern"]["layer"] = ["wearer"]
        self.refused(checks=c)
        self.refused(checks={**CHECKS, "ratifier_role": 7})
        self.refused(rat=[1, 2])

    def test_unknown_enforcement_is_refused(self):  # I6
        spec = copy.deepcopy(SPEC)
        del spec["coherence_factors"][0]["enforcement"]
        self.assertIn("enforcement", self.refused(spec=spec))

    def test_duplicates_are_refused(self):  # M1
        spec = copy.deepcopy(SPEC); spec["concepts"].append(copy.deepcopy(SPEC["concepts"][0]))
        self.assertIn("second_time_zone", self.refused(spec=spec))
        spec = copy.deepcopy(SPEC); spec["owner_desiderata"].append(dict(SPEC["owner_desiderata"][0]))
        self.assertIn("D1", self.refused(spec=spec))

    def test_empty_rule_or_planted_without_rule(self):  # M2
        c = copy.deepcopy(CHECKS); c["criteria"]["sapphire_crystal"]["rule"] = ""
        self.assertIn("sapphire_crystal", self.refused(checks=c))
        c = copy.deepcopy(CHECKS); del c["criteria"]["sapphire_crystal"]["rule"]
        self.assertIn("sapphire_crystal", self.refused(checks=c))

    def test_record_fields_are_strict(self):  # M3
        no_fp = {k: v for k, v in RATIFIED.items() if k != "false_positive_on_coherent"}
        for bad in (no_fp, {**RATIFIED, "catch_power": True}, {**RATIFIED, "catch_power": 1.5}):
            self.assertIn("ratification", self.refused(rat=bad), bad)

    def test_sidecar_content_types(self):  # M5
        c = copy.deepcopy(CHECKS); c["criteria"]["second_time_zone"]["sources"] = [5]
        self.assertIn("second_time_zone", self.refused(checks=c))
        c = copy.deepcopy(CHECKS); c["spec_fields"] = {**CHECKS["spec_fields"], "x": 5}
        self.assertIn("spec_fields", self.refused(checks=c))
        c = copy.deepcopy(CHECKS); c["sources"] = [{"url": "https://x"}]
        self.assertIn("sources", self.refused(checks=c))

    def test_validate_requires_a_full_warrant(self):  # M6
        t = self.imp()
        t["warrant"] = {"ratified": True}
        self.assertTrue(taxonomy.validate(t))
        t = self.imp()
        t["warrant"]["not_enforced_here"] = "fair_value"
        self.assertTrue(taxonomy.validate(t))

    def test_accepted_without_a_concept(self):  # M11
        spec = copy.deepcopy(SPEC); spec["accepted"] = SPEC["accepted"] + ["ghost"]
        self.assertIn("ghost", self.refused(spec=spec))

    def test_accepted_as_dict_keys(self):  # real compiles key accepted/rejected by canon
        spec = copy.deepcopy(SPEC)
        spec["accepted"] = {k: {} for k in SPEC["accepted"]}
        spec["rejected"] = {k: {} for k in SPEC["rejected"]}
        self.assertEqual(self.imp(spec=spec)["id"], "shipped:gmt@2")

    def test_cli_out_name_must_match_in_shipped_dir(self):  # M10
        import teddy
        s, c, r = self.files()
        shipped = self.d / "shipped"; shipped.mkdir()
        old = taxonomy.SHIPPED_DIR
        taxonomy.SHIPPED_DIR = shipped
        self.addCleanup(lambda: setattr(taxonomy, "SHIPPED_DIR", old))
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()) as err:
            rc = teddy.main(["taxonomy", "import-fr", str(s), "--checks", str(c), "--ratification",
                             str(r), "--category", "gmt", "--version", "2",
                             "--out", str(shipped / "gmt@3.json")])
        self.assertEqual(rc, 2)
        self.assertIn("gmt@2.json", err.getvalue())


class TestNotExported(Base):
    """Decision 47 of the GMT compile: concepts that judge the whole page, not a watch, are
    listed in the sidecar's not_exported with a reason and disclosed in the warrant."""

    def checks(self, reason="judges the whole recommendation page, not a watch"):
        c = copy.deepcopy(CHECKS)
        del c["criteria"]["fair_value"]
        c["not_exported"] = [{"canon": "fair_value", "reason": reason}]
        return c

    def test_listed_concept_is_left_out_and_disclosed(self):
        t = self.imp(checks=self.checks())
        with self.assertRaises(KeyError):
            self.crit(t, "fair_value")
        self.assertEqual(t["warrant"]["not_exported"],
                         [{"key": "fair_value", "kind": "more_is_better",
                           "reason": "judges the whole recommendation page, not a watch"}])
        self.assertNotIn("fair_value", t["warrant"]["not_enforced_here"])
        self.assertEqual(taxonomy.validate(t), [])

    def test_reason_required(self):
        self.assertIn("fair_value", self.refused(checks=self.checks(reason="")))

    def test_not_both_exported_and_not(self):
        c = self.checks()
        c["criteria"]["fair_value"] = {"layer": "watch"}
        self.assertIn("fair_value", self.refused(checks=c))

    def test_unknown_or_rejected_name_refused(self):
        c = self.checks()
        c["not_exported"].append({"canon": "ghost", "reason": "x"})
        self.assertIn("ghost", self.refused(checks=c))

    def test_malformed_list_refused(self):
        for bad in ({"fair_value": "x"}, ["fair_value"], [{"canon": "fair_value"}],
                    [{"canon": "fair_value", "reason": "a"}, {"canon": "fair_value", "reason": "b"}]):
            c = copy.deepcopy(CHECKS)
            del c["criteria"]["fair_value"]
            c["not_exported"] = bad
            self.assertIn("not_exported", self.refused(checks=c), bad)

    def test_must_concepts_can_be_left_out_but_are_named(self):
        c = copy.deepcopy(CHECKS)
        del c["criteria"]["second_time_zone"]
        c["not_exported"] = [{"canon": "second_time_zone", "reason": "page-level"}]
        w = self.imp(checks=c)["warrant"]
        self.assertEqual(w["not_exported"][0]["kind"], "must")
