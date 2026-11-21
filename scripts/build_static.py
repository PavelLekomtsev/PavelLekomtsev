#!/usr/bin/env python3
"""Build the static profile SVGs into assets/ (run locally, commit the output).

usage: build_static.py [OUT_DIR]   (default: <repo>/assets)
"""
import base64
import json
import re
import sys
from pathlib import Path

from hudkit.face import face_svg, load_face
from hudkit.fonts import load_fonts
from hudkit.palette import PAL, on_dark
from hudkit.svg import corners, esc, rect_path, svg_doc, wrap

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
    w, h = 640, 550
    # sized for a ~278 px README column on a 360 px phone: name >= 24 px, subtitle >= 12 px there
    sizes = {"name": 56, "sub": 28, "tag": 22, "ftag": 18, "pose": 24}
    name_x, name_base = 48, 170
    name, box = _name_block(fonts, content, name_x, name_base, sizes)
    line1, _, line2 = content["subtitle"].partition(" · ")
    fonts["SG5"].use(line1 + line2)
    face_h, face_top = 140, 345
    _, probe = _face_block(fonts, content, root, 0, 0, face_h, sizes["ftag"])
    cx = 52 - probe[0]
    face, fbox = _face_block(fonts, content, root, cx, face_top + face_h / 2, face_h, sizes["ftag"])
    px = fbox[0] + fbox[2] + 34
    pose = []
    for i, (k, v, col) in enumerate(_pose_items(content)):
        fonts["JB7"].use(k + " " + v)
        pose.append(f'<text class="pose" x="{px:.1f}" y="{face_top + 40 + i * 44}"><tspan fill="{col}">{k}</tspan>'
                    f' {esc(v)}</text>')
    body = "\n".join([
        _backdrop(w, h),
        f'<circle class="rec" cx="62" cy="59" r="6" fill="{PAL["rec"]}"/>',
        name,
        f'<text class="sub" x="{name_x}" y="{name_base + 70}">{esc(line1)}</text>',
        f'<text class="sub" x="{name_x}" y="{name_base + 106}">{esc(line2)}</text>',
        face,
        *pose,
    ])
    return svg_doc(w, h, body, fonts, TITLE, _banner_css(sizes, h, fbox[3]), DESC)


def build_typing(content: dict, root: Path) -> str:
    """Typing-and-deleting line cycling through content["typing"], drawn with SMIL (no scripts)."""
    fonts_dir, _ = _paths(root)
    fonts = load_fonts(str(fonts_dir))
    lines = content["typing"]
    w, h, size, y = 880, 56, 22, 36
    prompt = "> "
    cw = fonts["JB7"].width("M", size)
    fonts["JB7"].use(prompt + "".join(lines))
    t_char, t_del, hold, gap = 0.065, 0.025, 1.9, 0.35
    parts, carets = [], []
    n = len(lines)
    for i, line in enumerate(lines):
        k = len(prompt + line)
        x0 = (w - cw * k) / 2
        type_t = [j * t_char for j in range(k + 1)]
        t_hold = type_t[-1] + hold
        del_t = [t_hold + j * t_del for j in range(1, k + 1)]
        dur = del_t[-1] + gap
        times = type_t + [t_hold] + del_t + [dur]
        lens = list(range(k + 1)) + [k] + [k - j for j in range(1, k + 1)] + [0]
        # the path grows one glyph per step; glyphs past the end of a textPath are not rendered
        # https://www.w3.org/TR/SVG11/text.html#TextLayoutOnAPath
        vals = ";".join(f"M{x0:.1f} {y} h{max(0.01, n_ * cw):.1f}" for n_ in lens)
        keys = ";".join(f"{t / dur:.4f}" for t in times)
        begin = f"0s;a{n - 1}.end" if i == 0 else f"a{i - 1}.end"
        # without SMIL the first line stays fully typed; every run freezes at length 0, so no line lingers
        base = f"h{k * cw:.1f}" if i == 0 else "h0.01"
        if i == 0:
            still_x, caret_x = x0, x0 + k * cw + 1
        parts.append(
            f'<path id="p{i}" d="M{x0:.1f} {y} {base}"><animate id="a{i}" attributeName="d" begin="{begin}" '
            f'dur="{dur:.3f}s" calcMode="discrete" fill="freeze" values="{vals}" keyTimes="{keys}"/></path>\n'
            f'<text class="t"><textPath xlink:href="#p{i}"><tspan class="pr">{esc(prompt)}</tspan>{esc(line)}'
            f'</textPath></text>')
        cvals = ";".join(f"{x0 + n_ * cw + 1:.1f}" for n_ in lens)
        carets.append(f'<animate attributeName="x" begin="a{i}.begin" dur="{dur:.3f}s" calcMode="discrete" '
                      f'fill="freeze" values="{cvals}" keyTimes="{keys}"/>')
    caret = f'<rect class="cr" x="{caret_x:.1f}" y="16" width="11" height="26" rx="1">{"".join(carets)}</rect>'
    # SMIL ignores prefers-reduced-motion, so the static line is swapped in with CSS
    still = (f'<text class="still" x="{still_x:.1f}" y="{y}"><tspan class="pr">{esc(prompt)}</tspan>'
             f'{esc(lines[0])}</text>')
    css = (f".t,.still{{font:{size}px JB7;fill:{PAL['cyan']}}}.pr{{fill:{PAL['green']}}}.still{{display:none}}"
           f".cr{{fill:{PAL['cyan']};opacity:.85;animation:bl 1s step-end infinite}}@keyframes bl{{50%{{opacity:0}}}}"
           f"@media (prefers-reduced-motion:reduce){{.t,.cr{{display:none}}.still{{display:inline}}}}")
    return svg_doc(w, h, "\n".join(parts) + "\n" + caret + "\n" + still, fonts, lines[0], css)


