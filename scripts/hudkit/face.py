"""MediaPipe canonical face mesh rendered with a head pose, plus draw_axis-style pose axes."""
import json
import math
from typing import NamedTuple

from .palette import PAL, lerp_hex


class FaceModel(NamedTuple):
    verts: list
    tris: list
    contours: dict


def load_face(obj_path: str, contours_path: str) -> FaceModel:
    verts, tris = [], []
    with open(obj_path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.split()
            if not parts:
                continue
            if parts[0] == "v":
                verts.append(tuple(map(float, parts[1:4])))
            elif parts[0] == "f":
                tris.append(tuple(int(t.split("/")[0]) - 1 for t in parts[1:4]))
    with open(contours_path, encoding="utf-8") as fh:
        contours = {k: [tuple(p) for p in v] for k, v in json.load(fh).items()}
    return FaceModel(verts, tris, contours)


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def head_rotation(yaw: float, pitch: float, roll: float) -> list:
    """R = Rx(pitch)·Ry(-yaw)·Rz(roll); its columns are the X (red), Y (green), Z (blue) axes of draw_axis()."""
    # https://github.com/thohemp/6DRepNet/blob/master/sixdrepnet/utils.py
    y, p, r = -math.radians(yaw), math.radians(pitch), math.radians(roll)
    rx = [[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]]
    ry = [[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]]
    rz = [[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]]
    return _matmul(_matmul(rx, ry), rz)


def _apply(rot, v):
    return tuple(sum(rot[i][k] * v[k] for k in range(3)) for i in range(3))


def _area2(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _pt(p):
    return f"{p[0]:.1f} {p[1]:.1f}"


def face_svg(model: FaceModel, cx: float, cy: float, height: float, yaw: float, pitch: float, roll: float):
    """Shaded, back-face-culled mesh centred at (cx, cy) and scaled to `height`; returns (markup, bbox)."""
    # model axes: x right, y up, z towards the camera -> image basis (right, down, out of screen)
    base = [(x, -y, z) for x, y, z in model.verts]
    rot = head_rotation(yaw, pitch, roll)
    q = [_apply(rot, m) for m in base]

    # https://en.wikipedia.org/wiki/Back-face_culling
    front = sum(1 for t in model.tris if _area2(*(base[i] for i in t)) > 0)
    s0 = 1 if front > len(model.tris) / 2 else -1
    xs, ys = [v[0] for v in q], [v[1] for v in q]
    k = height / (max(ys) - min(ys))
    ox = cx - k * (max(xs) + min(xs)) / 2
    oy = cy - k * (max(ys) + min(ys)) / 2
    pts = [(ox + k * v[0], oy + k * v[1]) for v in q]

    light = (-0.35, -0.55, 0.76)
    tris, visible = [], set()
    for t in model.tris:
        a, b, c = (pts[i] for i in t)
        if _area2(a, b, c) * s0 <= 0:
            continue
        visible.update(t)
        qa, qb, qc = (q[i] for i in t)
        u = [qb[i] - qa[i] for i in range(3)]
        v = [qc[i] - qa[i] for i in range(3)]
        n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        ln = math.sqrt(sum(c_ * c_ for c_ in n)) or 1.0
        n = [c_ / ln for c_ in n]
        if n[2] < 0:
            n = [-c_ for c_ in n]
        lam = max(0.0, sum(n[i] * light[i] for i in range(3)))
        depth = (qa[2] + qb[2] + qc[2]) / 3
        tris.append((depth, (a, b, c), lerp_hex(PAL["mesh_fill0"], PAL["mesh_fill1"], lam ** 1.3)))
    # https://en.wikipedia.org/wiki/Painter%27s_algorithm
    tris.sort(key=lambda t_: t_[0])

    out = [f'<g class="mesh" stroke="{PAL["mesh_line"]}" stroke-width=".55" stroke-linejoin="round">']
    out += [f'<path d="M{_pt(a)}L{_pt(b)}L{_pt(c)}Z" fill="{col}"/>' for _, (a, b, c), col in tris]
    out.append("</g>")

    lines = [f"M{_pt(pts[i])}L{_pt(pts[j])}" for pairs in model.contours.values() for i, j in pairs
             if i in visible and j in visible]
    out.append(f'<path class="mesh" d="{"".join(lines)}" fill="none" stroke="{PAL["contour"]}" stroke-width="1.3" '
               f'stroke-linecap="round" opacity=".95" filter="url(#glow)"/>')

    eyes = []
    for key in ("LEFT_EYE", "RIGHT_EYE"):
        idx = {i for pair in model.contours[key] for i in pair}
        ex = sum(pts[i][0] for i in idx) / len(idx)
        ey = sum(pts[i][1] for i in idx) / len(idx)
        eyes.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="2.4"/>')
    out.append(f'<g class="mesh" fill="{PAL["contour"]}">{"".join(eyes)}</g>')

    # pose axes from the nose tip (landmark 1), drawn exactly like draw_axis()
    nose = pts[1]
    size = 0.62 * k * (max(xs) - min(xs))
    axes = []
    for col, color, cls in ((0, PAL["ax_x"], "ax ax1"), (1, PAL["ax_y"], "ax ax2"), (2, PAL["ax_z"], "ax ax3")):
        end = (nose[0] + size * rot[0][col], nose[1] + size * rot[1][col])
        axes.append(f'<path class="{cls}" pathLength="100" d="M{_pt(nose)}L{_pt(end)}" stroke="{color}"/>')
    out.append(f'<g stroke-width="3.2" stroke-linecap="round" fill="none" filter="url(#glow)">{"".join(axes)}</g>')
    out.append(f'<circle class="ax ax0" cx="{nose[0]:.1f}" cy="{nose[1]:.1f}" r="3.4" fill="{PAL["text"]}"/>')

    bbox = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
    return "\n".join(out), bbox
