import shutil, subprocess, sys, tempfile, unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "teddy-collection" / "lib"))
from teddycoll import frames  # noqa: E402

FFMPEG = shutil.which("ffmpeg")


def _dims(path):
    out = subprocess.run(["ffmpeg", "-i", str(path)], capture_output=True, text=True).stderr
    import re
    m = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5})", out)
    return int(m.group(1)), int(m.group(2))


def _coded_time(img, x, y):
    """Mean luma of a 60x60 patch at (x, y) of a JPEG, decoded back to video seconds.

    The video's limited-range luma 16 + 3N becomes full-range 3N * 255/219 in a JPEG;
    N is the frame number at 2 fps."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(img), "-vf",
                          f"crop=60:60:{x}:{y},format=gray", "-f", "rawvideo", "-"],
                         capture_output=True).stdout
    return (sum(raw) / len(raw)) * 219 / 255 / 3 / 2


class TestLabel(unittest.TestCase):
    def test_label_rounding(self):
        # Review minor 4: 0.999 must not become "0:001".
        self.assertEqual(frames._label(0.999), "0:01")
        self.assertEqual(frames._label(59.996), "1:00")
        self.assertEqual(frames._label(10.25), "0:10.25")
        self.assertEqual(frames._label(10.5), "0:10.5")
        self.assertEqual(frames._label(3725.5), "1:02:05.5")
        self.assertEqual(frames._label(65), "1:05")


@unittest.skipUnless(FFMPEG, "ffmpeg not installed")
class TestFrames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.video = cls.tmp / "t.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "testsrc=duration=5:size=1920x1080:rate=10",
                        "-pix_fmt", "yuv420p", str(cls.video)], check=True)
        # Luminance encodes time: frame N (2 fps) has luma 16 + 3N (see _coded_time).
        cls.coded = cls.tmp / "coded.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=black:s=320x240:r=2:d=40,geq=lum='16+3*N':cb=128:cr=128",
                        "-pix_fmt", "yuv420p", str(cls.coded)], check=True)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_sheet_count(self):
        sheets = frames.contact_sheet(self.video, "0", "5", 1, self.tmp / "sheet")
        self.assertEqual(len(sheets), 1)
        self.assertTrue(sheets[0].exists())
        self.assertEqual(sheets[0].name, "sheet_01.jpg")

    def test_sheet_tile_shows_the_frame_its_label_names(self):
        # G1: each tile's label is start + k*every, so the tile must show the frame
        # `frames still --at <label>` gives, not one from later in the interval.
        sheets = frames.contact_sheet(self.coded, "10", "34", 3, self.tmp / "drift")
        self.assertEqual(len(sheets), 1)
        for k in range(8):
            label = 10 + 3 * k
            col, row = k % 4, k // 4
            tile_t = _coded_time(sheets[0], col * 480 + 200, row * 360 + 200)
            self.assertAlmostEqual(tile_t, label, delta=0.3, msg=f"tile {k} labelled {label}")
            st = frames.still(self.coded, str(label), self.tmp / f"st{k}.jpg")
            self.assertAlmostEqual(_coded_time(st, 130, 100), label, delta=0.3)

    def test_still_and_crop(self):
        s = frames.still(self.video, "2", self.tmp / "s.jpg")
        self.assertEqual(_dims(s), (1920, 1080))
        c = frames.crop(s, (10, 20, 300, 200), self.tmp / "c.jpg")
        self.assertEqual(_dims(c), (300, 200))

    def test_crop_in_place(self):
        # Final review 1: SKILL.md Step 5.2 crops an image onto itself (--out <img>). ffmpeg
        # refuses "Output same as Input" for png/webp inputs (a .jpg slips past its guard).
        for ext in ("png", "webp", "jpg"):
            img = self.tmp / f"inplace.{ext}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                            "testsrc=duration=1:size=640x480:rate=1", "-frames:v", "1",
                            str(img)], check=True)
            out = frames.crop(img, (10, 20, 300, 200), img)
            self.assertEqual(out, img)
            self.assertEqual(_dims(img), (300, 200), ext)
        self.assertEqual(sorted(p.name for p in self.tmp.glob("tmp*")), [])

    def test_still_never_overwrites_its_video(self):
        # Final review 1: `still` reads a video, so writing "in place" would destroy the
        # input; it must refuse, not write through a temp file.
        with self.assertRaises((ValueError, frames.FfmpegError)):
            frames.still(self.video, "1", self.video)
        self.assertGreater(self.video.stat().st_size, 1000)

    def test_resize_long_edge(self):
        s = frames.still(self.video, "1", self.tmp / "r.jpg")
        frames.resize(s)
        self.assertEqual(_dims(s), (900, 506))

    def test_resize_never_upscales(self):
        s = frames.still(self.video, "1", self.tmp / "u.jpg")
        frames.resize(s, long_edge=4000)
        self.assertEqual(_dims(s), (1920, 1080))

    def test_resize_png_returns_jpg(self):
        png = self.tmp / "p.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        "testsrc=duration=1:size=1920x1080:rate=1", "-frames:v", "1",
                        str(png)], check=True)
        out = frames.resize(png)
        self.assertEqual(out, self.tmp / "p.jpg")
        self.assertEqual(out.read_bytes()[:2], b"\xff\xd8")
        self.assertTrue(png.exists())
        self.assertEqual(png.read_bytes()[:4], b"\x89PNG")
        self.assertEqual(_dims(out), (900, 506))


class TestSheetNumbering(unittest.TestCase):
    """Final review 9: sheet 100 and later must be returned and cleaned up."""

    def test_more_than_99_sheets(self):
        def fake_run(args):
            Path(args[-1]).write_bytes(b"x")
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "sh_150.jpg").write_bytes(b"old")      # a stale sheet from an earlier, longer run
            (d / "sh_x.jpg").write_bytes(b"keep")       # not a sheet
            with unittest.mock.patch.object(frames, "_run", side_effect=fake_run):
                got = frames.contact_sheet(d / "v.mp4", "0", "1212", 1, d / "sh")
            self.assertEqual(len(got), 101)
            self.assertEqual(got[0].name, "sh_01.jpg")
            self.assertEqual(got[99].name, "sh_100.jpg")
            self.assertEqual(got[100].name, "sh_101.jpg")
            self.assertFalse((d / "sh_150.jpg").exists())
            self.assertTrue((d / "sh_x.jpg").exists())


if __name__ == "__main__":
    unittest.main()
