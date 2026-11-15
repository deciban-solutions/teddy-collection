import unittest
from pathlib import Path

import re

# any home directory, a Windows mount, the owner's browser, the owner's other repo
FORBIDDEN = re.compile(r"/home/[a-z]|/mnt/c|msedge|BFIH-Game")
PLUGINS = Path(__file__).resolve().parents[1] / "plugins"


class TestNoOwnerPaths(unittest.TestCase):
    def test_no_owner_paths(self):
        for f in PLUGINS.rglob("*"):
            if not f.is_file() or "__pycache__" in f.parts:
                continue
            text = f.read_bytes().decode("utf-8", "ignore")
            m = FORBIDDEN.search(text)
            self.assertIsNone(m, f"{m and m.group(0)} in {f}")


if __name__ == "__main__":
    unittest.main()
