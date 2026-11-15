import json, subprocess, sys, tempfile, threading, unittest
from unittest import mock
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection"
sys.path.insert(0, str(ROOT / "lib"))
from teddycoll import links  # noqa: E402

PAGES = {
    "/slgb009": (200, "<html><head><title>SLGB009 | Grand Seiko</title></head><body>x</body></html>"),
    "/slgb015": (200, "<html><head><title>SLGB015</title></head><body>nothing</body></html>"),
    "/body": (200, "<html><head><title>Product</title></head><body>Ref. 220.10.38.20.01.001 here</body></html>"),
    "/og": (200, '<html><head><meta property="og:title" content="Speedmaster 3861"></head></html>'),
    "/long": (200, "<html><head><title>SLGB0091 | Grand Seiko</title></head></html>"),
    "/blocked": (403, "forbidden"),
    "/ratelimited": (429, "slow down"),
    "/down": (503, "unavailable"),
    "/rolex-base": (200, "<html><head><title>Perpetual Padellone</title></head>"
                         "<body>Ref. 53505 in Everose gold</body></html>"),
    "/rolex-longer": (200, "<html><body>Ref. 535051 and 153505</body></html>"),
    "/tudor": (200, "<html><body>Black Bay ref. 79230B and ref 79230R</body></html>"),
    "/tudor-n": (200, "<html><body>Black Bay 58, ref. 79230N</body></html>"),
    "/timex": (200, "<html><head><title>Expedition® Field Post Titanium Automatic</title></head></html>"),
    "/tokens": (200, "<html><body>The Seiko Presage Cocktail Time automatic</body></html>"),
    "/missing": (404, "not found"),
    "/price": (200, "<html><body>Strap only $55.13, or 1,5513 points; was 5.513 last year</body></html>"),
    "/phone": (200, "<html><body>Call us on 555 1016 or (800) 555-6062</body></html>"),
    "/sub5513": (200, "<html><head><title>Rolex Submariner 5513</title></head><body>Ref. 6062</body></html>"),
}
HITS = {}


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/bogus":
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=bogus-xyz")
            self.end_headers(); self.wfile.write(b"<title>SLGB009</title>"); return
        if self.path == "/redir":
            self.send_response(302); self.send_header("Location", "/slgb009"); self.end_headers(); return
        HITS[self.path] = HITS.get(self.path, 0) + 1
        code, body = PAGES.get(self.path, (404, "nope"))
        self.send_response(code)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), H)
        cls.base = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown(); cls.srv.server_close()

    def u(self, p):
        return self.base + p

    def u2(self, p):
        """The same server under a second host name (a different host for host skipping)."""
        return self.base.replace("127.0.0.1", "localhost") + p


class TestVerify(Base):
    def test_title_match(self):
        r = links.verify(self.u("/slgb009"), ["SLGB009"])
        self.assertTrue(r["match"]); self.assertEqual(r["status"], 200)
        self.assertEqual(r["title"], "SLGB009 | Grand Seiko")
        self.assertEqual(r["matched_terms"], ["SLGB009"])
        self.assertEqual(r["kind"], "other"); self.assertIn("checked_at", r)

    def test_reference_normalised(self):
        self.assertTrue(links.verify(self.u("/body"), ["22010382001001"])["match"])

    def test_wrong_watch(self):
        r = links.verify(self.u("/slgb015"), ["SLGB009"])
        self.assertFalse(r["match"]); self.assertEqual(r["matched_terms"], [])

    def test_no_match_inside_longer_reference(self):
        self.assertFalse(links.verify(self.u("/long"), ["SLGB009"])["match"])

    def test_bogus_charset_still_verifies(self):
        r = links.verify(self.u("/bogus"), ["SLGB009"])
        self.assertTrue(r["match"]); self.assertEqual(r["status"], 200)

    def test_non_http_rejected(self):
        r = links.verify("file:///etc/hostname", ["x"])
        self.assertEqual(r["status"], 0); self.assertFalse(r["match"])
        self.assertEqual(links.verify("ftp://example.com/a", ["a"])["status"], 0)

    def test_og_title_and_redirect(self):
        self.assertTrue(links.verify(self.u("/og"), ["3861"])["match"])
        self.assertTrue(links.verify(self.u("/redir"), ["slgb-009"])["match"])

    def test_empty_expect_never_matches(self):
        self.assertFalse(links.verify(self.u("/slgb009"), ["", " . "])["match"])

    def test_kind_inference_and_hint(self):
        self.assertEqual(links.infer_kind("https://www.grand-seiko.com/x"), "brand")
        self.assertEqual(links.infer_kind("https://press.iwc.com/x"), "press")
        self.assertEqual(links.infer_kind("https://www.iwc.com/x"), "brand")
        self.assertEqual(links.infer_kind("https://unknown.example/x"), "other")
        self.assertEqual(links.verify(self.u("/slgb009"), ["x"], kind="dealer")["kind"], "dealer")


