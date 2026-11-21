"""Colours shared by every asset."""

PAL = {
    # panels and text
    "bg": "#0d1117", "panel": "#0b1117", "panel2": "#0f1820", "line": "#1f2c36", "grid": "#0f1e26",
    "hud": "#5d7280", "text": "#e6edf3", "sub": "#93a8b4", "muted": "#6b7d89",
    "cyan": "#22d3ee", "green": "#3fb950", "ink": "#03141a", "rec": "#f85149",
    # banner background
    "bg0": "#05080c", "bg1": "#0a1a21",
    # face mesh
    "mesh_fill0": "#07161a", "mesh_fill1": "#16574f", "mesh_line": "#226f62", "contour": "#2dd4bf",
    # head-pose axes (X red, Y green, Z blue)
    "ax_x": "#ff5c5c", "ax_y": "#4ade80", "ax_z": "#5aa2ff",
}


def luminance(hex6: str) -> float:
    # https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
    def channel(v: int) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def on_dark(hex6: str) -> str:
    """Brand colour that stays readable on a near-black panel."""
    if luminance(hex6) >= 0.06:
        return "#" + hex6
    t = 0.62
    rgb = (int(hex6[i:i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{round(c + (255 - c) * t):02x}" for c in rgb)


def lerp_hex(c0: str, c1: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    a = [int(c0[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))
