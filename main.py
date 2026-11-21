#!/usr/bin/env python3
"""Republic of Meridia - invented passport spread.

Writes one image to /output/entry.png (or $OUTPUT_PATH): an open passport
spread for a country that does not exist. Left page: the data page with a
portrait, personal details and a machine-readable strip. Right page: visas
and arrival/departure stamps from neighbouring countries, plus one piece of
paperwork that says what kind of place Meridia is.

Primary path draws everything with Pillow. If Pillow (or a usable font) is
not available, the program copies the bundled fallback.png - the same image,
rendered by this program - so it still runs in a stdlib-only sandbox.
Output is fully deterministic: no randomness, no timestamps.
"""

import math
import os
import shutil
import sys

W, H = 1024, 720
OUT = os.environ.get("OUTPUT_PATH", "/output/entry.png")
_HERE = os.path.dirname(os.path.abspath(__file__))
FALLBACK = os.path.join(_HERE, "fallback.png")

# ---------------------------------------------------------------- palette
DESK = (36, 43, 50)
PAGE = (233, 238, 241)
PAGE_EDGE = (205, 216, 222)
NAVY = (22, 50, 79)
NAVY_DARK = (16, 38, 60)
GOLD = (176, 141, 62)
GOLD_LIGHT = (201, 162, 39)
INK = (20, 39, 61)
LABEL = (90, 107, 120)
RULE = (120, 140, 155)
GUILLOCHE = (127, 160, 181)
BLUE_INK = (31, 78, 121)
PURPLE_INK = (106, 74, 138)
GREEN_INK = (46, 107, 79)
RED_INK = (163, 51, 39)
VISA_BG = (238, 243, 230)
VISA_GREEN = (61, 107, 53)
SKIN = (223, 176, 138)
SKIN_DARK = (198, 150, 112)
HAIR = (51, 36, 28)

FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
]


# ------------------------------------------------------------------- MRZ
def _mrz_value(ch):
    if ch == "<":
        return 0
    if ch.isdigit():
        return int(ch)
    return ord(ch) - 55  # A=10 .. Z=35


def _mrz_check(text):
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(text):
        total += _mrz_value(ch) * weights[i % 3]
    return str(total % 10)


def build_mrz():
    """TD3 two-line MRZ for the holder. Verified against the ICAO example
    L898902C36UTO7408122F1204159ZE184226B<<<<<10 in _self_check()."""
    doc = "MD4819207"          # passport number, 9 chars
    nat = "MER"
    dob = "920314"             # 14 MAR 1992
    sex = "F"
    exp = "340611"             # 11 JUN 2034
    optional = "<" * 14
    line1_name = "VOSS<<ELENA<MARIS"
    line1 = ("P<MER" + line1_name).ljust(44, "<")
    doc_c = _mrz_check(doc)
    dob_c = _mrz_check(dob)
    exp_c = _mrz_check(exp)
    opt_c = _mrz_check(optional)
    # composite check digit covers doc+check, dob+check, expiry+check,
    # optional data+check (nationality and sex excluded) - ICAO Doc 9303.
    composite_src = doc + doc_c + dob + dob_c + exp + exp_c + optional + opt_c
    line2 = (doc + doc_c + nat + dob + dob_c + sex + exp + exp_c
             + optional + opt_c + _mrz_check(composite_src))
    assert len(line1) == 44 and len(line2) == 44
    return line1, line2


def _self_check():
    # ICAO Doc 9303 worked example must reproduce exactly.
    doc, nat, dob, sex, exp = "L898902C3", "UTO", "740812", "F", "120415"
    optional = "ZE184226B<<<<<"
    doc_c = _mrz_check(doc)
    dob_c = _mrz_check(dob)
    exp_c = _mrz_check(exp)
    opt_c = _mrz_check(optional)
    composite_src = doc + doc_c + dob + dob_c + exp + exp_c + optional + opt_c
    line2 = (doc + doc_c + nat + dob + dob_c + sex + exp + exp_c
             + optional + opt_c + _mrz_check(composite_src))
    assert line2 == "L898902C36UTO7408122F1204159ZE184226B<<<<<10", line2


