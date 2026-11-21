#!/usr/bin/env python3
"""Build the static profile SVGs into assets/ (run locally, commit the output).

usage: build_static.py [OUT_DIR]   (default: <repo>/assets)
"""
import json
import sys
from pathlib import Path

from hudkit.face import face_svg, load_face
from hudkit.fonts import load_fonts
from hudkit.palette import PAL
from hudkit.svg import esc, rect_path, svg_doc

ROOT = Path(__file__).resolve().parents[1]
TITLE = "Pavel Lekomtsev – Middle Computer Vision Engineer"
DESC = ("Detection-style banner: the name inside a bounding box labelled middle_cv_engineer, "
        "and a 3D face mesh with head-pose axes.")


def _paths(root: Path):
    return root / "scripts" / "fonts", root / "scripts" / "data"


def _banner_css(fonts_sizes: dict, height: int, sweep_h: float) -> str:
    s = fonts_sizes
    return f"""
.hud{{font:15px JB5;fill:{PAL["hud"]}}}
.name{{font:{s["name"]}px SG7;fill:{PAL["text"]}}}
.sub{{font:{s["sub"]}px SG5;fill:{PAL["sub"]}}}
.lbl{{font:{s["tag"]}px JB7;fill:{PAL["ink"]}}}
.lbl2{{font:{s["ftag"]}px JB7;fill:#03140a}}
.pose{{font:{s["pose"]}px JB7;fill:{PAL["sub"]}}}
.box{{stroke-dasharray:100 100;animation:draw 1.3s cubic-bezier(.6,0,.2,1) .25s both}}
.fbox{{stroke-dasharray:100 100;animation:draw 1.3s cubic-bezier(.6,0,.2,1) .7s both}}
.tag{{animation:fade .35s ease 1.45s both}}
.ftag{{animation:fade .35s ease 2.35s both}}
.mesh{{animation:fade .9s ease 1.1s both}}
.ax{{stroke-dasharray:100 100;animation:draw .45s ease-out both}}
.ax0{{stroke-dasharray:none;animation:fade .2s ease 1.9s both}}
.ax1{{animation-delay:1.95s}}.ax2{{animation-delay:2.1s}}.ax3{{animation-delay:2.25s}}
.sweep{{opacity:0;animation:sweep 1.1s ease-in-out 1s 1 forwards}}
.rec{{animation:blink 1.2s step-end infinite}}
.scan{{animation:scan 6s linear infinite}}
@keyframes draw{{from{{stroke-dashoffset:100}}to{{stroke-dashoffset:0}}}}
@keyframes fade{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes blink{{50%{{opacity:0}}}}
@keyframes scan{{from{{transform:translateY(-70px)}}to{{transform:translateY({height + 10}px)}}}}
@keyframes sweep{{0%{{opacity:0;transform:translateY(0)}}15%{{opacity:1}}85%{{opacity:1}}100%{{opacity:0;transform:translateY({sweep_h:.0f}px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}"""


def _backdrop(w: int, h: int) -> str:
    """Gradient, grid, moving scan band, vignette and camera corner brackets."""
    return f"""<!-- Face mesh: MediaPipe canonical face model, Apache License 2.0 -->
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{PAL["bg0"]}"/><stop offset="1" stop-color="{PAL["bg1"]}"/></linearGradient>
<radialGradient id="vig" cx=".5" cy=".5" r=".75"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".55"/></radialGradient>
<pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="{PAL["grid"]}" stroke-width="1"/></pattern>
<linearGradient id="scanG" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{PAL["cyan"]}" stop-opacity="0"/><stop offset="1" stop-color="{PAL["cyan"]}" stop-opacity=".13"/></linearGradient>
<linearGradient id="sweepG" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{PAL["green"]}" stop-opacity="0"/><stop offset=".5" stop-color="{PAL["green"]}" stop-opacity=".9"/><stop offset="1" stop-color="{PAL["green"]}" stop-opacity="0"/></linearGradient>
<filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="2.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
</defs>
<g clip-path="url(#frame)">
<rect width="{w}" height="{h}" fill="url(#bg)"/>
<rect width="{w}" height="{h}" fill="url(#grid)"/>
<rect class="scan" width="{w}" height="70" fill="url(#scanG)"/>
<rect width="{w}" height="{h}" fill="url(#vig)"/>
</g>
<g stroke="{PAL["cyan"]}" stroke-width="2.4" fill="none" opacity=".8" stroke-linecap="square">
<path d="M26 64V26H64"/><path d="M{w - 64} 26H{w - 26}V64"/><path d="M26 {h - 64}V{h - 26}H64"/><path d="M{w - 64} {h - 26}H{w - 26}V{h - 64}"/>
</g>"""