def _icon_path(root: Path, slug: str) -> str:
    _, data = _paths(root)
    svg = (data / "icons" / f"{slug}.svg").read_text(encoding="utf-8")
    return re.search(r'<path d="([^"]+)"', svg).group(1)


def build_stack(content: dict, root: Path) -> str:
    """Tech-stack panel: one row per category, each technology as an icon + name chip."""
    fonts_dir, _ = _paths(root)
    fonts = load_fonts(str(fonts_dir))
    w = 920
    label_w, row_h, chip_h, gap, top, max_x = 172, 46, 32, 8, 60, w - 36
    rows, y = [], top
    for cat in content["stack"]:
        rows.append(f'<text class="lb" x="40" y="{y + 21}">{esc(fonts["JB7"].use(cat["label"]))}</text>')
        x = 40 + label_w
        for item in cat["items"]:
            cw = 12 + 18 + 8 + fonts["SG5"].width(item["name"], 14) + 12
            if x + cw > max_x:
                x, y = 40 + label_w, y + row_h
            rows.append(f'<rect x="{x:.1f}" y="{y}" width="{cw:.1f}" height="{chip_h}" rx="7" class="chip"/>')
            if item["slug"]:
                rows.append(f'<g transform="translate({x + 12:.1f} {y + 7}) scale(.75)" fill="{on_dark(item["hex"])}">'
                            f'<path d="{_icon_path(root, item["slug"])}"/></g>')
            else:  # no official icon: a small bounding-box glyph instead
                rows.append(f'<rect x="{x + 12:.1f}" y="{y + 7}" width="18" height="18" rx="3" fill="none" '
                            f'stroke="{PAL["cyan"]}" stroke-width="1.6"/><rect x="{x + 16:.1f}" y="{y + 11}" '
                            f'width="10" height="10" fill="{PAL["cyan"]}" opacity=".35"/>')
            rows.append(f'<text class="nm" x="{x + 38:.1f}" y="{y + 21}">{esc(item["name"])}</text>')
            x += cw + gap
        y += row_h
    h = y + 22
    note = "python-first · edge-ready"
    head = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{PAL["panel"]}" stroke="{PAL["line"]}"/>'
            + corners(12, 12, w - 24, h - 24, n=16)
            + f'<text class="hd" x="40" y="40">{esc(fonts["JB7"].use("TECH STACK"))}</text>'
            + f'<text class="hd2" x="{w - 40}" y="40" text-anchor="end">{esc(fonts["JB5"].use(note))}</text>')
    css = (f".lb{{font:12.5px JB7;fill:{PAL['muted']};letter-spacing:1.5px}}"
           f".nm{{font:14px SG5;fill:{PAL['text']}}}.chip{{fill:{PAL['panel2']};stroke:{PAL['line']}}}"
           f".hd{{font:14px JB7;fill:{PAL['cyan']};letter-spacing:2px}}.hd2{{font:12.5px JB5;fill:{PAL['hud']}}}")
    return svg_doc(w, h, head + "\n".join(rows), fonts, "Tech stack", css)


def _praxis_art(fonts, w: int, h: int) -> str:
    """Stand-in preview for Praxis (no screenshots in the repo): keyframes over a segmented action timeline."""
    segs = [(0.16, "#22d3ee", "pick up"), (0.22, "#3fb950", "rotate"), (0.12, "#a371f7", "inspect"),
            (0.2, "#f0883e", "put down"), (0.1, "#db61a2", "push"), (0.2, "#4493f8", "release")]
    out = [f'<rect width="{w}" height="{h}" fill="#08111a"/>',
           '<pattern id="pg" width="22" height="22" patternUnits="userSpaceOnUse"><path d="M22 0H0V22" fill="none" '
           'stroke="#0f1e26"/></pattern>',
           f'<rect width="{w}" height="{h}" fill="url(#pg)"/>']
    fx, fw = 26, w - 52
    for j in range(6):
        out.append(f'<rect x="{fx + j * (fw / 6) + 3:.1f}" y="16" width="{fw / 6 - 6:.1f}" height="60" rx="6" '
                   f'fill="#0f1c26" stroke="{PAL["line"]}"/>')
        out.append(f'<circle cx="{fx + j * (fw / 6) + fw / 12:.1f}" cy="46" r="{9 + (j % 3) * 3}" fill="none" '
                   f'stroke="{segs[j][1]}" stroke-width="2" opacity=".8"/>')
    cx = fx
    for frac, col, lab in segs:
        sw = fw * frac
        out.append(f'<rect x="{cx + 1:.1f}" y="88" width="{sw - 2:.1f}" height="18" rx="4" fill="{col}" opacity=".9"/>')
        if fonts["JB5"].width(lab, 11) + 6 <= sw:
            out.append(f'<text class="pa" x="{cx + 4:.1f}" y="124">{esc(lab)}</text>')
        cx += sw
    out.append(f'<path d="M{fx + fw * 0.58:.1f} 82V112" stroke="{PAL["text"]}" stroke-width="2"/>')
    return "\n".join(out)


