"""Draw ``app/assets/icon.ico``: red rounded tile, white play button, text lines."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[2] / "app" / "assets" / "icon.ico"


def tile(size: int = 256) -> Image.Image:
    """One large frame; smaller sizes are resampled from it."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256
    d.rounded_rectangle([8 * s, 8 * s, 248 * s, 248 * s], radius=56 * s, fill=(196, 48, 43, 255))
    d.polygon([(64 * s, 52 * s), (64 * s, 140 * s), (138 * s, 96 * s)], fill=(255, 255, 255, 255))
    for i, width in enumerate((176, 140, 160)):
        y = (162 + i * 28) * s
        d.rounded_rectangle([40 * s, y, (40 + width) * s, y + 14 * s], radius=7 * s, fill=(255, 255, 255, 235))
    return img


def main() -> None:
    """Write the .ico with the usual Windows sizes."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    big = tile(256)
    big.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(OUT.with_suffix(".png"))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