class TestUnreadable(Base):
    """G2/F4: a source that could not be read is `unreadable`, not `no_match`."""

    def test_statuses(self):
        for path, code in (("/blocked", 403), ("/ratelimited", 429), ("/down", 503)):
            r = links.verify(self.u(path), ["SLGB009"])
            self.assertEqual(r["status"], code)
            self.assertEqual(r["result"], "unreadable", path)
            self.assertFalse(r["match"])
        r = links.verify("http://127.0.0.1:1/x", ["SLGB009"])
        self.assertEqual((r["status"], r["result"]), (0, "unreadable"))

    def test_read_but_absent_is_no_match(self):
        self.assertEqual(links.verify(self.u("/slgb015"), ["SLGB009"])["result"], "no_match")
        self.assertEqual(links.verify(self.u("/missing"), ["SLGB009"])["result"], "no_match")
        self.assertEqual(links.verify(self.u("/slgb009"), ["SLGB009"])["result"], "match")

    def test_mocked_fetch_timeout(self):
        with mock.patch.object(links, "_fetch", return_value=(0, "")):
            self.assertEqual(links.verify("https://brand.example/x", ["A"])["result"], "unreadable")


class TestPartialReference(Base):
    """F5/G3: a page carrying the reference's core number is a `partial` match."""

    def page(self, ref, text):
        """The result of checking a watch with reference `ref` against a page of `text`."""
        body = f"<html><head><title>Watch</title></head><body>{text}</body></html>"
        with mock.patch.object(links, "_fetch", return_value=(200, body)):
            return links.verify_watch({"id": "x", "reference": ref,
                                       "sources": [{"url": "https://dealer.example/x"}]})["sources"][0]

    def test_partial_forms(self):
        self.assertEqual(links.partial_forms("M53505-0002"), {"53505-0002", "M53505", "53505"})
        self.assertEqual(links.partial_forms("5711/1A-010"), {"5711/1A"})
        self.assertEqual(links.partial_forms("WSSA0030"), set())      # 4 letters is not a brand prefix
        self.assertEqual(links.partial_forms("126610LN"), set())

    def test_review_counterexamples_do_not_match(self):
        # Review Important 2: different watches, a phone number and a price.
        for ref, text in (("WSSA0030", "Santos ref. WGSA0030 in yellow gold"),
                          ("WSSA0030", "Call us on 1 800 555 0030 today"),
                          ("WSSA0030", "Call us on (800) 555-0030 today"),
                          ("5711/1A-010", "Nautilus 5711/1R-001 in rose gold"),
                          ("5711/1A-010", "Nautilus 5711/1300A-001"),
                          ("CBN2A1A.BA0643", "Carrera CBN2A1B.BA0643 blue dial"),
                          ("M53505-0002", "Price 1,53505 USD"),
                          ("M53505-0002", "Price $53505"),
                          ("126610LN", "Submariner 126610LV"),
                          ("M126610LN-0001", "Submariner M126610LV-0002")):
            r = self.page(ref, text)
            self.assertFalse(r["match"], f"{ref} matched {text!r}: {r}")

    def test_prefix_and_suffix_variants_are_partial(self):
        for ref, text in (("M53505-0002", "Ref. 53505 in Everose gold"),
                          ("M53505-0002", "reference 53505-0002, press release"),
                          ("M53505-0002", "M53505 Perpetual"),
                          ("53505", "Rolex M53505-0002 Perpetual"),
                          ("5711/1A-010", "Nautilus 5711/1A in steel"),
                          ("M79230N-0001", "Black Bay 58, ref. 79230N")):
            r = self.page(ref, text)
            self.assertEqual(r["result"], "partial", f"{ref} vs {text!r}: {r}")
        self.assertEqual(self.page("126610LN", "Submariner 126610LN")["result"], "match")

    def test_base_reference_matches_partial(self):
        w = {"id": "p", "model": "Perpetual Padellone", "reference": "M53505-0002",
             "sources": [{"url": self.u("/rolex-base"), "kind": "press"}]}
        out = links.verify_watch(w)
        src = out["sources"][0]
        self.assertTrue(src["match"])
        self.assertEqual(src["result"], "partial")
        self.assertEqual(src["match_level"], "partial")
        self.assertEqual(src["matched_terms"], ["53505"])
        self.assertTrue(links.passes(out))

    def test_core_inside_longer_number_does_not_match(self):
        w = {"id": "p", "reference": "M53505-0002", "sources": [{"url": self.u("/rolex-longer")}]}
        self.assertFalse(links.passes(links.verify_watch(w)))

    def test_core_letter_suffix_must_match(self):
        # A different letter suffix is a different watch (79230B is not 79230N).
        w = {"id": "t", "reference": "M79230N-0001", "sources": [{"url": self.u("/tudor")}]}
        self.assertFalse(links.passes(links.verify_watch(w)))
        w["sources"] = [{"url": self.u("/tudor-n")}]
        self.assertEqual(links.verify_watch(w)["sources"][0]["result"], "partial")

    def test_full_reference_is_full(self):
        w = {"id": "g", "reference": "SLGB009", "sources": [{"url": self.u("/slgb009")}]}
        src = links.verify_watch(w)["sources"][0]
        self.assertEqual((src["result"], src["match_level"]), ("match", "full"))

    def test_trademark_signs_dropped(self):
        w = {"id": "t", "reference": None, "model": "Expedition Field Post Titanium Automatic",
             "sources": [{"url": self.u("/timex")}]}
        self.assertEqual(links.verify_watch(w)["sources"][0]["match_level"], "full")

    def test_model_tokens_in_order(self):
        w = {"id": "s", "reference": None, "model": "Presage Cocktail Time",
             "sources": [{"url": self.u("/tokens")}]}
        self.assertEqual(links.verify_watch(w)["sources"][0]["match_level"], "full")
        w["model"] = "Seiko Presage Automatic"
        src = links.verify_watch(w)["sources"][0]
        self.assertEqual((src["result"], src["match_level"]), ("partial", "tokens"))
        w["model"] = "Automatic Presage"   # out of order
        self.assertFalse(links.verify_watch(w)["sources"][0]["match"])