# ----------------------------------------------------------------- fonts
def load_fonts():
    from PIL import ImageFont

    found = {}
    for path in FONT_PATHS:
        if os.path.exists(path):
            key = os.path.basename(path).replace(".ttf", "")
            found[key] = path
    if "DejaVuSans" not in found or "DejaVuSans-Bold" not in found:
        raise ImportError("no usable sans fonts")
    if "DejaVuSansMono" not in found:
        raise ImportError("no usable mono font")

    def f(name, size):
        return ImageFont.truetype(found[name], size)

    serif = found.get("DejaVuSerif-Bold") or found["DejaVuSans-Bold"]
    serif_reg = found.get("DejaVuSerif") or found["DejaVuSans"]
    serif_it = found.get("DejaVuSerif-Italic") or serif_reg
    return {
        "serif_b": lambda s: ImageFont.truetype(serif, s),
        "serif": lambda s: ImageFont.truetype(serif_reg, s),
        "serif_it": lambda s: ImageFont.truetype(serif_it, s),
        "sans": lambda s: f("DejaVuSans", s),
        "sans_b": lambda s: f("DejaVuSans-Bold", s),
        "mono": lambda s: f("DejaVuSansMono", s),
    }


# --------------------------------------------------------------- helpers
def spaced(draw, xy, text, font, fill, tracking=2):
    """Draw text with manual letter tracking; returns width used."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def text_w(draw, text, font):
    return draw.textlength(text, font=font)


def rounded(draw, box, radius, **kw):
    draw.rounded_rectangle(box, radius=radius, **kw)


def guilloche(draw, x0, y0, x1, y1):
    """Faint security wave lines across a page."""
    yy = y0 + 8
    while yy < y1 - 4:
        pts = []
        x = x0
        while x <= x1:
            pts.append((x, yy + 2.0 * math.sin((x - x0) / 26.0 + yy / 40.0)))
            x += 6
        draw.line(pts, fill=GUILLOCHE + (12,), width=1)
        yy += 18


def watermark(draw, cx, cy, text, font):
    layer = _blank_layer()
    ld = _draw(layer)
    w = text_w(ld, text, font)
    ld.text((cx - w / 2, cy - 20), text, font=font, fill=(22, 50, 79, 14))
    layer = layer.rotate(-28, resample=0, center=(cx, cy))
    return layer


def _blank_layer():
    from PIL import Image

    return Image.new("RGBA", (W, H), (0, 0, 0, 0))


def _draw(img):
    from PIL import ImageDraw

    return ImageDraw.Draw(img)


def star_points(cx, cy, r_outer, r_inner, n=5):
    pts = []
    for i in range(2 * n):
        r = r_outer if i % 2 == 0 else r_inner
        a = -math.pi / 2 + i * math.pi / n
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def draw_arms(draw, cx, cy, s):
    """Small coat of arms: navy shield, gold star, sea waves, olive sprigs."""
    w, h = s, int(s * 1.15)
    x0, y0 = cx - w / 2, cy - h / 2
    x1, y1 = cx + w / 2, cy + h / 2
    shield = [
        (x0, y0), (x1, y0), (x1, y0 + h * 0.62),
        (cx, y1), (x0, y0 + h * 0.62),
    ]
    draw.polygon(shield, fill=NAVY, outline=GOLD, width=3)
    draw.polygon(star_points(cx, y0 + h * 0.30, s * 0.20, s * 0.085), fill=GOLD_LIGHT)
    for k in range(3):
        yy = y0 + h * (0.66 + k * 0.10)
        pts = []
        x = x0 + 6
        while x <= x1 - 6:
            pts.append((x, yy + 2.5 * math.sin((x - x0) / 9.0)))
            x += 4
        draw.line(pts, fill=GOLD_LIGHT, width=2)
    # olive sprigs left and right of the shield
    for sign in (-1, 1):
        bx = cx + sign * (w / 2 + 8)
        for k in range(4):
            ly = cy - h * 0.28 + k * h * 0.16
            draw.ellipse([bx - 4, ly - 2.5, bx + 4, ly + 2.5],
                         fill=(74, 110, 74))
        draw.arc([bx - 6, cy - h * 0.32, bx + 6, cy + h * 0.34],
                 start=90 if sign < 0 else 270, end=270 if sign < 0 else 90,
                 fill=(74, 110, 74), width=2)


def draw_portrait(draw, box):
    """Stylised passport photograph: shoulders, head, hair, soft features,
    halftone dots and a gold seal overlapping one corner."""
    x0, y0, x1, y1 = box
    cw, ch = x1 - x0, y1 - y0
    cx = (x0 + x1) / 2
    # background gradient
    for i in range(ch):
        t = i / max(ch - 1, 1)
        col = tuple(int(a + (b - a) * t) for a, b in zip((204, 216, 224), (169, 188, 201)))
        draw.line([(x0, y0 + i), (x1, y0 + i)], fill=col)
    # shoulders / blazer
    draw.polygon([(x0 + 8, y1), (x0 + 26, y0 + ch * 0.66), (cx - 16, y0 + ch * 0.60),
                  (cx + 16, y0 + ch * 0.60), (x1 - 26, y0 + ch * 0.66), (x1 - 8, y1)],
                 fill=(29, 47, 69))
    # shirt V + collar
    draw.polygon([(cx - 15, y0 + ch * 0.60), (cx, y0 + ch * 0.78), (cx + 15, y0 + ch * 0.60)],
                 fill=(235, 238, 240))
    draw.polygon([(cx - 15, y0 + ch * 0.60), (cx - 4, y0 + ch * 0.70), (cx, y0 + ch * 0.62),
                  (cx + 4, y0 + ch * 0.70), (cx + 15, y0 + ch * 0.60)],
                 fill=(200, 208, 214))
    # neck + head
    draw.rectangle([cx - 13, y0 + ch * 0.52, cx + 13, y0 + ch * 0.64], fill=SKIN_DARK)
    draw.ellipse([cx - 34, y0 + ch * 0.10, cx + 34, y0 + ch * 0.52], fill=SKIN)
    # hair: top mass + shoulder-length sides
    draw.pieslice([cx - 37, y0 + ch * 0.02, cx + 37, y0 + ch * 0.42],
                  start=180, end=360, fill=HAIR)
    draw.polygon([(cx - 37, y0 + ch * 0.16), (cx - 30, y0 + ch * 0.10),
                  (cx - 26, y0 + ch * 0.30), (cx - 34, y0 + ch * 0.52),
                  (cx - 40, y0 + ch * 0.44)], fill=HAIR)
    draw.polygon([(cx + 37, y0 + ch * 0.16), (cx + 30, y0 + ch * 0.10),
                  (cx + 26, y0 + ch * 0.30), (cx + 34, y0 + ch * 0.52),
                  (cx + 40, y0 + ch * 0.44)], fill=HAIR)
    draw.ellipse([cx - 36, y0 + ch * 0.06, cx + 36, y0 + ch * 0.26], fill=HAIR)
    draw.ellipse([cx - 30, y0 + ch * 0.10, cx + 30, y0 + ch * 0.34], fill=SKIN)
    # brows, eyes, nose, lips - kept soft and low contrast
    for s in (-1, 1):
        ex = cx + s * 13
        draw.arc([ex - 7, y0 + ch * 0.26, ex + 7, y0 + ch * 0.33],
                 start=200, end=340, fill=(70, 48, 36), width=2)
        draw.ellipse([ex - 4, y0 + ch * 0.315, ex + 4, y0 + ch * 0.345],
                     fill=(52, 40, 34))
        draw.ellipse([ex - 1, y0 + ch * 0.32, ex + 1.5, y0 + ch * 0.335],
                     fill=(240, 240, 240))
    draw.line([(cx + 1, y0 + ch * 0.34), (cx - 1, y0 + ch * 0.42)],
              fill=SKIN_DARK, width=2)
    draw.arc([cx - 5, y0 + ch * 0.42, cx + 5, y0 + ch * 0.46],
             start=0, end=180, fill=(150, 100, 85), width=2)
    draw.ellipse([cx - 7, y0 + ch * 0.478, cx + 7, y0 + ch * 0.495],
                 fill=(176, 106, 94))
    # halftone dots
    for gy in range(y0 + 4, y1 - 2, 6):
        for gx in range(x0 + 4, x1 - 2, 6):
            draw.ellipse([gx, gy, gx + 1, gy + 1], fill=(60, 70, 80, 10))
    draw.rectangle(box, outline=(120, 135, 148), width=2)


def seal_stamp(draw, cx, cy, r, ink):
    """Circular seal overlapping the photo corner."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ink, width=3)
    draw.ellipse([cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6],
                 outline=ink, width=1)
    draw.polygon(star_points(cx, cy, r * 0.42, r * 0.18), fill=ink)
    draw.arc([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2],
             start=210, end=330, fill=ink, width=2)


