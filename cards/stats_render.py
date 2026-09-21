"""Admin statistics card — 1080x1350 PNG for the /stats report.

Reuses the share card's palette, fonts and background helpers. Input is the
aggregate `Stats` only, so nothing personal (ids, names, message text,
fingerprints, IPs) can reach the image. Uzbek only.
"""

import io

from PIL import Image, ImageDraw, ImageFilter

from cards import render as r
from core.services.stats import Stats, date_label, fmt, summary_uz

W, H = 1080, 1350
MARGIN = 72
MUTED = (150, 190, 205)


def _background() -> Image.Image:
    base = r._vertical_gradient((W, H), (5, 18, 26), (4, 13, 27))
    r._add_glow(base, (W // 2, 620), 1700, (10, 62, 88), 120, 1.7)
    r._add_glow(base, (40, 30), 1250, r.CYAN_500, 105, 2.0)
    r._add_glow(base, (1050, 1330), 1250, r.BLUE_ACCENT, 95, 2.0)
    return base


def _glass(base: Image.Image, box: tuple[int, int, int, int], radius: int = 36) -> None:
    x0, y0, x1, y1 = box
    size = (x1 - x0, y1 - y0)
    body = base.crop(box).filter(ImageFilter.GaussianBlur(14))
    body = Image.blend(body, Image.new("RGB", size, r.GLASS_TINT), 0.66)
    base.paste(body, (x0, y0), r._rounded_mask(size, radius))
    border = r._vertical_gradient(size, (120, 226, 245), (40, 130, 180))
    base.paste(border, (x0, y0), r._ring_mask(size, radius, 2))


def _text(draw, xy, text, size, weight, fill, anchor="ls") -> None:
    draw.text(xy, text, font=r._font(size, weight), fill=fill, anchor=anchor)


def _wrap(text: str, size: int, weight: int, max_w: int) -> list[str]:
    font = r._font(size, weight)
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and font.getlength(trial) > max_w:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + ([line] if line else [])


def render_stats_card(s: Stats) -> bytes:
    img = _background()
    draw = ImageDraw.Draw(img)

    # Header: wordmark, title, date.
    font = r._font(44, 700)
    x = MARGIN
    for ch in "SHIVIR":
        draw.text((x, 128), ch, font=font, fill=r.TEXT, anchor="ls")
        x += font.getlength(ch) + 5
    _text(draw, (MARGIN, 190), "KUNLIK HISOBOT", 30, 600, r.CYAN_300)
    _text(draw, (W - MARGIN, 190), date_label(s.today), 30, 500, MUTED, "rs")

    # Three KPI tiles.
    gap, top, tile_h = 24, 246, 232
    tile_w = (W - 2 * MARGIN - 2 * gap) // 3
    kpis = (("Faol userlar", s.active_1), ("Yangi userlar", s.new_users_1), ("Yangi xabarlar", s.messages_1))
    for i, (label, value) in enumerate(kpis):
        x0 = MARGIN + i * (tile_w + gap)
        _glass(img, (x0, top, x0 + tile_w, top + tile_h))
        draw = ImageDraw.Draw(img)
        text = fmt(value)
        size = 84
        while r._font(size, 700).getlength(text) > tile_w - 40 and size > 36:
            size -= 4
        _text(draw, (x0 + tile_w / 2, top + 132), text, size, 700, r.TEXT, "ms")
        _text(draw, (x0 + tile_w / 2, top + 190), label, 26, 500, r.CYAN_200, "ms")

    # Table: Ko‘rsatkich | Bugun | 7 kun | 30 kun
    t_top, row_h = 508, 84
    t_box = (MARGIN, t_top, W - MARGIN, t_top + 5 * row_h - 20)
    _glass(img, t_box)
    draw = ImageDraw.Draw(img)
    cols = (MARGIN + 44, 640, 800, W - MARGIN - 44)  # label (left), then three right-aligned numbers
    heads = ("Ko‘rsatkich", "Bugun", "7 kun", "30 kun")
    rows = (
        ("Faol userlar", s.active_1, s.active_7, s.active_30),
        ("Yangi userlar", s.new_users_1, s.new_users_7, s.new_users_30),
        ("Xabarlar", s.messages_1, s.messages_7, s.messages_30),
    )
    y = t_top + 62
    _text(draw, (cols[0], y), heads[0], 26, 600, r.CYAN_300)
    for cx, head in zip(cols[1:], heads[1:]):
        _text(draw, (cx, y), head, 26, 600, r.CYAN_300, "rs")
    draw.line((cols[0], y + 22, cols[3], y + 22), fill=(40, 90, 115), width=2)
    for label, *vals in rows:
        y += row_h
        _text(draw, (cols[0], y), label, 32, 500, r.TEXT)
        for cx, v in zip(cols[1:], vals):
            _text(draw, (cx, y), fmt(v), 34, 700, r.TEXT, "rs")

    # Summary.
    b_top = t_box[3] + 36
    b_box = (MARGIN, b_top, W - MARGIN, 1236)
    _glass(img, b_box)
    draw = ImageDraw.Draw(img)
    _text(draw, (MARGIN + 44, b_top + 66), "BUGUNGI XULOSA", 26, 700, r.CYAN_300)
    for i, line in enumerate(_wrap(summary_uz(s), 32, 500, W - 2 * MARGIN - 88)[:5]):
        _text(draw, (MARGIN + 44, b_top + 122 + i * 46), line, 32, 500, r.TEXT)

    _text(draw, (W // 2, 1290), "SHIVIR • ichki hisobot", 22, 500, MUTED, "ms")

    buf = io.BytesIO()
    img.save(buf, format="PNG", compress_level=3)
    return buf.getvalue()
