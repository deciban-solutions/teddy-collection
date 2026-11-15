import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "scripts"))
from teddycoll import ingest  # noqa: E402

VID = "abcDEF12345"
URL = f"https://www.youtube.com/watch?v={VID}"


class TranscriptsDisabled(Exception):
    pass


def good(channel="Teddy Baldassarre"):
    meta = {"title": "T", "upload_date": "20261101", "duration": 600, "views": 5,
            "description": "d", "channel": channel}
    return {
        "transcript": lambda vid: [SimpleNamespace(start=75.2, text="a\nb")],
        "metadata": lambda vid, run: dict(meta),
        "comments": lambda vid, run: [{"text": "nice"}],
        "video": lambda vid, run: None,
    }


class TestIngest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_blocked_video_still_ingests(self):
        f = good()
        def boom(vid, run):
            raise RuntimeError("blocked in your country")
        f["video"] = boom
        st = ingest.run_ingest(URL, self.run, fetchers=f)
        self.assertEqual(st["video"]["status"], "unavailable")
        self.assertIn("blocked", st["video"]["reason"])
        for k in ("transcript", "metadata", "comments"):
            self.assertEqual(st[k]["status"], "ok", k)
        d = self.run / VID
        self.assertTrue((d / "transcript.txt").exists())
        self.assertEqual(json.loads((d / "comments.json").read_text()), [{"text": "nice"}])
        self.assertNotIn("comments", json.loads((d / "metadata.json").read_text()))

    def test_no_captions(self):
        f = good()
        def off(vid):
            raise TranscriptsDisabled("disabled")
        f["transcript"] = off
        st = ingest.run_ingest(URL, self.run, fetchers=f)
        self.assertEqual(st["transcript"]["status"], "unavailable")
        self.assertEqual(st["metadata"]["status"], "ok")

    def test_no_captions_exit_code_zero(self):
        import teddy
        f = good()
        f["transcript"] = lambda vid: (_ for _ in ()).throw(TranscriptsDisabled("x"))
        with mock.patch.object(ingest, "default_fetchers", return_value=f), \
                redirect_stdout(io.StringIO()):
            rc = teddy.main(["ingest", URL, "--run", str(self.run)])
        self.assertEqual(rc, 0)

    def test_wrong_channel_refused(self):
        with self.assertRaises(ValueError):
            ingest.run_ingest(URL, self.run, fetchers=good("Other"))

    def test_any_channel_allowed(self):
        st = ingest.run_ingest(URL, self.run, fetchers=good("Other"), any_channel=True)
        self.assertEqual(st["metadata"]["status"], "ok")

    def test_channel_id_accepted(self):
        f = good("Other")
        f["metadata"] = lambda vid, run: {"channel": "Other",
                                          "channel_id": "UCLGp7H4XuzA9TLJ0L4PUx8w"}
        st = ingest.run_ingest(URL, self.run, fetchers=f)
        self.assertEqual(st["metadata"]["status"], "ok")

    def _no_meta(self):
        f = good()
        def boom(vid, run):
            raise RuntimeError("network down")
        f["metadata"] = boom
        return f

    def test_metadata_unavailable_stops(self):
        import teddy
        with self.assertRaises(ingest.MetadataUnavailable) as cm:
            ingest.run_ingest(URL, self.run, fetchers=self._no_meta())
        self.assertIn("cannot verify channel, title or upload date: metadata unavailable (", str(cm.exception))
        with mock.patch.object(ingest, "default_fetchers", return_value=self._no_meta()), \
                redirect_stdout(io.StringIO()), mock.patch("sys.stderr", io.StringIO()):
            rc = teddy.main(["ingest", URL, "--run", str(self.run)])
        self.assertEqual(rc, 2)

    def test_metadata_unavailable_any_channel_proceeds(self):
        st = ingest.run_ingest(URL, self.run, fetchers=self._no_meta(), any_channel=True)
        self.assertEqual(st["metadata"]["status"], "unavailable")
        self.assertEqual(st["transcript"]["status"], "ok")

    def test_comments_failure_is_independent(self):
        f = good()
        def boom(vid, run):
            raise RuntimeError("comments off")
        f["comments"] = boom
        st = ingest.run_ingest(URL, self.run, fetchers=f)
        self.assertEqual(st["comments"]["status"], "unavailable")
        self.assertEqual(st["metadata"]["status"], "ok")
        self.assertTrue((self.run / VID / "metadata.json").exists())

    def _cli(self, argv, fetchers=None):
        import teddy
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ingest, "default_fetchers", return_value=fetchers or good()), \
                mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": self.tmp.name}), \
                redirect_stdout(out), mock.patch("sys.stderr", err):
            rc = teddy.main(argv)
        return rc, err.getvalue()

    def test_cli_wrong_channel_clean_error(self):
        rc, err = self._cli(["ingest", URL, "--run", str(self.run)], good("Other"))
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("error: "))
        self.assertNotIn("Traceback", err)

    def test_cli_bad_url_clean_error(self):
        rc, err = self._cli(["ingest", "https://example.com/x"])
        self.assertEqual(rc, 2)
        self.assertTrue(err.startswith("error: "))
        self.assertNotIn("Traceback", err)

    def test_transcript_format(self):
        st = ingest.run_ingest(URL, self.run, fetchers=good())
        self.assertEqual(st["transcript"]["status"], "ok")
        text = (self.run / VID / "transcript.txt").read_text()
        self.assertEqual(text.splitlines(), ["01:15 a b"])

    def test_video_id_extraction(self):
        for u in (URL, f"https://youtu.be/{VID}?t=3", f"https://www.youtube.com/shorts/{VID}"):
            self.assertEqual(ingest.video_id(u), VID)

    def test_bad_id_raises_before_new_run(self):
        import teddy
        bad = ["https://www.youtube.com/watch?v=short", "https://example.com/x",
               "https://youtu.be/abc$EF12345"]
        for u in bad:
            with self.assertRaises(ValueError, msg=u):
                ingest.video_id(u)
        with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": self.tmp.name}), \
                mock.patch("teddycoll.paths.new_run") as nr:
            with mock.patch("sys.stderr", io.StringIO()):
                self.assertEqual(teddy.main(["ingest", URL, bad[0]]), 2)
            nr.assert_not_called()


class TestYtdlpFallback(unittest.TestCase):
    """Final review 2: ingest runs the yt-dlp executable, or `python -m yt_dlp` without one."""

    def _calls(self, which):
        seen = []

        def fake_run(argv, **kw):
            seen.append(argv)
            out = Path(argv[argv.index("-o") + 1])
            if "--skip-download" in argv:
                out.with_name("info.info.json").write_text('{"title": "T", "comments": []}')
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(ingest.shutil, "which", return_value=which), \
                mock.patch.object(ingest.subprocess, "run", side_effect=fake_run):
            ingest._fetch_metadata(VID, Path(d))
            ingest._fetch_comments(VID, Path(d))
            ingest._fetch_video(VID, Path(d))
        return seen

    def test_binary_on_path(self):
        for argv in self._calls("/usr/local/bin/yt-dlp"):
            self.assertEqual(argv[0], "/usr/local/bin/yt-dlp")

    def test_module_when_no_binary(self):
        calls = self._calls(None)
        self.assertEqual(len(calls), 3)
        for argv in calls:
            self.assertEqual(argv[:3], [sys.executable, "-m", "yt_dlp"])


if __name__ == "__main__":
    unittest.main()
