import os, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import paths  # noqa: E402


class TestPaths(unittest.TestCase):
    def test_data_home_env_override(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": d}):
                home = paths.data_home()
                self.assertEqual(home, Path(d))
                for sub in ("dataset", "taxonomies/user", "runs"):
                    self.assertTrue((home / sub).is_dir(), sub)

    def test_read_only_home_still_resolves(self):
        # G14: reading the data home never fails because its folders cannot be created.
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": d + "/ro"}), \
                    mock.patch.object(Path, "mkdir", side_effect=OSError(30, "Read-only file system")):
                self.assertEqual(paths.data_home(), Path(d) / "ro")

    def test_new_run_is_unique(self):
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.dict(os.environ, {"TEDDY_COLLECTION_HOME": d}):
                a = paths.new_run(["abc123"])
                time.sleep(1.1)
                b = paths.new_run(["abc123"])
                self.assertNotEqual(a, b)
                self.assertTrue(a.is_dir() and b.is_dir())
                self.assertTrue(a.name.endswith("_abc123"))
                self.assertEqual(a.parent, Path(d) / "runs")


if __name__ == "__main__":
    unittest.main()