class TestVerifyWatch(Base):
    def w(self, *paths, **kw):
        w = {"id": "a", "model": "Seiko", "reference": "SLGB009",
             "sources": [{"url": self.u(p), "kind": "brand"} for p in paths]}
        w.update(kw)
        return w

    def test_blocked_then_fallback(self):
        out = links.verify_watch(self.w("/blocked", "/slgb009"))
        self.assertTrue(links.passes(out))
        self.assertEqual(out["sources"][0]["status"], 403)
        self.assertFalse(out["sources"][0]["match"])
        self.assertTrue(out["sources"][1]["match"])
        self.assertEqual(out["sources"][0]["kind"], "brand")

    def test_model_default_when_reference_empty(self):
        out = links.verify_watch(self.w("/slgb015", reference="", model="SLGB015"))
        self.assertTrue(links.passes(out))

    def test_all_404_fails(self):
        self.assertFalse(links.passes(links.verify_watch(self.w("/missing", "/missing"))))

    def test_unreachable_recorded(self):
        out = links.verify_watch(self.w("/x") | {"sources": [{"url": "http://127.0.0.1:1/x"}]})
        self.assertFalse(out["sources"][0]["match"]); self.assertEqual(out["sources"][0]["status"], 0)


class TestCli(Base):
    def run_cli(self, paths_, full=False):
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / "records.json"
            rec.write_text(json.dumps({"videos": [], "appearances": [], "watches": [
                {"id": "a", "model": "Seiko", "reference": "SLGB009",
                 "sources": [{"url": p if p.startswith("http") else self.u(p), "kind": "brand"}
                             for p in paths_]}]}))
            r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "teddy.py"),
                                "verify-links", str(rec)], capture_output=True, text=True)
            if full:
                return r.returncode, json.loads(rec.read_text()), r.stderr, json.loads(r.stdout)
            return r.returncode, json.loads(rec.read_text())

    def test_404_fails(self):
        code, rec = self.run_cli(["/missing"])
        self.assertEqual(code, 1)
        self.assertEqual(rec["watches"][0]["sources"][0]["status"], 404)

    def test_blocked_reported_as_unread(self):
        code, rec, err, out = self.run_cli(["/blocked", self.u2("/ratelimited")], full=True)
        self.assertEqual(code, 1)
        self.assertEqual(out["unreadable"], ["a"])
        self.assertEqual(out["no_matching_source"], [])
        self.assertIn("a: no source could be read (403, 429), unread", err)
        self.assertNotIn("no source matched", err)

    def test_only_rechecks_named_watches(self):
        # G16: --only fetches the named watches and leaves the others' rows untouched.
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / "records.json"
            rec.write_text(json.dumps({"watches": [
                {"id": "a", "reference": "SLGB009", "sources": [{"url": self.u("/slgb009")}]},
                {"id": "b", "reference": "SLGB009", "sources": [{"url": self.u("/slgb009")}]}]}))
            r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "teddy.py"),
                                "verify-links", str(rec), "--only", "b"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            ws = json.loads(rec.read_text())["watches"]
            self.assertNotIn("status", ws[0]["sources"][0])
            self.assertTrue(ws[1]["sources"][0]["match"])
            self.assertEqual(json.loads(r.stdout)["watches"], 1)

    def test_pass_writes_back(self):
        code, rec = self.run_cli(["/blocked", self.u2("/slgb009")])
        self.assertEqual(code, 0)
        self.assertTrue(rec["watches"][0]["sources"][1]["match"])
        self.assertEqual(rec["videos"], [])