def rect_stamp(layer, box, lines, ink, angle, font_b, font_s):
    """Rectangular arrival/departure stamp, rotated, on its own layer."""
    from PIL import Image

    w = box[2] - box[0]
    h = box[3] - box[1]
    tmp = Image.new("RGBA", (w + 40, h + 40), (0, 0, 0, 0))
    td = _draw(tmp)
    td.rounded_rectangle([20, 20, 20 + w, 20 + h], radius=6,
                         outline=ink + (220,), width=3)
    td.rounded_rectangle([24, 24, 20 + w - 4, 20 + h - 4], radius=4,
                         outline=ink + (200,), width=1)
    y = 20 + 10
    for i, (txt, fnt) in enumerate(lines):
        ww = text_w(td, txt, fnt)
        td.text((20 + (w - ww) / 2, y), txt, font=fnt, fill=ink + (225,))
        y += 22 if i == 0 else 20
    tmp = tmp.rotate(angle, resample=2, expand=False)
    layer.alpha_composite(tmp, (box[0] - 20, box[1] - 20))


def circle_stamp(layer, cx, cy, r, lines, ink, angle, font_b, font_s):
    """Circular fee stamp."""
    from PIL import Image

    d = 2 * r + 40
    tmp = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    td = _draw(tmp)
    td.ellipse([20, 20, 20 + 2 * r, 20 + 2 * r], outline=ink + (220,), width=3)
    td.ellipse([26, 26, 20 + 2 * r - 6, 20 + 2 * r - 6], outline=ink + (200,), width=1)
    y = 20 + r - len(lines) * 11
    for txt, fnt in lines:
        ww = text_w(td, txt, fnt)
        td.text((20 + r - ww / 2, y), txt, font=fnt, fill=ink + (225,))
        y += 22
    tmp = tmp.rotate(angle, resample=2, expand=False)
    layer.alpha_composite(tmp, (cx - r - 20, cy - r - 20))


