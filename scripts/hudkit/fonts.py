"""Static font instances that measure text and embed themselves as base64 subsets."""
import base64
import io

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer


class Font:
    def __init__(self, path: str, wght: int, family: str):
        # https://fonttools.readthedocs.io/en/latest/varLib/instancer.html
        self.font = instancer.instantiateVariableFont(TTFont(path), {"wght": wght})
        self.family = family
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.hmtx = self.font["hmtx"]
        self.chars = set()

    def use(self, text: str) -> str:
        """Register the characters for the embedded subset and return the text unchanged."""
        self.chars.update(text)
        return text

    def width(self, text: str, size: float, ls: float = 0.0) -> float:
        """Advance width in px; exact because layout features and kerning are disabled."""
        self.use(text)
        adv = sum(self.hmtx[self.cmap[ord(ch)]][0] for ch in text)
        return adv * size / self.upm + ls * len(text)

    def cap(self, size: float) -> float:
        return self.font["OS/2"].sCapHeight * size / self.upm

    def css(self) -> str:
        if not self.chars:
            return ""
        buf = io.BytesIO()
        self.font.save(buf)
        buf.seek(0)
        font = TTFont(buf)
        # https://fonttools.readthedocs.io/en/latest/subset/index.html
        opts = subset.Options()
        opts.layout_features = []
        opts.hinting = False
        opts.notdef_outline = True
        opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14]
        sub = subset.Subsetter(options=opts)
        sub.populate(text="".join(sorted(self.chars)))
        sub.subset(font)
        out = io.BytesIO()
        font.save(out)
        b64 = base64.b64encode(out.getvalue()).decode()
        return f"@font-face{{font-family:'{self.family}';src:url(data:font/ttf;base64,{b64}) format('truetype')}}"


def load_fonts(fonts_dir: str) -> dict:
    return {
        "SG7": Font(f"{fonts_dir}/SpaceGrotesk.ttf", 700, "SG7"),
        "SG5": Font(f"{fonts_dir}/SpaceGrotesk.ttf", 500, "SG5"),
        "JB5": Font(f"{fonts_dir}/JetBrainsMono.ttf", 500, "JB5"),
        "JB7": Font(f"{fonts_dir}/JetBrainsMono.ttf", 700, "JB7"),
    }
