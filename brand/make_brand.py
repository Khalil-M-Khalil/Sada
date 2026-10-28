"""Regenerates the Sada logo files. Needs Pillow:  python make_brand.py
Concept: an echo. Ripples leave one source point; where something moves, the middle ripple breaks and a coral dot marks it."""
import math, os
from PIL import Image, ImageDraw, ImageFont

BG1, BG2 = (22, 38, 74), (9, 17, 33)
AZ, VI, CO, INK = (79, 124, 255), (185, 140, 255), (255, 107, 87), (232, 238, 252)
C, W, DOT, FONT_ = (512, 512), 52, 78, None
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DIM = (96, 92, 176)
GAP = 315  # direction of the disturbance: up and to the right
# (centre-line radius, colour, start angle, end angle); None angles = full circle. Angles run clockwise from 3 o'clock.
RINGS = [(185, AZ, None, None), (315, VI, GAP + 30, GAP - 30 + 360), (412, DIM, GAP - 55, GAP + 55)]


def font(size):  # first font found: Windows, then Linux
    for p in ("C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf", FONT):
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            pass
    return ImageFont.load_default()


def pt(r, ang, f=1.0):
    return C[0] * f + r * f * math.cos(math.radians(ang)), C[1] * f + r * f * math.sin(math.radians(ang))


def icon(size=1024, plain=False):
    k = 4
    s = size * k
    f = s / 1024
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    if not plain:
        grad = Image.new("RGBA", (s, s))
        gd = ImageDraw.Draw(grad)
        for y in range(s):
            t = y / s
            gd.line([(0, y), (s, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)) + (255,))
        mask = Image.new("L", (s, s), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(230 * f), fill=255)
        img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    cx, cy, w = C[0] * f, C[1] * f, W * f
    for rc, col, a0, a1 in RINGS:
        r = (rc + W / 2) * f  # PIL measures the outer radius
        box = [cx - r, cy - r, cx + r, cy + r]
        if a0 is None:
            d.arc(box, 0, 360, fill=col, width=int(w))
            continue
        if a1 > 360:
            d.arc(box, a0, 360, fill=col, width=int(w))
            d.arc(box, 0, a1 - 360, fill=col, width=int(w))
        else:
            d.arc(box, a0, a1, fill=col, width=int(w))
        for ang in (a0, a1):
            ex, ey = pt(rc, ang, f)
            d.ellipse([ex - w / 2, ey - w / 2, ex + w / 2, ey + w / 2], fill=col)
    mx, my = pt(315, GAP, f)  # the moving object, sitting in the gap of the middle ring
    d.ellipse([mx - 58 * f, my - 58 * f, mx + 58 * f, my + 58 * f], fill=CO)
    d.ellipse([cx - DOT * f, cy - DOT * f, cx + DOT * f, cy + DOT * f], fill=INK)
    return img.resize((size, size), Image.LANCZOS)


def svg():
    parts = []
    for rc, col, a0, a1 in RINGS:
        if a0 is None:
            parts.append(f'<circle cx="{C[0]}" cy="{C[1]}" r="{rc}" fill="none" stroke="rgb{col}" stroke-width="{W}"/>')
        else:
            (x0, y0), (x1, y1) = pt(rc, a0), pt(rc, a1)
            large = 1 if (a1 - a0) > 180 else 0
            parts.append(f'<path d="M{x0:.1f},{y0:.1f} A{rc},{rc} 0 {large} 1 {x1:.1f},{y1:.1f}" fill="none" stroke="rgb{col}" stroke-width="{W}" stroke-linecap="round"/>')
    mx, my = pt(315, GAP)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="rgb{BG1}"/><stop offset="1" stop-color="rgb{BG2}"/></linearGradient></defs>'
            f'<rect width="1024" height="1024" rx="230" fill="url(#g)"/>{"".join(parts)}'
            f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="58" fill="rgb{CO}"/><circle cx="{C[0]}" cy="{C[1]}" r="{DOT}" fill="rgb{INK}"/></svg>')


def wizard(w, h, big):
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(BG1[i] + (BG2[i] - BG1[i]) * t) for i in range(3)))
    if big:
        ic = icon(112)
        img.paste(ic, ((w - 112) // 2, 44), ic)
        d.text((w // 2, 190), "Sada", font=font(30), fill=INK, anchor="mm")
        d.text((w // 2, 222), "Wi-Fi motion sensing", font=font(12), fill=(154, 170, 208), anchor="mm")
        d.text((w // 2, h - 20), "Local only. Nothing leaves\nthis computer.", font=font(10), fill=(154, 170, 208), anchor="mm", align="center")
    else:
        ic = icon(48)
        img.paste(ic, ((w - 48) // 2, (h - 48) // 2), ic)
    return img


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))  # write next to this script
    icon(512).save("sada-logo-512.png")
    icon(1024, plain=True).save("sada-mark-transparent.png")
    icon(256).save("sada.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    open("sada-logo.svg", "w").write(svg())
    wizard(164, 314, True).save("wizard_large.bmp")
    wizard(55, 58, False).save("wizard_small.bmp")
    print("done")
