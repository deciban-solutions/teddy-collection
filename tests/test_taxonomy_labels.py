import contextlib, io, json, subprocess, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "teddy-collection" / "lib"))
from teddycoll import taxonomy  # noqa: E402

SCRIPT = ROOT / "plugins" / "teddy-collection" / "scripts" / "teddy.py"
FIX = Path(__file__).resolve().parent / "fixtures"


def crit(key="wr", rule="water_resistance_m >= 100", p=None, f=None):
    return {"key": key, "statement": "s", "kind": "must", "evidence_class": "deductive",
            "check": {"type": "deterministic", "rule": rule,
                      "planted": {"pass": p if p is not None else [{"water_resistance_m": 200}],
                                  "fail": f if f is not None else [{"water_resistance_m": 50}]}},
            "sources": []}


def tax(cat="dive", version="1", label="compiled", kind="shipped", **kw):
    t = {"id": f"{kind}:{cat}@{version}", "category": cat, "version": version, "label": label,
         "paradigm": "p", "created": "2026-11-14", "change_log": [],
         "layers": {"wearer": [], "watch": [crit()]},
         "spec_fields": {"water_resistance_m": "number: metres"}}
    t.update(kw)
    return t


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.shipped = root / "shipped"
        self.user = root / "user"
        self.shipped.mkdir()
        self.user.mkdir()
        self._old = (taxonomy.SHIPPED_DIR, taxonomy.USER_DIR)
        taxonomy.SHIPPED_DIR, taxonomy.USER_DIR = self.shipped, self.user
        self.addCleanup(lambda: setattr(taxonomy, "SHIPPED_DIR", self._old[0]))
        self.addCleanup(lambda: setattr(taxonomy, "USER_DIR", self._old[1]))

    def ship(self, t):
        n = t["id"].split(":", 1)[1]
        (self.shipped / f"{n}.json").write_text(json.dumps(t))


class TestLabels(Base):
    def test_label_required(self):
        t = tax()
        del t["label"]
        errs = taxonomy.validate(t)
        self.assertTrue(any("label" in e for e in errs), errs)
        self.assertEqual(taxonomy.validate(tax()), [])

    def test_bad_enums_refused(self):
        t = tax(label="final")
        t["layers"]["watch"][0]["kind"] = "nice"
        t["layers"]["watch"][0]["evidence_class"] = "vibes"
        t["layers"]["watch"][0]["check"]["type"] = "magic"
        self.assertEqual(len(taxonomy.validate(t)), 4)

    def test_id_version_consistency(self):
        t = tax()
        t["version"] = "2"
        self.assertTrue(taxonomy.validate(t))

    def test_runtime_draft_is_provisional(self):
        self.ship(tax(label="provisional"))
        new = taxonomy.branch("shipped:dive@1", {}, "r")
        self.assertEqual(taxonomy.get(new)["label"], "provisional")
        self.ship(tax(cat="field", label="compiled"))
        new = taxonomy.branch("shipped:field@1", {}, "r")
        self.assertEqual(taxonomy.get(new)["label"], "provisional")

    def test_shipped_readonly(self):
        self.ship(tax())
        before = {p.name: p.read_bytes() for p in self.shipped.iterdir()}
        new = taxonomy.branch("shipped:dive@1", {"coherence": [{"factor": "x"}]}, "r")
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.shipped.iterdir()})
        self.assertTrue((self.user / "dive@1.1.json").exists())
        self.assertEqual(new, "user:dive@1.1")

    def test_branch_ids_and_log(self):
        self.ship(tax(version="2", **{"id": "shipped:dive@2"}))
        a = taxonomy.branch("shipped:dive@2", {"layers": {"watch": [crit("depth")]}}, "add depth")
        b = taxonomy.branch(a, {}, "again")
        self.assertEqual((a, b), ("user:dive@2.1", "user:dive@2.2"))
        t = taxonomy.get(a)
        self.assertEqual(t["version"], "2.1")
        self.assertEqual([c["key"] for c in t["layers"]["watch"]], ["wr", "depth"])
        self.assertEqual(t["change_log"][-1]["reason"], "add depth")
        self.assertIn("date", t["change_log"][-1])
        self.assertIn("layers", t["change_log"][-1]["additions"])


class TestFixturePrivacy(Base):
    def test_fixture_has_no_owner_city(self):
        # the scrubbed word is stored only as a hash, so the test does not re-leak it
        import hashlib, re
        banned = "adab3ee5523a5d77a6aec62efbbc41da7f8d8d440523d906047da93a4b7aacde"
        words = re.findall(r"[a-z]+", (FIX / "fr_spec.json").read_text().lower())
        self.assertNotIn(banned, {hashlib.sha256(w.encode()).hexdigest() for w in words})


class TestCli(Base):
    def test_check_malformed_is_diagnosed(self):
        import importlib, contextlib, io
        sys.path.insert(0, str(SCRIPT.parent))
        teddy = importlib.import_module("teddy")
        t = tax()
        t["layers"]["watch"][0]["check"] = "judged"
        self.ship(t)
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            rc = teddy.main(["taxonomy", "check", "shipped:dive@1"])
        self.assertNotEqual(rc, 0)
        self.assertIn("error:", err.getvalue())

    def test_check_cli(self):
        self.ship(tax())
        # the CLI subprocess cannot see the patched dirs, so test via main()
        sys.path.insert(0, str(SCRIPT.parent))
        import importlib
        teddy = importlib.import_module("teddy")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(teddy.main(["taxonomy", "check", "shipped:dive@1"]), 0)
            self.assertEqual(teddy.main(["taxonomy", "list"]), 0)
        self.assertIn("shipped:dive@1", out.getvalue())