class TestFinalReviewLinks(Base):
    """Final review 6, 15, 18."""

    def src(self, ref, path):
        w = {"id": "x", "reference": ref, "sources": [{"url": self.u(path)}]}
        return links.verify_watch(w)["sources"][0]

    def test_short_digit_reference_not_matched_in_prices_or_phones(self):
        # 6: full level ran on norm() text, so 5513 matched $55.13 and 1016 matched 555 1016.
        for ref, path in (("5513", "/price"), ("1016", "/phone"), ("6062", "/phone")):
            got = self.src(ref, path)
            self.assertFalse(got["match"], (ref, path, got))
        self.assertEqual(self.src("5513", "/sub5513")["match_level"], "full")
        self.assertEqual(self.src("6062", "/sub5513")["match_level"], "full")

    def cli(self, watches, *extra):
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / "records.json"
            rec.write_text(json.dumps({"watches": watches}))
            before = rec.read_text()
            r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "teddy.py"),
                                "verify-links", str(rec), *extra], capture_output=True, text=True)
            return r, json.loads(rec.read_text()), before == rec.read_text()

    def test_only_unknown_id(self):
        # 15: --only with an id not in records.json names it and exits 2, writing nothing.
        r, _, unchanged = self.cli([{"id": "a", "reference": "SLGB009",
                                     "sources": [{"url": self.u("/slgb009")}]}], "--only", "a", "zz")
        self.assertEqual(r.returncode, 2)
        self.assertIn("zz", r.stderr)
        self.assertTrue(unchanged)

    def test_host_skipped_after_429_or_403(self):
        # 18: after a 429 or 403 the host is not fetched again in this run.
        for path, code in (("/ratelimited", 429), ("/blocked", 403)):
            HITS.clear()
            r, rec, _ = self.cli([
                {"id": "a", "reference": "SLGB009", "sources": [{"url": self.u(path)}]},
                {"id": "b", "reference": "SLGB009", "sources": [{"url": self.u(path)},
                                                                {"url": self.u("/slgb009")},
                                                                {"url": self.u2("/slgb009")}]}])
            self.assertEqual(HITS.get(path), 1, path)
            self.assertNotIn("/slgb009", {k for k, v in HITS.items() if v > 1})
            b = rec["watches"][1]["sources"]
            self.assertEqual([s["result"] for s in b], ["unreadable", "unreadable", "match"])
            self.assertEqual(b[1]["status"], code)
            self.assertIn("skipped", b[1])
            self.assertEqual(json.loads(r.stdout)["unreadable"], ["a"])


if __name__ == "__main__":
    unittest.main()
