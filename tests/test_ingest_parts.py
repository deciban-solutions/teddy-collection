"""Ingest in two passes (text first, then the heavy parts) and discarding a stopped run."""
import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "scripts"))
from teddycoll import ingest  # noqa: E402
from test_ingest_degrades import URL, VID, good  # noqa: E402
import teddy  # noqa: E402


class TestIngestParts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name)
        self.calls = []
        f = good()
        for k in ("comments", "video"):
            inner = f[k]
            f[k] = (lambda inner, k: lambda vid, run: (self.calls.append(k), inner(vid, run))[1])(inner, k)
        self.f = f

    def tearDown(self):
        self.tmp.cleanup()

    def test_text_pass_skips_comments_and_video(self):
        st = ingest.run_ingest(URL, self.run, fetchers=self.f, parts=("transcript",))
        self.assertEqual(set(st), {"metadata", "transcript"})
        self.assertEqual(self.calls, [])
        self.assertTrue((self.run / VID / "transcript.txt").exists())

    def test_second_pass_adds_heavy_parts(self):
        ingest.run_ingest(URL, self.run, fetchers=self.f, parts=("transcript",))
        st = ingest.run_ingest(URL, self.run, fetchers=self.f, parts=("comments", "video"))
        self.assertEqual(st["comments"]["status"], "ok")
        self.assertEqual(sorted(self.calls), ["comments", "video"])
        self.assertTrue((self.run / VID / "transcript.txt").exists())

    def test_default_fetches_everything(self):
        st = ingest.run_ingest(URL, self.run, fetchers=self.f)
        self.assertEqual(list(st), ["transcript", "metadata", "comments", "video"])

    def test_cli_parts_flag(self):
        with mock.patch.object(ingest, "default_fetchers", return_value=self.f), \
                redirect_stdout(io.StringIO()) as out:
            rc = teddy.main(["ingest", URL, "--run", str(self.run), "--parts", "transcript"])
        self.assertEqual(rc, 0)
        self.assertEqual(set(json.loads(out.getvalue())["videos"][VID]), {"metadata", "transcript"})
        self.assertEqual(self.calls, [])

    def test_cli_unknown_part_refused(self):
        with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
            rc = teddy.main(["ingest", URL, "--run", str(self.run), "--parts", "transcript,audio"])
        self.assertEqual(rc, 2)


class TestDiscardRun(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": self.tmp.name})
        self.env.start()
        self.home = Path(self.tmp.name)
        (self.home / "runs").mkdir()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _run(self, *argv):
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()) as err:
            rc = teddy.main(["discard-run", *argv])
        return rc, out.getvalue(), err.getvalue()

    def test_removes_a_run_folder(self):
        run = self.home / "runs" / f"20261116T000000_{VID}"
        (run / VID).mkdir(parents=True)
        (run / VID / "video.mp4").write_bytes(b"x" * 10)
        rc, out, _ = self._run(str(run))
        self.assertEqual(rc, 0)
        self.assertFalse(run.exists())
        self.assertTrue((self.home / "runs").is_dir())
        self.assertEqual(json.loads(out)["removed"], str(run))

    def test_refuses_anything_outside_runs(self):
        for target in (self.home / "dataset", self.home / "runs", self.home,
                       self.home / "runs" / "x" / "..", Path(self.tmp.name).parent):
            rc, _, err = self._run(str(target))
            self.assertEqual(rc, 2, target)
            self.assertIn("not a run folder", err)
        self.assertTrue((self.home / "dataset").is_dir())

    def test_refuses_a_symlink_out_of_runs(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        link = self.home / "runs" / "20261116T000000_link"
        link.symlink_to(outside.name)
        rc, _, _ = self._run(str(link))
        self.assertEqual(rc, 2)
        self.assertTrue(Path(outside.name).is_dir())


if __name__ == "__main__":
    unittest.main()