def _name_block(fonts, content, name_x, name_base, sizes) -> tuple:
    """Name inside a closed detection box with its class label; returns (markup, box)."""
    sg7, jb7 = fonts["SG7"], fonts["JB7"]
    name, tag = content["name"], content["label"]
    name_w = sg7.width(name, sizes["name"])
    cap = sg7.cap(sizes["name"])
    pad_x, pad_y = 20, 18
    box = (name_x - pad_x, name_base - cap - pad_y, name_w + 2 * pad_x, cap + 2 * pad_y)
    tag_h = round(sizes["tag"] * 1.6)
    tag_w = jb7.width(tag, sizes["tag"]) + 18
    markup = (f'<text class="name" x="{name_x}" y="{name_base}">{esc(name)}</text>\n'
              f'<path class="box" pathLength="100" d="{rect_path(*box)}" fill="none" stroke="{PAL["cyan"]}" '
              f'stroke-width="2.6" filter="url(#glow)"/>\n'
              f'<g class="tag"><rect x="{box[0] - 1.3:.1f}" y="{box[1] - tag_h:.1f}" width="{tag_w:.1f}" '
              f'height="{tag_h}" fill="{PAL["cyan"]}"/>'
              f'<text class="lbl" x="{box[0] + 8:.1f}" y="{box[1] - tag_h * 0.3:.1f}">{esc(tag)}</text></g>')
    return markup, box


def _face_block(fonts, content, root, cx, cy, height, ftag_size) -> tuple:
    """Face mesh with pose axes inside a detection box with the driver label; returns (markup, face box)."""
    _, data = _paths(root)
    model = load_face(str(data / "face" / "canonical_face_model.obj"), str(data / "face" / "contours.json"))
    pose = content["pose"]
    face, fb = face_svg(model, cx, cy, height, pose["yaw"], pose["pitch"], pose["roll"])
    fpad = 16
    fbox = (fb[0] - fpad, fb[1] - fpad, fb[2] - fb[0] + 2 * fpad, fb[3] - fb[1] + 2 * fpad)
    ftag = content["face_label"]
    ftag_h = round(ftag_size * 1.6)
    ftag_w = fonts["JB7"].width(ftag, ftag_size) + 16
    markup = (f'{face}\n<rect class="sweep" x="{fbox[0]:.1f}" y="{fbox[1]:.1f}" width="{fbox[2]:.1f}" height="2" '
              f'fill="url(#sweepG)"/>\n'
              f'<path class="fbox" pathLength="100" d="{rect_path(*fbox)}" fill="none" stroke="{PAL["green"]}" '
              f'stroke-width="2.4" filter="url(#glow)"/>\n'
              f'<g class="ftag"><rect x="{fbox[0] - 1.2:.1f}" y="{fbox[1] - ftag_h:.1f}" width="{ftag_w:.1f}" '
              f'height="{ftag_h}" fill="{PAL["green"]}"/>'
              f'<text class="lbl2" x="{fbox[0] + 7:.1f}" y="{fbox[1] - ftag_h * 0.3:.1f}">{esc(ftag)}</text></g>')
    return markup, fbox


def _pose_items(content):
    p = content["pose"]
    # yaw turns about the Y axis (green), pitch about X (red), roll about Z (blue)
    return [("yaw", f'{p["yaw"]:+.1f}°', PAL["ax_y"]), ("pitch", f'{p["pitch"]:+.1f}°', PAL["ax_x"]),
            ("roll", f'{p["roll"]:+.1f}°', PAL["ax_z"])]