def build_card(project: dict, root: Path) -> str:
    """Project card: preview with a detection-style label, title, badge, wrapped description, tech chips."""
    fonts_dir, data = _paths(root)
    fonts = load_fonts(str(fonts_dir))
    w, h, ih = 434, 336, 178
    out = [f'<clipPath id="cl"><rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14"/></clipPath>',
           f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="{PAL["panel"]}"/>',
           '<g clip-path="url(#cl)">']
    if project["thumb"]:
        b64 = base64.b64encode((data / "thumbs" / project["thumb"]).read_bytes()).decode()
        out.append(f'<image x="0" y="0" width="{w}" height="{ih}" preserveAspectRatio="xMidYMid slice" '
                   f'xlink:href="data:image/jpeg;base64,{b64}"/>')
        out.append(f'<rect x="0" y="0" width="{w}" height="{ih}" fill="url(#fade)"/>')
    else:
        out.append(_praxis_art(fonts, w, ih))
    out.append("</g>")
    out.append(f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="14" fill="none" stroke="{PAL["line"]}"/>')
    out.append(corners(12, 12, w - 24, ih - 22, n=14, op=0.9))
    tw = fonts["JB7"].width(project["tag"], 12) + 14
    out.append(f'<rect x="12" y="{ih - 34}" width="{tw:.1f}" height="22" fill="{PAL["cyan"]}"/>'
               f'<text class="tg" x="19" y="{ih - 18.5}">{esc(project["tag"])}</text>')
    out.append(f'<text class="ti" x="24" y="{ih + 38}">{esc(fonts["SG7"].use(project["title"]))}</text>')
    bw = fonts["JB7"].width(project["badge"], 10.5, ls=0.5) + 16
    gold = project.get("accent") == "gold"
    fill, stroke, ink = ("#3a2a05", "#d4a72c", "#f2cc60") if gold else (PAL["panel2"], PAL["line"], PAL["sub"])
    out.append(f'<rect x="{w - 24 - bw:.1f}" y="{ih + 22}" width="{bw:.1f}" height="22" rx="11" fill="{fill}" '
               f'stroke="{stroke}"/><text class="bd" x="{w - 24 - bw / 2:.1f}" y="{ih + 37}" text-anchor="middle" '
               f'fill="{ink}">{esc(project["badge"])}</text>')
    for i, line in enumerate(wrap(fonts["SG5"], project["desc"], 14.5, w - 48)[:3]):
        out.append(f'<text class="ds" x="24" y="{ih + 66 + i * 20}">{esc(line)}</text>')
    x = 24.0
    for chip in project["chips"]:
        cw = fonts["JB5"].width(chip, 11.5) + 16
        out.append(f'<rect x="{x:.1f}" y="{h - 40}" width="{cw:.1f}" height="22" rx="6" fill="{PAL["panel2"]}" '
                   f'stroke="{PAL["line"]}"/><text class="ch" x="{x + 8:.1f}" y="{h - 25}">{esc(chip)}</text>')
        x += cw + 6
    defs = ('<defs><linearGradient id="fade" x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stop-color="#0b1117" '
            'stop-opacity="0"/><stop offset="1" stop-color="#0b1117" stop-opacity=".85"/></linearGradient></defs>')
    css = (f".tg{{font:12px JB7;fill:{PAL['ink']}}}.ti{{font:24px SG7;fill:{PAL['text']}}}"
           f".bd{{font:10.5px JB7;letter-spacing:.5px}}.ds{{font:14.5px SG5;fill:{PAL['sub']}}}"
           f".ch{{font:11.5px JB5;fill:{PAL['cyan']}}}.pa{{font:11px JB5;fill:{PAL['sub']}}}")
    return svg_doc(w, h, defs + "\n".join(out), fonts, f'{project["title"]} – {project["desc"]}', css)


def load_content(root: Path = ROOT) -> dict:
    return json.loads((root / "scripts" / "content.json").read_text(encoding="utf-8"))


def main(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    content = load_content()
    outputs = {
        "banner.svg": build_banner(content, ROOT),
        "banner-mobile.svg": build_banner_mobile(content, ROOT),
        "typing.svg": build_typing(content, ROOT),
        "stack.svg": build_stack(content, ROOT),
    }
    for project in content["projects"]:
        outputs[f'card-{project["slug"]}.svg'] = build_card(project, ROOT)
    for name, svg in outputs.items():
        (out_dir / name).write_text(svg, encoding="utf-8")
        print(f"{name}: {len(svg) / 1024:.1f} KB")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets")
