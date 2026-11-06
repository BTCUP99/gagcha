"""Exercise pack_gif end to end. Fixtures live in a temporary folder."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw


class PackGifTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.frames = Path(tmp.name) / "源帧"
        self.frames.mkdir()
        self.output = Path(tmp.name) / "成品.gif"
        self.script = Path(__file__).resolve().parents[1] / "skills" / "gagcha" / "scripts" / "pack_gif.py"

    def call(self, *options):
        return subprocess.run([sys.executable, self.script, self.frames, self.output, *options],
                              capture_output=True, text=True)

    def frame(self, number, x=None, size=(32, 32)):
        im = Image.new("RGBA", size)
        if x is not None:
            ImageDraw.Draw(im).rectangle((x, 5, x + 3, 8), fill=(0, 0, 0, 255))
        im.save(self.frames / f"f{number}.png")

    def test_transparency_natural_order_and_pauses(self):
        # A visible black shape must survive a palette that also needs transparency.
        self.frame(11, 12)
        self.frame(10)
        self.frame(3, 2)
        self.frame(2, 2)
        r = self.call("--delay-ms", "80,100,160,200")
        self.assertEqual(r.returncode, 0, r.stderr)
        with Image.open(self.output) as gif:
            self.assertEqual((gif.n_frames, gif.info["loop"]), (3, 0))
            for i, (pos, delay) in enumerate([((2, 5, 6, 9), 180), (None, 160),
                                               ((12, 5, 16, 9), 200)]):
                gif.seek(i)
                rgba = gif.convert("RGBA")
                self.assertEqual(gif.info["duration"], delay)
                self.assertEqual(rgba.getchannel("A").getbbox(), pos)
                if pos:
                    self.assertEqual(rgba.getpixel(pos[:2]), (0, 0, 0, 255))

    def test_failure_preserves_existing_output(self):
        self.frame(1, 2)
        self.frame(2, 7)
        self.assertEqual(self.call().returncode, 0)
        original = self.output.read_bytes()
        self.assertNotEqual(self.call().returncode, 0)
        self.assertNotEqual(self.call("--force", "--max-bytes", "10").returncode, 0)
        self.frame(3, 10, size=(40, 32))
        self.assertNotEqual(self.call("--force").returncode, 0)
        self.assertEqual(self.output.read_bytes(), original)

    def test_fractional_fps_rgb_matte_and_resize(self):
        for n in range(12):
            self.frame(n, n)
        r = self.call("--fps", "12", "--matte", "#FFFFFF", "--size", "16x16")
        self.assertEqual(r.returncode, 0, r.stderr)
        with Image.open(self.output) as gif:
            duration = 0
            for i in range(gif.n_frames):
                gif.seek(i)
                duration += gif.info["duration"]
                r, g, b, a = gif.convert("RGBA").getpixel((15, 15))
                self.assertGreaterEqual(min(r, g, b), 250)
                self.assertEqual(a, 255)
            self.assertEqual((gif.size, duration), ((16, 16), 1000))

    def test_append_uses_shot_order_even_with_identical_filenames(self):
        self.frame(1, 1)
        self.frame(2, 2)
        second = self.frames.parent / "侧面"
        third = self.frames.parent / "远景"
        for folder, positions in [(second, [5, 6]), (third, [12, 13])]:
            folder.mkdir()
            for index, x in enumerate(positions, 1):
                frame = Image.new("RGBA", (32, 32))
                ImageDraw.Draw(frame).rectangle((x, 5, x + 3, 8), fill=(0, 0, 0, 255))
                frame.save(folder / f"f{index}.png")
        r = self.call("--append", second, "--append", third, "--delay-ms", "80,100,120,140,160,180")
        self.assertEqual(r.returncode, 0, r.stderr)
        with Image.open(self.output) as gif:
            self.assertEqual(gif.n_frames, 6)
            for i, x in enumerate((1, 2, 5, 6, 12, 13)):
                gif.seek(i)
                self.assertEqual(gif.info["duration"], 80 + i * 20)
                self.assertEqual(gif.convert("RGBA").getchannel("A").getbbox(), (x, 5, x + 4, 9))
        before = self.output.read_bytes()
        self.assertNotEqual(self.call("--force", "--append", third / "missing").returncode, 0)
        empty = self.frames.parent / "empty"
        empty.mkdir()
        self.assertNotEqual(self.call("--force", "--append", empty).returncode, 0)
        self.assertEqual(self.output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
