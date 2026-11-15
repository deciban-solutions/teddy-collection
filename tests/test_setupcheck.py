import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "teddy-collection"
sys.path.insert(0, str(PLUGIN / "lib"))
from teddycoll import setupcheck  # noqa: E402


class TestSetupCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": self.tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def by_name(self, entries):
        return {e["name"]: e for e in entries}

    def test_missing_tool_reported(self):
        with mock.patch.dict(os.environ, {"PATH": ""}):
            e = self.by_name(setupcheck.check())["ffmpeg"]
        self.assertFalse(e["ok"])
        self.assertTrue(e["fix"].strip())

    def test_entry_shape_and_requirements(self):
        entries = setupcheck.check()
        names = [e["name"] for e in entries]
        for n in ("python", "yt-dlp", "youtube_transcript_api", "ffmpeg", "data folder"):
            self.assertIn(n, names)
        for e in entries:
            self.assertIsInstance(e["ok"], bool)
            if not e["ok"]:
                self.assertTrue(e["fix"].strip(), e["name"])

    def test_data_folder_created_and_reported(self):
        d = self.by_name(setupcheck.check())["data folder"]
        self.assertTrue(d["ok"])
        self.assertIn(self.tmp.name, d["version"])
        self.assertTrue((Path(self.tmp.name) / "dataset").is_dir())

    def test_python_row_names_the_interpreter(self):
        # F1: the user must know which python3 to pip-install into.
        self.assertIn(sys.executable, self.by_name(setupcheck.check())["python"]["version"])

    def test_old_python_not_ok(self):
        with mock.patch.object(sys, "version_info", (3, 8, 0)):
            self.assertFalse(self.by_name(setupcheck.check())["python"]["ok"])

    def test_subprocess_timeout_is_not_ok(self):
        with mock.patch.object(setupcheck.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired("ffmpeg", 10)), \
             mock.patch.object(setupcheck.shutil, "which", return_value="/x/ffmpeg"):
            self.assertFalse(self.by_name(setupcheck.check())["ffmpeg"]["ok"])

    def test_ytdlp_ok_via_module_only(self):
        fake = mock.Mock(__version__="2099.1.1")
        with mock.patch.dict(os.environ, {"PATH": ""}), mock.patch.dict(sys.modules, {"yt_dlp": fake}):
            e = self.by_name(setupcheck.check())["yt-dlp"]
        self.assertTrue(e["ok"])

    def test_data_folder_not_writable_is_not_ok(self):
        # Final review 10: the check must actually write to the folder.
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root can write anywhere")
        home = Path(self.tmp.name) / "ro"
        for sub in ("dataset", "taxonomies/user", "runs"):
            (home / sub).mkdir(parents=True)
        home.chmod(0o500)
        self.addCleanup(home.chmod, 0o700)
        with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": str(home)}):
            d = self.by_name(setupcheck.check())["data folder"]
        self.assertFalse(d["ok"])
        self.assertIn("TEDDY_COLLECTION_HOME", d["fix"])
        self.assertEqual(sorted(x.name for x in home.iterdir()), ["dataset", "runs", "taxonomies"])

    def test_data_folder_that_cannot_be_created_is_not_ok(self):
        # Final review 10: data_home() swallows a mkdir failure so reads work; the check must not.
        with mock.patch.object(Path, "mkdir", side_effect=OSError(30, "Read-only file system")), \
                mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": self.tmp.name + "/nope"}):
            d = self.by_name(setupcheck.check())["data folder"]
        self.assertFalse(d["ok"])
        self.assertIn("Read-only", d["fix"])

    def test_ytdlp_module_only_is_what_ingest_runs(self):
        # Final review 2: a module-only yt-dlp passes the check, so ingest must run it as
        # `python -m yt_dlp` when no yt-dlp executable is on PATH.
        from teddycoll import ingest
        with mock.patch.object(ingest.shutil, "which", return_value=None):
            self.assertEqual(ingest.ytdlp_argv(), [sys.executable, "-m", "yt_dlp"])
        with mock.patch.object(ingest.shutil, "which", return_value="/opt/bin/yt-dlp"):
            self.assertEqual(ingest.ytdlp_argv(), ["/opt/bin/yt-dlp"])

    def test_cli_exit_code_and_json(self):
        env = dict(os.environ, PATH="")
        r = subprocess.run([sys.executable, "-I", str(PLUGIN / "scripts" / "teddy.py"), "setup-check"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertFalse({e["name"]: e for e in json.loads(r.stdout)}["ffmpeg"]["ok"])


if __name__ == "__main__":
    unittest.main()