# ----------------------------------------------------------------- pages
def draw_left_page(img, F):
    d = _draw(img)
    x0, y0, x1, y1 = 24, 18, 500, 702
    d.rectangle([x0, y0, x1, y1], fill=PAGE)
    guilloche(d, x0 + 6, y0 + 130, x1 - 6, y1 - 100)
    wm = watermark(d, 262, 400, "MERIDIA", F["serif_b"](64))
    img.alpha_composite(wm)

    # header band
    d.rectangle([x0, y0, x1, y0 + 100], fill=NAVY)
    d.rectangle([x0, y0 + 100, x1, y0 + 104], fill=GOLD)
    t = "REPUBLIC OF MERIDIA"
    fw = F["serif_b"](30)
    tw = sum(text_w(d, c, fw) + 2 for c in t) - 2
    spaced(d, ((x0 + x1 - tw) / 2, y0 + 16), t, fw, GOLD_LIGHT, tracking=2)
    t2 = "RÉPUBLIQUE DE MÉRIDIE"
    f2 = F["sans"](13)
    tw2 = sum(text_w(d, c, f2) + 3 for c in t2) - 3
    spaced(d, ((x0 + x1 - tw2) / 2, y0 + 58), t2, f2, (200, 205, 190), tracking=3)
    d.line([(x0 + 40, y0 + 88), (x1 - 40, y0 + 88)], fill=GOLD, width=1)

    # coat of arms + document title
    draw_arms(d, 262, 158, 62)
    t3 = "PASSPORT"
    f3 = F["serif_b"](26)
    tw3 = text_w(d, t3, f3)
    d.text(((x0 + x1 - tw3) / 2, 196), t3, font=f3, fill=NAVY)
    t4 = "PASSEPORT"
    f4 = F["sans"](12)
    tw4 = sum(text_w(d, c, f4) + 4 for c in t4) - 4
    spaced(d, ((x0 + x1 - tw4) / 2, 228), t4, f4, LABEL, tracking=4)
    d.line([(x0 + 60, 252), (x1 - 60, 252)], fill=RULE, width=1)

    # type / code / number row
    row = "TYPE  P      CODE  MER      No.  MD4819207"
    fr = F["sans_b"](15)
    twr = text_w(d, row, fr)
    d.text(((x0 + x1 - twr) / 2, 262), row, font=fr, fill=INK)

    # photo
    draw_portrait(d, (44, 296, 194, 486))
    # gold seal overlapping the photo's lower corner (clear of the SEX field)
    seal = _blank_layer()
    sd = _draw(seal)
    seal_stamp(sd, 178, 470, 24, GOLD + (235,))
    img.alpha_composite(seal)

    # data fields right of the photo
    fx = 212
    fields = [
        ("SURNAME", "VOSS"),
        ("GIVEN NAMES", "ELENA MARIS"),
        ("NATIONALITY", "MERIDIAN"),
        ("DATE OF BIRTH", "14 MAR 1992"),
        ("PLACE OF BIRTH", "CALDARA, MERIDIA"),
        ("SEX", "F"),
    ]
    fy = 296
    for label, value in fields:
        d.text((fx, fy), label, font=F["sans"](11), fill=LABEL)
        d.text((fx, fy + 15), value, font=F["sans_b"](19), fill=INK)
        fy += 32
    d.line([(fx, 292), (fx, 486)], fill=RULE, width=1)

    # issue / expiry / authority row
    d.line([(44, 502), (480, 502)], fill=RULE, width=1)
    cols = [
        (44, "DATE OF ISSUE", "12 JUN 2024"),
        (200, "DATE OF EXPIRY", "11 JUN 2034"),
        (356, "AUTHORITY", "MINISTRY OF"),
    ]
    for cx, label, value in cols:
        d.text((cx, 514), label, font=F["sans"](11), fill=LABEL)
        d.text((cx, 529), value, font=F["sans_b"](17), fill=INK)
    d.text((356, 551), "THE INTERIOR", font=F["sans_b"](17), fill=INK)

    # holder's signature
    d.text((44, 580), "HOLDER'S SIGNATURE", font=F["sans"](11), fill=LABEL)
    sig = _blank_layer()
    sg = _draw(sig)
    sg.text((60, 592), "Elena M. Voss", font=F["serif_it"](26), fill=(31, 58, 95, 255))
    sig = sig.rotate(-4, resample=2, center=(140, 605))
    img.alpha_composite(sig)
    d.line([(44, 626), (300, 626)], fill=RULE, width=1)

    # machine-readable zone
    d.rectangle([x0 + 14, 640, x1 - 14, 692], fill=(214, 222, 228))
    line1, line2 = build_mrz()
    fm = F["mono"](16)
    d.text((x0 + 26, 648), line1, font=fm, fill=(15, 30, 45))
    d.text((x0 + 26, 670), line2, font=fm, fill=(15, 30, 45))


