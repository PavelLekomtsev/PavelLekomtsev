"""SVG document and drawing helpers."""
from .palette import PAL


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def rect_path(x: float, y: float, w: float, h: float) -> str:
    return f"M{x:.1f} {y:.1f}H{x + w:.1f}V{y + h:.1f}H{x:.1f}Z"


def corners(x, y, w, h, n=14, color=PAL["cyan"], sw=2, op=0.75) -> str:
    """Camera-frame corner brackets around a rectangle."""
    return (f'<g stroke="{color}" stroke-width="{sw}" fill="none" opacity="{op}" stroke-linecap="square">'
            f'<path d="M{x} {y + n}V{y}H{x + n}"/><path d="M{x + w - n} {y}H{x + w}V{y + n}"/>'
            f'<path d="M{x} {y + h - n}V{y + h}H{x + n}"/><path d="M{x + w - n} {y + h}H{x + w}V{y + h - n}"/></g>')


def wrap(font, text: str, size: float, max_w: float) -> list:
    """Greedy word wrap measured with the font's real advances."""
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}" if cur else word
        if not cur or font.width(cand, size) <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def svg_doc(w: int, h: int, body: str, fonts: dict, title: str, css: str = "", desc: str = "") -> str:
    """Standalone SVG with embedded font subsets; call it after the body has registered its text."""
    font_css = "\n".join(c for c in (f.css() for f in fonts.values()) if c)
    desc_el = f"<desc>{esc(desc)}</desc>\n" if desc else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(title)}">\n'
            f"<title>{esc(title)}</title>\n{desc_el}"
            f"<!-- Fonts: Space Grotesk and JetBrains Mono, SIL Open Font License 1.1 (subsets) -->\n"
            f"<style>\n{font_css}\ntext{{font-kerning:none}}\n{css}\n</style>\n{body}\n</svg>\n")
