import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
WORKFLOW = ROOT / ".github" / "workflows" / "profile-assets.yml"
OUTPUT = "https://raw.githubusercontent.com/PavelLekomtsev/PavelLekomtsev/output/"


def readme():
    return README.read_text(encoding="utf-8")


class ReadmeTest(unittest.TestCase):
    def test_readme_assets_exist(self):
        paths = re.findall(r'(?:src|srcset)="(assets/[^"]+)"', readme())
        self.assertGreaterEqual(len(paths), 8)
        for rel in paths:
            self.assertTrue((ROOT / rel).is_file(), rel)

    def test_readme_has_no_long_dash_or_cyrillic(self):
        text = readme()
        self.assertNotIn("\u2014", text)
        self.assertIsNone(re.search(r"[\u0400-\u04FF]", text))
        for banned in ("TensorRT", "live demo", "LIVE DEMO"):
            self.assertNotIn(banned, text)

    def test_every_img_has_alt(self):
        imgs = re.findall(r"<img\b[^>]*>", readme())
        self.assertGreaterEqual(len(imgs), 15)
        for tag in imgs:
            self.assertRegex(tag, r'alt="[^"]+"', tag[:80])

    def test_badges_and_contacts(self):
        text = readme()
        labels = re.findall(r"img\.shields\.io/badge/([^-]+(?:--[^-]+)*)-", text)
        for want in ("Intelli--Vision", "VkusVill%20%C3%97%20ITMO", "ITMO", "HSE"):
            self.assertIn(want, labels)
        for link in ("https://t.me/ashaprokky", "mailto:polekomtsev@edu.hse.ru", "https://huggingface.co/PavelLekomtsev"):
            self.assertIn(f'href="{link}"', text)

    def test_featured_links(self):
        text = readme()
        projects = json.loads((ROOT / "scripts" / "content.json").read_text(encoding="utf-8"))["projects"]
        lines = text.splitlines()
        for i in range(0, len(projects), 2):  # cards come in pairs, both on one line so they sit side by side
            a, b = projects[i], projects[i + 1]
            pair = [ln for ln in lines if f'href="{a["url"]}"' in ln]
            self.assertEqual(len(pair), 1, a["url"])
            self.assertIn(f'href="{b["url"]}"', pair[0])
            self.assertIn(f'src="assets/card-{a["slug"]}.svg"', pair[0])
            self.assertIn(f'src="assets/card-{b["slug"]}.svg"', pair[0])
        stats_line = [ln for ln in lines if f"{OUTPUT}activity.svg" in ln]
        self.assertEqual(len(stats_line), 1)
        self.assertIn(f"{OUTPUT}languages.svg", stats_line[0])

    def test_picture_mobile_source(self):
        text = readme()
        self.assertIn('<source media="(max-width: 600px)" srcset="assets/banner-mobile.svg">', text)
        self.assertIn(f'<source media="(prefers-color-scheme: dark)" srcset="{OUTPUT}snake-dark.svg">', text)
        self.assertIn(f'src="{OUTPUT}snake-light.svg"', text)



class LicenceTest(unittest.TestCase):
    def test_vendored_licences_present(self):
        face_licence = ROOT / "scripts" / "data" / "face" / "LICENSE"
        self.assertTrue(face_licence.is_file())
        text = face_licence.read_text(encoding="utf-8")
        self.assertIn("Apache License", text)
        self.assertIn("Version 2.0", text)
        for font in ("OFL-SpaceGrotesk.txt", "OFL-JetBrainsMono.txt"):
            self.assertIn("SIL OPEN FONT LICENSE", (ROOT / "scripts" / "fonts" / font).read_text(encoding="utf-8"))
        notice = (ROOT / "NOTICE.md").read_text(encoding="utf-8")
        self.assertIn("scripts/data/face/LICENSE", notice)
        self.assertIn("contours.json", notice)

class WorkflowTest(unittest.TestCase):
    def test_workflow_versions(self):
        wf = WORKFLOW.read_text(encoding="utf-8")
        for pin in ("actions/checkout@v7", "actions/setup-python@v7", "Platane/snk@v3.5.0"):
            self.assertIn(pin, wf)
        self.assertRegex(wf, r"permissions:\s*\n\s+contents: write")
        # a failed stats build must stop the job before anything is published
        self.assertLess(wf.index("build_stats.py --out dist"), wf.index("git push --force"))
        self.assertLess(wf.index("unittest discover"), wf.index("build_stats.py --out dist"))


if __name__ == "__main__":
    unittest.main()