def draw_right_page(img, F):
    d = _draw(img)
    x0, y0, x1, y1 = 524, 18, 1000, 702
    d.rectangle([x0, y0, x1, y1], fill=PAGE)
    guilloche(d, x0 + 6, y0 + 70, x1 - 6, y1 - 6)
    wm = watermark(d, 762, 400, "MERIDIA", F["serif_b"](64))
    img.alpha_composite(wm)

    # header
    t = "VISAS"
    f = F["serif_b"](22)
    tw = text_w(d, t, f)
    d.text(((x0 + x1 - tw) / 2, 30), t, font=f, fill=NAVY)
    d.text((x1 - 30, 34), "8", font=F["sans_b"](16), fill=LABEL)
    d.line([(x0 + 40, 62), (x1 - 40, 62)], fill=RULE, width=1)

    # visa sticker: Republic of Tarnovia
    vx0, vy0, vx1, vy1 = 544, 74, 980, 226
    d.rectangle([vx0, vy0, vx1, vy1], fill=VISA_BG, outline=VISA_GREEN, width=2)
    d.rectangle([vx0 + 5, vy0 + 5, vx1 - 5, vy1 - 5], outline=VISA_GREEN, width=1)
    d.text((vx0 + 16, vy0 + 12), "VISA", font=F["sans_b"](26), fill=VISA_GREEN)
    d.text((vx0 + 16, vy0 + 46), "REPUBLIC OF TARNOVIA",
           font=F["sans_b"](16), fill=INK)
    visa_lines = [
        "SINGLE ENTRY  —  VALID FOR 30 DAYS",
        "NOT VALID FOR EMPLOYMENT",
        "ISSUED AT CALDARA  —  28 AUG 2024",
        "FEE PAID  —  40 MERIDIAN DINARS",
        "CONTROL No.  TV-2024-08813",
    ]
    yy = vy0 + 70
    for ln in visa_lines:
        d.text((vx0 + 16, yy), ln, font=F["sans"](13), fill=(40, 55, 45))
        yy += 15
    draw_arms(d, vx1 - 52, vy0 + 40, 44)

    # stamps
    layer = _blank_layer()
    fb, fs = F["sans_b"](15), F["sans"](11)
    rect_stamp(layer, (544, 240, 754, 314),
               [("TARNOVIA", fb), ("ARRIVAL  03 SEP 2024", fs), ("PORT OF LINDQVIST", fs)],
               BLUE_INK, -7, fb, fs)
    rect_stamp(layer, (770, 240, 980, 314),
               [("TARNOVIA", fb), ("DEPARTURE  17 SEP 2024", fs), ("PORT OF LINDQVIST", fs)],
               BLUE_INK, 5, fb, fs)
    rect_stamp(layer, (544, 328, 754, 402),
               [("VESSALIA", fb), ("ARRIVAL  22 JAN 2025", fs), ("HARBOUR GATE 4", fs)],
               PURPLE_INK, -5, fb, fs)
    rect_stamp(layer, (770, 328, 980, 402),
               [("VESSALIA", fb), ("DEPARTURE  05 FEB 2025", fs), ("HARBOUR GATE 4", fs)],
               PURPLE_INK, 8, fb, fs)
    rect_stamp(layer, (544, 416, 754, 490),
               [("KESTRELIA", fb), ("ARRIVAL  11 MAY 2025", fs), ("FERRY TERMINAL", fs)],
               GREEN_INK, -6, fb, fs)
    circle_stamp(layer, 875, 453, 36,
                 [("FEE PAID", F["sans_b"](13)), ("40 MD", F["sans_b"](15)),
                  ("CALDARA", F["sans"](10))],
                 GOLD, 10, fb, fs)
    img.alpha_composite(layer)

    # observations - the telling detail of the place
    ox0, oy0, ox1, oy1 = 544, 508, 980, 594
    d.rectangle([ox0, oy0, ox1, oy1], outline=NAVY, width=2)
    d.text((ox0 + 14, oy0 + 10), "OBSERVATIONS", font=F["sans_b"](13), fill=NAVY)
    obs = [
        "HOLDER IS A REGISTERED SEAFARER.",
        "MERIDIAN MARITIME AUTHORITY —",
        "SEAMAN'S BOOK No. MB-77120.",
    ]
    yy = oy0 + 32
    for ln in obs:
        d.text((ox0 + 14, yy), ln, font=F["sans"](14), fill=INK)
        yy += 19

    # red sea-only stamp
    layer2 = _blank_layer()
    rect_stamp(layer2, (544, 612, 980, 686),
               [("ARRIVAL BY SEA ONLY", F["sans_b"](17)),
                ("MERIDIA HAS NO INTERNATIONAL AIRPORT", F["sans"](12)),
                ("PORT OF CALDARA", F["sans"](11))],
               RED_INK, -3, fb, fs)
    img.alpha_composite(layer2)


