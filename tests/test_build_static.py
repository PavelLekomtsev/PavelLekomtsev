import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_static  # noqa: E402
from hudkit.fonts import load_fonts  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
CYRILLIC = re.compile(r"[\u0400-\u04FF]")
KEYFRAMES = re.compile(r"@keyframes\s*[\w-]+\s*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")
MEDIA = re.compile(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}")


def content():
    return json.loads((ROOT / "scripts" / "content.json").read_text(encoding="utf-8"))


def style_of(svg_text):
    return re.search(r"<style>(.*?)</style>", svg_text, re.S).group(1)


def texts_of(svg_text):
    root = ET.fromstring(svg_text)
    return " ".join("".join(t.itertext()) for t in root.iter(f"{SVG_NS}text"))


def css_font_px(css, cls):
    return float(re.search(r"\." + cls + r"\{font:([\d.]+)px", css).group(1))


class StaticAssetChecks:
    """Checks shared by every generated SVG."""

    def assert_wellformed_no_external_refs(self, svg_text):
        root = ET.fromstring(svg_text)
        self.assertIsNotNone(root.find(f"{SVG_NS}title"))
        for el in root.iter():
            for attr in ("href", XLINK_HREF):
                ref = el.get(attr)
                if ref is not None:
                    self.assertTrue(ref.startswith("#") or ref.startswith("data:"), ref[:60])
        self.assertNotIn("url(http", svg_text)

    def assert_public_copy_rules(self, svg_text):
        self.assertNotIn("\u2014", svg_text)
        self.assertIsNone(CYRILLIC.search(svg_text))
        for banned in ("TensorRT", "LIVE"):
            self.assertNotIn(banned, svg_text)


class BannerTest(unittest.TestCase, StaticAssetChecks):
    @classmethod
    def setUpClass(cls):
        cls.content = content()
        cls.svg = build_static.build_banner(cls.content, ROOT)
        cls.mobile = build_static.build_banner_mobile(cls.content, ROOT)

    def test_banner_wellformed_no_external_refs(self):
        for svg in (self.svg, self.mobile):
            self.assert_wellformed_no_external_refs(svg)

    def test_banner_name_box_contains_name(self):
        root = ET.fromstring(self.svg)
        box = next(el for el in root.iter(f"{SVG_NS}path") if el.get("class") == "box")
        x0, x1 = re.match(r"M([\d.]+) [\d.]+H([\d.]+)", box.get("d")).groups()
        name_w = load_fonts(str(ROOT / "scripts" / "fonts"))["SG7"].width(self.content["name"], 78)
        self.assertGreaterEqual(float(x1) - float(x0), name_w + 40 - 0.1)  # path coordinates are rounded to 0.1 px

    def test_banner_fail_safe_animation(self):
        for svg in (self.svg, self.mobile):
            css = style_of(svg)
            self.assertIn("prefers-reduced-motion", css)
            plain = MEDIA.sub("", KEYFRAMES.sub("", css))
            for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", plain):
                for value in re.findall(r"animation:([^;}]*)", body):
                    if selector.strip() == ".sweep":
                        continue
                    self.assertTrue("both" in value or "infinite" in value, f"{selector}: {value}")
            self.assertNotIn("stroke-dashoffset:100", plain)

    def test_banner_copy(self):
        text = texts_of(self.svg)
        c = self.content
        for s in (c["name"], c["label"], c["subtitle"], c["face_label"], "yaw", "+25.0°", "pitch", "roll"):
            self.assertIn(s, text)
        for svg in (self.svg, self.mobile):
            self.assert_public_copy_rules(svg)

    def test_mobile_banner_min_font_size(self):
        root = ET.fromstring(self.mobile)
        width = float(root.get("width"))
        css = style_of(self.mobile)
        self.assertGreaterEqual(css_font_px(css, "name") * 360 / width, 24)
        self.assertGreaterEqual(css_font_px(css, "sub") * 360 / width, 12)
        self.assertIn(self.content["name"].split()[0], texts_of(self.mobile))


if __name__ == "__main__":
    unittest.main()