def build_banner(content: dict, root: Path) -> str:
    fonts_dir, _ = _paths(root)
    fonts = load_fonts(str(fonts_dir))
    w, h = 1200, 360
    sizes = {"name": 78, "sub": 23, "tag": 17, "ftag": 15, "pose": 15}
    name, box = _name_block(fonts, content, 92, 204, sizes)
    face, fbox = _face_block(fonts, content, root, 1014, 198, 160, sizes["ftag"])
    hud = content["hud"]
    pose = "".join(f'<tspan fill="{col}">{k}</tspan> {esc(v)}{" · " if i < 2 else ""}'
                   for i, (k, v, col) in enumerate(_pose_items(content)))
    fonts["JB5"].use(hud["tl"] + hud["tr"] + hud["bl"] + "yaw pitch roll +-.0123456789° · ")
    fonts["SG5"].use(content["subtitle"])
    body = "\n".join([
        _backdrop(w, h),
        f'<circle class="rec" cx="62" cy="59" r="5" fill="{PAL["rec"]}"/>',
        f'<text class="hud" x="76" y="64">{esc(hud["tl"])}</text>',
        f'<text class="hud" x="{w - 62}" y="64" text-anchor="end">{esc(hud["tr"])}</text>',
        f'<text class="hud" x="62" y="{h - 44}">{esc(hud["bl"])}</text>',
        f'<text class="hud" x="{w - 62}" y="{h - 44}" text-anchor="end">{pose}</text>',
        name,
        f'<text class="sub" x="92" y="{204 + 58}">{esc(content["subtitle"])}</text>',
        face,
    ])
    return svg_doc(w, h, body, fonts, TITLE, _banner_css(sizes, h, fbox[3]), DESC)


def build_banner_mobile(content: dict, root: Path) -> str:
    """Narrow-screen header: name, label, two-line subtitle, face and a large pose readout, no small HUD text."""
    fonts_dir, _ = _paths(root)
    fonts = load_fonts(str(fonts_dir))
    w, h = 640, 520
    sizes = {"name": 52, "sub": 22, "tag": 20, "ftag": 16, "pose": 21}
    name, box = _name_block(fonts, content, 52, 160, sizes)
    line1, _, line2 = content["subtitle"].partition(" · ")
    fonts["SG5"].use(line1 + line2)
    face_h, face_top = 130, 322
    _, probe = _face_block(fonts, content, root, 0, 0, face_h, sizes["ftag"])
    cx = 52 - probe[0]
    face, fbox = _face_block(fonts, content, root, cx, face_top + face_h / 2, face_h, sizes["ftag"])
    px = fbox[0] + fbox[2] + 34
    pose = []
    for i, (k, v, col) in enumerate(_pose_items(content)):
        fonts["JB7"].use(k + " " + v)
        pose.append(f'<text class="pose" x="{px:.1f}" y="{face_top + 34 + i * 40}"><tspan fill="{col}">{k}</tspan>'
                    f' {esc(v)}</text>')
    body = "\n".join([
        _backdrop(w, h),
        f'<circle class="rec" cx="62" cy="59" r="6" fill="{PAL["rec"]}"/>',
        name,
        f'<text class="sub" x="52" y="{160 + 62}">{esc(line1)}</text>',
        f'<text class="sub" x="52" y="{160 + 94}">{esc(line2)}</text>',
        face,
        *pose,
    ])
    return svg_doc(w, h, body, fonts, TITLE, _banner_css(sizes, h, fbox[3]), DESC)


def load_content(root: Path = ROOT) -> dict:
    return json.loads((root / "scripts" / "content.json").read_text(encoding="utf-8"))


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    content = load_content()
    outputs = {
        "banner.svg": build_banner(content, ROOT),
        "banner-mobile.svg": build_banner_mobile(content, ROOT),
    }
    for name, svg in outputs.items():
        (out_dir / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets")