# ------------------------------------------------------------------ render
def render():
    from PIL import Image, ImageDraw, ImageFilter

    _self_check()
    fonts = load_fonts()
    img = Image.new("RGBA", (W, H), DESK + (255,))
    # soft shadow under the spread
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([30, 26, 1006, 708], radius=6, fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(7))
    img.alpha_composite(shadow)

    draw_left_page(img, fonts)
    draw_right_page(img, fonts)

    # centre gutter shadow + page edges
    d = ImageDraw.Draw(img)
    for i in range(12):
        a = 90 - i * 7
        d.line([(506 - i, 18), (506 - i, 702)], fill=(10, 16, 22, a), width=1)
        d.line([(518 + i, 18), (518 + i, 702)], fill=(10, 16, 22, a), width=1)
    d.rectangle([24, 18, 500, 702], outline=(140, 150, 158), width=1)
    d.rectangle([524, 18, 1000, 702], outline=(140, 150, 158), width=1)
    return img.convert("RGB")


def main():
    try:
        img = render()
    except Exception:
        # stdlib-only sandbox: no Pillow or no fonts - ship the bundled image.
        if not os.path.exists(FALLBACK):
            raise
        os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
        shutil.copyfile(FALLBACK, OUT)
        return
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    img.save(OUT, format="PNG", optimize=True)


if __name__ == "__main__":
    main()
