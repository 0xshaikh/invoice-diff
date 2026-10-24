"""Generate favicon.ico and og-image.png for invoice-diff docs."""

import os

from PIL import Image, ImageDraw, ImageFont

OUT = os.path.dirname(os.path.abspath(__file__))


# ---------- fonts ----------
def load_font(size, bold=False):
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for p in paths:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# ---------- colors ----------
BG = (10, 13, 20)  # #0a0d14
FG = (238, 242, 247)  # #eef2f7
ACCENT = (255, 107, 53)  # #FF6B35
MUTED = (139, 148, 165)  # #8b94a5
PANEL = (18, 22, 32)
BORDER = (44, 52, 70)

# ---------- favicon 64x64 ----------
S = 64
fav = Image.new("RGBA", (S, S), BG)
d = ImageDraw.Draw(fav)
# rounded square
r = 14
d.rounded_rectangle([0, 0, S - 1, S - 1], radius=r, fill=BG, outline=ACCENT, width=3)
# orange diff arrow → as a stylized "i" mark
# vertical bar
d.rounded_rectangle([22, 16, 30, 48], radius=4, fill=ACCENT)
# top dot
d.ellipse([23, 10, 29, 16], fill=ACCENT)
# arrow head (bottom-right chevron)
d.polygon([(24, 44), (36, 50), (24, 56)], fill=ACCENT)
fav.save(os.path.join(OUT, "favicon.png"))
# multi-size ICO
imgs = []
for size in (16, 24, 32, 48, 64):
    imgs.append(fav.resize((size, size), Image.LANCZOS))
fav.save(os.path.join(OUT, "favicon.ico"), sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)])

# ---------- og-image 1200x630 ----------
W, H = 1200, 630
og = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(og)

# subtle accent bar on left
d.rectangle([0, 0, 8, H], fill=ACCENT)


# logo mark top-left
def draw_mark(x, y, scale=1.0):
    s = int(40 * scale)
    rr = int(8 * scale)
    d.rounded_rectangle(
        [x, y, x + s, y + s], radius=rr, fill=None, outline=ACCENT, width=max(2, int(2 * scale))
    )
    bx = int(14 * scale)
    bw = int(6 * scale)
    d.rounded_rectangle(
        [x + bx, y + int(9 * scale), x + bx + bw, y + int(31 * scale)],
        radius=int(3 * scale),
        fill=ACCENT,
    )
    d.ellipse(
        [x + bx + int(1 * scale), y + int(5 * scale), x + bx + int(5 * scale), y + int(9 * scale)],
        fill=ACCENT,
    )
    d.polygon(
        [
            (x + bx + int(1 * scale), y + int(29 * scale)),
            (x + bx + int(11 * scale), y + int(34 * scale)),
            (x + bx + int(1 * scale), y + int(39 * scale)),
        ],
        fill=ACCENT,
    )


draw_mark(70, 60, 1.6)

title_font = load_font(78, bold=True)
subtitle_font = load_font(30, bold=True)
label_font = load_font(22, bold=True)
body_font = load_font(26)
kpi_num_font = load_font(64, bold=True)
kpi_lbl_font = load_font(20)
footer_font = load_font(20)

d.text((160, 68), "invoice-diff", font=title_font, fill=FG)
d.text((164, 158), "Reconcile marketplace invoices in 10 seconds.", font=subtitle_font, fill=ACCENT)

d.text((70, 220), "Flipkart  ·  Meesho  ·  Amazon.in", font=label_font, fill=MUTED)

# divider
d.line([(70, 270), (W - 70, 270)], fill=BORDER, width=2)

# KPI cards
cards = [
    ("100", "orders reconciled"),
    ("5", "discrepancies caught"),
    ("Rs.2,340", "total impact"),
    ("10s", "total runtime"),
]
card_w = 250
gap = 26
start_x = 70
y0 = 320
for i, (num, lbl) in enumerate(cards):
    cx = start_x + i * (card_w + gap)
    d.rounded_rectangle(
        [cx, y0, cx + card_w, y0 + 180], radius=14, fill=PANEL, outline=BORDER, width=2
    )
    d.text((cx + 24, y0 + 24), num, font=kpi_num_font, fill=ACCENT)
    # wrap label
    words = lbl.split()
    line = ""
    ly = y0 + 104
    for w in words:
        t = (line + " " + w).strip()
        if d.textlength(t, font=kpi_lbl_font) > card_w - 48:
            d.text((cx + 24, ly), line, font=kpi_lbl_font, fill=FG)
            ly += 28
            line = w
        else:
            line = t
    if line:
        d.text((cx + 24, ly), line, font=kpi_lbl_font, fill=FG)

# footer
d.line([(70, H - 70), (W - 70, H - 70)], fill=BORDER, width=1)
d.text(
    (70, H - 52), "MIT License  ·  github.com/0xshaikh/invoice-diff", font=footer_font, fill=MUTED
)
d.text(
    (W - 70 - d.textlength("python  ·  CLI  ·  no config", font=footer_font), H - 52),
    "python  ·  CLI  ·  no config",
    font=footer_font,
    fill=MUTED,
)

og.save(os.path.join(OUT, "og-image.png"))
print("done")
print("favicon.ico", os.path.getsize(os.path.join(OUT, "favicon.ico")))
print("favicon.png", os.path.getsize(os.path.join(OUT, "favicon.png")))
print("og-image.png", os.path.getsize(os.path.join(OUT, "og-image.png")))
