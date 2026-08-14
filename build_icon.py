"""Gera um .ico (gamepad tema) para o JoyMap, usado no .exe."""
from PIL import Image, ImageDraw
import os

SIZES = [16, 24, 32, 48, 64, 128, 256]
BG = (25, 118, 210)      # azul Windows
FACE = (250, 250, 250)
BTN = (213, 0, 0)
ACCENT = (255, 193, 7)

out = os.path.join(os.path.dirname(__file__), "JoyMap.ico")
base = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
b = ImageDraw.Draw(base)

def draw(size):
    g = base.resize((size, size), Image.LANCZOS)
    gd = ImageDraw.Draw(g)
    s = size
    m = s / 256.0
    pad = 14 * m
    gd.ellipse([pad, pad, s - pad, s - pad], fill=BG, outline=(0, 0, 0, 0))
    gd.ellipse([pad * .5, pad * .2, pad * 1.8, pad * 1.6], fill=BG)
    gd.ellipse([s - pad * 1.8, pad * .2, s - pad * .5, pad * 1.6], fill=BG)
    r = 12 * m
    x1, y1 = s * .30, s * .55
    x2, y2 = s * .70, s * .55
    gd.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=FACE)
    gd.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=FACE)
    bx, by = s * .76, s * .72
    rad = 9 * m
    off = 22 * m
    for dx, dy, col in [(0, -off, BTN), (off, 0, ACCENT), (-off, 0, ACCENT), (0, off, BTN)]:
        gd.ellipse([bx + dx - rad, by + dy - rad, bx + dx + rad, by + dy + rad], fill=col)
    return g

imgs = [draw(s) for s in SIZES]
# Salva a partir da imagem 256 (maior); o Pillow redimensiona para cada size.
imgs[-1].save(out, format="ICO", sizes=[(s, s) for s in SIZES])
print("salvo:", out, "tamanho:", os.path.getsize(out), "bytes")
