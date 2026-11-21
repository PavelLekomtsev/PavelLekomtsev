import math
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from hudkit.face import face_svg, head_rotation, load_face  # noqa: E402
from hudkit.fonts import load_fonts  # noqa: E402
from hudkit.palette import luminance, on_dark  # noqa: E402
from hudkit.svg import wrap  # noqa: E402

FONTS = ROOT / "scripts" / "fonts"
FACE = ROOT / "scripts" / "data" / "face"


class HeadRotationTest(unittest.TestCase):
    def test_head_rotation_matches_draw_axis(self):
        # reference: draw_axis() in 6DRepNet / Hopenet (yaw is negated first)
        yaw, pitch, roll = 25.0, 6.0, 4.0
        y, p, r = -math.radians(yaw), math.radians(pitch), math.radians(roll)
        want = [
            (math.cos(y) * math.cos(r), math.cos(p) * math.sin(r) + math.cos(r) * math.sin(p) * math.sin(y)),
            (-math.cos(y) * math.sin(r), math.cos(p) * math.cos(r) - math.sin(p) * math.sin(y) * math.sin(r)),
            (math.sin(y), -math.cos(y) * math.sin(p)),
        ]
        rot = head_rotation(yaw, pitch, roll)
        for col, (wx, wy) in enumerate(want):
            self.assertAlmostEqual(rot[0][col], wx, places=9)
            self.assertAlmostEqual(rot[1][col], wy, places=9)

    def test_axis_directions(self):
        rot = head_rotation(0.0, 0.0, 0.0)
        self.assertEqual((round(rot[0][0], 9), round(rot[1][0], 9)), (1.0, 0.0))  # X points right
        self.assertEqual((round(rot[0][1], 9), round(rot[1][1], 9)), (0.0, 1.0))  # Y points down
        self.assertAlmostEqual(math.hypot(rot[0][2], rot[1][2]), 0.0, places=9)  # Z points out of the screen


class FontTest(unittest.TestCase):
    def test_font_width_and_css(self):
        fonts = load_fonts(str(FONTS))
        self.assertLess(abs(fonts["SG7"].width("Pavel Lekomtsev", 78) - 630.3), 1.0)
        fonts["JB5"].use("abc")
        css = fonts["JB5"].css()
        self.assertIn("@font-face", css)
        self.assertIn("base64,", css)


class PaletteTest(unittest.TestCase):
    def test_on_dark(self):
        self.assertEqual(on_dark("3776AB"), "#3776AB")
        self.assertGreaterEqual(luminance(on_dark("0E1128")[1:]), 0.06)


class WrapTest(unittest.TestCase):
    def test_wrap(self):
        font = load_fonts(str(FONTS))["SG5"]
        text = ("Smart parking for Nizhny Novgorod: a UE5 digital twin with six cameras, "
                "YOLOv8 + SORT and a plate-recognition barrier.")
        lines = wrap(font, text, 14.5, 386)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(font.width(line, 14.5), 386)
        self.assertEqual(" ".join(lines), text)


class FaceTest(unittest.TestCase):
    def test_face_svg_bbox_and_wellformed(self):
        model = load_face(str(FACE / "canonical_face_model.obj"), str(FACE / "contours.json"))
        markup, (x0, y0, x1, y1) = face_svg(model, 500, 200, 160, 25.0, 6.0, 4.0)
        ET.fromstring(f'<svg xmlns="http://www.w3.org/2000/svg">{markup}</svg>')
        self.assertAlmostEqual(y1 - y0, 160, delta=1)
        self.assertLess(x0, 500)
        self.assertGreater(x1, 500)


if __name__ == "__main__":
    unittest.main()
