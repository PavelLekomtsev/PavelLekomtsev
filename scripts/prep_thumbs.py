#!/usr/bin/env python3
"""Prepare the project-card thumbnails (868x356 JPEG, 2x the card image area).

Dev-only helper: needs Pillow, which CI does not install.

Sources (download them into one folder, then pass it as SRC_DIR):
  neosmart.png      https://raw.githubusercontent.com/PavelLekomtsev/NeoSmart/main/Documentation/extras/TrafficCounter.png
  platescanner.png  https://raw.githubusercontent.com/encore-ecosystem/PlateScanner/main/appendices/articles/Assets/third_out_cropped.png
  football.jpg      frame at t=14 s of
                    https://raw.githubusercontent.com/PavelLekomtsev/CV-Football-Analyzer/main/OutputVideo/output_video.mp4
                    (ffmpeg -ss 14 -i <url> -frames:v 1 -q:v 2 football.jpg)

usage: prep_thumbs.py SRC_DIR OUT_DIR
"""
import sys
from pathlib import Path

from PIL import Image

W, H = 868, 356

# name: (source file, vertical crop position 0..1, optional region of interest as fractions x0, y0, x1, y1)
JOBS = {
    "neosmart.jpg": ("neosmart.png", 0.5, None),
    "platescanner.jpg": ("platescanner.png", 0.45, None),
    "football.jpg": ("football.jpg", 0.5, (0.2, 0.3, 0.72, 0.72)),
}


def prep(src: Path, dst: Path, crop_y: float, roi=None) -> None:
    im = Image.open(src).convert("RGB")
    if roi:
        x0, y0, x1, y1 = roi
        im = im.crop((round(x0 * im.width), round(y0 * im.height), round(x1 * im.width), round(y1 * im.height)))
    scale = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    left = (im.width - W) // 2
    top = int((im.height - H) * crop_y)
    im.crop((left, top, left + W, top + H)).save(dst, "JPEG", quality=82, optimize=True, progressive=True)


def main(argv):
    src_dir, out_dir = Path(argv[1]), Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (src, crop_y, roi) in JOBS.items():
        prep(src_dir / src, out_dir / name, crop_y, roi)
        print(f"{name}: {(out_dir / name).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv)
