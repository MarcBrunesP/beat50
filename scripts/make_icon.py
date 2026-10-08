"""Generates assets/beat50.png and assets/beat50.icns: the "groove" icon, a close-up of a record's grooves.

Drawn with the standard library on the macOS icon grid (an 824 px rounded square inside 1024), scaled with sips
and iconutil. Run it once; the results are committed.
"""
import math
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path

SIZE = 1024
ROOT = Path(__file__).resolve().parent.parent

BODY, CORNER = 824, 184             # the rounded square and its corner radius
OFFSET = (SIZE - BODY) / 2
NAVY, BLUE, AMBER = (10, 31, 68), (11, 95, 184), (240, 177, 46)
CENTRE = OFFSET + 600               # the record's centre, near the bottom-right corner
RINGS = list(range(620, 223, -44))  # outermost first; blue, navy, blue... inwards
LABEL, HOLE = 150, 16
EDGES = sorted(RINGS + [LABEL, HOLE])


def _colour(d):
    """Colour at distance d from the record's centre, without antialiasing."""
    if d < HOLE:
        return NAVY
    if d < LABEL:
        return AMBER
    inside = [k for k, r in enumerate(RINGS) if d < r]
    if not inside:
        return NAVY
    return BLUE if inside[-1] % 2 == 0 else NAVY


def _clamp(v):
    return max(0.0, min(1.0, v))


def _body_alpha(x, y):
    """Coverage of the rounded square, from its signed distance."""
    half = BODY / 2 - CORNER
    qx = abs(x - SIZE / 2) - half
    qy = abs(y - SIZE / 2) - half
    dist = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - CORNER
    return _clamp(0.5 - dist)


def _pixel(x, y):
    px, py = x + 0.5, y + 0.5
    alpha = _body_alpha(px, py)
    if alpha == 0:
        return b"\x00\x00\x00\x00"
    d = math.hypot(px - CENTRE, py - CENTRE)
    edge = min(EDGES, key=lambda r: abs(r - d))
    if abs(edge - d) < 1:
        t = _clamp(edge - d + 0.5)  # share of the pixel inside this edge
        inner, outer = _colour(edge - 1), _colour(edge + 1)
        rgb = [round(i * t + o * (1 - t)) for i, o in zip(inner, outer)]
    else:
        rgb = _colour(d)
    return bytes((*rgb, round(255 * alpha)))


def _png(path):
    rows = b"".join(b"\x00" + b"".join(_pixel(x, y) for x in range(SIZE)) for y in range(SIZE))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "beat50.png"
        _png(base)
        iconset = Path(tmp) / "beat50.iconset"
        iconset.mkdir()
        for side in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                name = f"icon_{side}x{side}{'@2x' if scale == 2 else ''}.png"
                px = str(side * scale)
                subprocess.run(["sips", "-z", px, px, str(base), "--out", str(iconset / name)],
                               check=True, capture_output=True)
        target = ROOT / "assets" / "beat50.icns"
        target.parent.mkdir(exist_ok=True)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)
        shutil.copy(base, ROOT / "assets" / "beat50.png")
    print(target)


if __name__ == "__main__":
    main()
