"""SHIVIR share card — 1080x1080 PNG: one glass panel holding the anonymous
message, the approved SHIVIR logo and wordmark beneath it.

Design (Arctic Cyan on deep navy): a message-independent *static layer* —
background glow, glass panel, border, logo, wordmark — is composed once per
process and cached; each request only lays out and draws the message text on
a copy of it. Pure Pillow, no network, no subprocesses, no randomness: the
same message always yields the same pixels (see TEMPLATE_VERSION).

Privacy: the public signature is `render_share_card(message_body)`. Nothing
sender- or recipient-identifying, no link, no timestamp can reach the image.
"""

import functools
import io
import re
import threading
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Bump when the visual design changes — part of any cache key that stores cards.
TEMPLATE_VERSION = "arctic-glass-v1"

CARD_WIDTH = 1080
CARD_HEIGHT = 1080

_ROOT = Path(__file__).parent
_INTER_PATH = _ROOT / "fonts" / "InterVariable.ttf"          # OFL, see fonts/OFL-Inter.txt
_LOGO_PATH = _ROOT.parent / "web" / "static" / "images" / "shivir-logo.png"  # the approved logo, unmodified
# Bundled color emoji font (OFL, see fonts/OFL-NotoColorEmoji.txt). Loaded only
# from this local path: never downloaded, never looked up on the host system,
# so output is identical on every machine.
_EMOJI_FONT_PATH = _ROOT / "fonts" / "NotoColorEmoji.ttf"
_EMOJI_STRIKE = 109  # CBDT color emoji only exist at this one bitmap size

# --- Brand palette ---------------------------------------------------------
CYAN_500 = (6, 182, 212)
CYAN_300 = (103, 232, 249)
CYAN_200 = (165, 243, 252)
INK_950 = (6, 20, 26)
INK_900 = (10, 32, 40)
GLASS_TINT = (6, 22, 38)          # deep navy body of the glass panel
TEXT = (248, 250, 252)
BLUE_ACCENT = (37, 124, 235)     # restrained cool accent, secondary to cyan

# --- Layout ------------------------------------------------------------------
PANEL = (130, 200, 950, 708)      # x0, y0, x1, y1  (820 x 508)
PANEL_RADIUS = 56
TEXT_PAD_X = 76
TEXT_PAD_Y = 62
LOGO_HEIGHT = 108
LOGO_TOP = 770
WORDMARK_SIZE = 40
WORDMARK_BASELINE = 952
WORDMARK_TRACKING = 4

MESSAGE_WEIGHT = 500
MESSAGE_MAX_FONT = 54
MESSAGE_MIN_FONT = 30
LINE_HEIGHT = 1.32
_CAP_HEIGHT = 0.727               # Inter cap height / em

_INNER_W = PANEL[2] - PANEL[0] - 2 * TEXT_PAD_X
_INNER_H = PANEL[3] - PANEL[1] - 2 * TEXT_PAD_Y

# Grapheme-ish emoji clusters: flags, and pictographs with optional VS16 /
# skin tone / ZWJ chains. Anything else is ordinary text.
_PICT = "[☀-➿⬀-⯿\U0001F300-\U0001FAFF]"
_MOD = "[️\U0001F3FB-\U0001F3FF]"
_EMOJI_RE = re.compile(rf"(?:[\U0001F1E6-\U0001F1FF]{{2}}|{_PICT}{_MOD}?(?:‍{_PICT}{_MOD}?)*)")
_STRIP_RE = re.compile("[​‌‍⁠﻿️\U0001F3FB-\U0001F3FF\x00-\x08\x0B-\x1F\x7F]")


# ============================================================================
# Fonts
# ============================================================================

@functools.lru_cache(maxsize=None)
def _font(size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(_INTER_PATH), size, layout_engine=ImageFont.Layout.RAQM)
    # Inter axes: optical size (14-32) then weight. Both must be set together.
    font.set_variation_by_axes([min(max(size, 14), 32), weight])
    return font


@functools.lru_cache(maxsize=1)
def _emoji_font() -> ImageFont.FreeTypeFont | None:
    """The bundled color emoji font, or None if it can't be loaded — in which
    case emoji are dropped from the text (see _sanitize) rather than drawn as boxes."""
    # Explicit is_file() check: ImageFont.truetype() silently falls back to
    # searching the host's system font directories by file name when a path
    # can't be opened, which would defeat "bundled only".
    if not _EMOJI_FONT_PATH.is_file():
        return None
    try:
        return ImageFont.truetype(str(_EMOJI_FONT_PATH), _EMOJI_STRIKE, layout_engine=ImageFont.Layout.RAQM)
    except OSError:
        return None


@functools.lru_cache(maxsize=512)
def _emoji_bitmap(cluster: str) -> Image.Image | None:
    """Color bitmap for one emoji cluster, or None if it can't be drawn."""
    font = _emoji_font()
    if font is None:
        return None
    try:
        width = int(font.getlength(cluster)) + 8
        canvas = Image.new("RGBA", (max(width, 8), _EMOJI_STRIKE + 32), (0, 0, 0, 0))
        ImageDraw.Draw(canvas).text((0, 0), cluster, font=font, embedded_color=True)
        box = canvas.getbbox()
        return canvas.crop(box) if box else None
    except (OSError, ValueError):
        return None


@functools.lru_cache(maxsize=1)
def _notdef_mask() -> bytes:
    # Inter has no CJK, so a CJK ideograph renders as Inter's own .notdef box —
    # the exact shape any unsupported character would otherwise be drawn as.
    return bytes(_font(40, 400).getmask("\u4e00"))


@functools.lru_cache(maxsize=4096)
def _has_glyph(char: str) -> bool:
    return char.isspace() or bytes(_font(40, 400).getmask(char)) != _notdef_mask()


# ============================================================================
# Text model: a line is a str; emoji clusters inside it are drawn as bitmaps
# ============================================================================

def _sanitize(text: str) -> str:
    """Normalise what will be drawn: drop control/zero-width junk, drop emoji
    that can't be rendered, drop characters Inter has no glyph for (nothing
    else could draw them either), collapse spaces."""
    out = []
    pos = 0
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for match in _EMOJI_RE.finditer(text):
        out.append(_sanitize_plain(text[pos:match.start()]))
        if _emoji_bitmap(match.group()) is not None:
            out.append(match.group())
        pos = match.end()
    out.append(_sanitize_plain(text[pos:]))
    cleaned = "".join(out)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" ?\n ?", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _sanitize_plain(text: str) -> str:
    text = _STRIP_RE.sub(lambda m: "\n" if m.group() == "\n" else "", text)
    return "".join(ch for ch in text if ch in "\n\t" or _has_glyph(ch))


def _split_runs(line: str) -> list[tuple[str, bool]]:
    runs, pos = [], 0
    for match in _EMOJI_RE.finditer(line):
        if match.start() > pos:
            runs.append((line[pos:match.start()], False))
        runs.append((match.group(), True))
        pos = match.end()
    if pos < len(line):
        runs.append((line[pos:], False))
    return runs


def _emoji_size(size: int, bitmap: Image.Image) -> tuple[int, int]:
    height = round(size * 1.02)
    return max(1, round(bitmap.width * height / bitmap.height)), height


@functools.lru_cache(maxsize=65536)
def _measure(line: str, size: int, weight: int = MESSAGE_WEIGHT) -> float:
    font = _font(size, weight)
    total = 0.0
    for text, is_emoji in _split_runs(line):
        if is_emoji:
            width, _ = _emoji_size(size, _emoji_bitmap(text))
            total += width + size * 0.08
        else:
            total += font.getlength(text)
    return total


def _atoms(word: str) -> list[str]:
    """Split a word into characters, keeping each emoji cluster whole."""
    atoms, pos = [], 0
    for match in _EMOJI_RE.finditer(word):
        atoms.extend(word[pos:match.start()])
        atoms.append(match.group())
        pos = match.end()
    atoms.extend(word[pos:])
    return atoms


def _break_long_word(word: str, size: int, max_w: float) -> list[str]:
    """A single token wider than the panel is broken between characters."""
    pieces, current = [], ""
    for atom in _atoms(word):
        if current and _measure(current + atom, size) > max_w:
            pieces.append(current)
            current = atom
        else:
            current += atom
    if current:
        pieces.append(current)
    return pieces


def _greedy(words: list[str], size: int, max_w: float) -> list[str]:
    space = _measure(" ", size)
    lines, current, width = [], "", 0.0
    for word in words:
        w = _measure(word, size)
        if current and width + space + w > max_w:
            lines.append(current)
            current, width = word, w
        elif current:
            current, width = f"{current} {word}", width + space + w
        else:
            current, width = word, w
    if current:
        lines.append(current)
    return lines


def _wrap_paragraph(paragraph: str, size: int, max_w: float) -> list[str]:
    words = []
    for word in paragraph.split(" "):
        if word:
            words.extend(_break_long_word(word, size, max_w) if _measure(word, size) > max_w else [word])
    if not words:
        return [""]
    lines = _greedy(words, size, max_w)
    if len(lines) == 1:
        return lines
    # Balanced wrap: keep the greedy line count, but find the narrowest width
    # that still gives that count — even line lengths, no lone last word.
    lo = int(max(_measure(w, size) for w in words))
    hi = int(max_w)
    while lo < hi:
        mid = (lo + hi) // 2
        if len(_greedy(words, size, mid)) <= len(lines):
            hi = mid
        else:
            lo = mid + 1
    return _greedy(words, size, hi)


def _wrap(text: str, size: int, max_w: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(_wrap_paragraph(paragraph, size, max_w))
    return lines


def _line_pitch(size: int) -> int:
    return round(size * LINE_HEIGHT)


def _ink_height(n_lines: int, size: int) -> float:
    """Cap-top of the first line to just below the last baseline."""
    return (n_lines - 1) * _line_pitch(size) + size * (_CAP_HEIGHT + 0.10)


def _fit(text: str) -> tuple[int, list[str]]:
    """Largest font size (MESSAGE_MAX..MIN) at which the balanced-wrapped text
    fits the panel. If even the minimum doesn't (only possible above the
    200-character design limit), shorten the text with an ellipsis rather
    than clip or shrink further."""
    working = text
    for _ in range(40):
        for size in range(MESSAGE_MAX_FONT, MESSAGE_MIN_FONT - 1, -2):
            lines = _wrap(working, size, _INNER_W)
            if _ink_height(len(lines), size) <= _INNER_H:
                return size, lines
        working = working[: max(1, int(len(working) * 0.9))].rstrip() + "…"
    return MESSAGE_MIN_FONT, ["…"]


# ============================================================================
# Static layer (background, glass panel, logo, wordmark) — built once
# ============================================================================

def _radial(diameter: int, color: tuple[int, int, int], alpha: int, power: float = 2.0) -> tuple[Image.Image, Image.Image]:
    # radial_gradient() is normalised to the corner: at the edge midpoints it only
    # reaches 181/255. Normalise to the true radius so every glow fades to zero
    # *inside* its box (otherwise it leaves hard rectangular edges).
    ramp = Image.radial_gradient("L").point(lambda v: int(alpha * max(0.0, 1 - v / 180) ** power))
    return Image.new("RGB", (diameter, diameter), color), ramp.resize((diameter, diameter), Image.BICUBIC)


def _add_glow(base: Image.Image, center: tuple[int, int], diameter: int, color, alpha: int, power: float = 2.0) -> None:
    layer, mask = _radial(diameter, color, alpha, power)
    base.paste(layer, (center[0] - diameter // 2, center[1] - diameter // 2), mask)


def _arc_light(base: Image.Image, center: tuple[int, int], radius: int, color) -> None:
    """A soft luminous ribbon curving in from a corner — the only decoration."""
    mask = Image.new("L", base.size, 0)
    box = (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius)
    ImageDraw.Draw(mask).ellipse(box, outline=255, width=9)
    line = mask.filter(ImageFilter.GaussianBlur(2.5)).point(lambda v: int(v * 0.55))
    halo = mask.filter(ImageFilter.GaussianBlur(34)).point(lambda v: min(255, int(v * 1.5)))
    base.paste(Image.new("RGB", base.size, color), (0, 0), halo.point(lambda v: int(v * 0.55)))
    base.paste(Image.new("RGB", base.size, CYAN_300), (0, 0), line)


def _rounded_mask(size: tuple[int, int], radius: int, scale: int = 3) -> Image.Image:
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(big).rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * scale, fill=255)
    return big.resize(size, Image.LANCZOS)


def _ring_mask(size: tuple[int, int], radius: int, width: int, scale: int = 3) -> Image.Image:
    big = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, big.width - 1, big.height - 1), radius * scale, fill=255)
    inset = width * scale
    d.rounded_rectangle((inset, inset, big.width - 1 - inset, big.height - 1 - inset), max(1, (radius - width) * scale), fill=0)
    return big.resize(size, Image.LANCZOS)


def _vertical_gradient(size: tuple[int, int], top, bottom) -> Image.Image:
    strip = Image.linear_gradient("L").resize(size, Image.BILINEAR)  # 0 at top -> 255 at bottom
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), strip)


def _build_background() -> Image.Image:
    base = _vertical_gradient((CARD_WIDTH, CARD_HEIGHT), (5, 18, 26), (4, 13, 27))
    _add_glow(base, (CARD_WIDTH // 2, 470), 1500, (10, 62, 88), 120, 1.7)       # calm haze behind the panel
    _add_glow(base, (40, 30), 1250, CYAN_500, 110, 2.0)                           # top-left
    _add_glow(base, (1050, 1060), 1250, BLUE_ACCENT, 100, 2.0)                     # bottom-right
    _arc_light(base, (-20, -120), 500, CYAN_500)
    _arc_light(base, (1100, 1210), 520, BLUE_ACCENT)
    return base


def _build_static_layer() -> Image.Image:
    base = _build_background()
    x0, y0, x1, y1 = PANEL
    size = (x1 - x0, y1 - y0)
    mask = _rounded_mask(size, PANEL_RADIUS)

    # Outer edge glow (soft, cyan) — painted before the panel so the panel body covers its inside.
    ring = Image.new("L", base.size, 0)
    ring.paste(_ring_mask(size, PANEL_RADIUS, 5), (x0, y0))
    for blur, strength in ((22, 0.62), (64, 0.32)):
        halo = ring.filter(ImageFilter.GaussianBlur(blur)).point(lambda v, s=strength: min(255, int(v * s * 3.2)))
        base.paste(Image.new("RGB", base.size, CYAN_500), (0, 0), halo)

    # Glass body: blurred backdrop, dark tint, faint top light and edge light.
    body = base.crop(PANEL).filter(ImageFilter.GaussianBlur(20))
    body = Image.blend(body, Image.new("RGB", size, GLASS_TINT), 0.60)
    body.paste(Image.new("RGB", size, CYAN_200), (0, 0), _vertical_gradient(size, (16, 16, 16), (0, 0, 0)).convert("L"))
    for cx, cy, diameter, color, alpha in (
        (size[0], size[1] // 2, 460, (30, 140, 235), 90),   # right edge light
        (0, size[1] - 40, 380, CYAN_500, 60),               # lower-left edge light
        (size[0] // 2, 0, 520, CYAN_300, 34),               # top sheen
    ):
        layer, m = _radial(diameter, color, alpha, 2.0)
        body.paste(layer, (cx - diameter // 2, cy - diameter // 2), m)
    base.paste(body, (x0, y0), mask)

    # Thin border: brighter at the top, softer at the bottom, plus a 1px inner highlight.
    border = _vertical_gradient(size, (170, 246, 255), (60, 175, 220))
    base.paste(border, (x0, y0), _ring_mask(size, PANEL_RADIUS, 2))
    inner = _ring_mask((size[0] - 8, size[1] - 8), PANEL_RADIUS - 4, 1).point(lambda v: int(v * 0.16))
    base.paste(Image.new("RGB", inner.size, (255, 255, 255)), (x0 + 4, y0 + 4), inner)

    # Logo — the approved asset, scaled proportionally (premultiplied, so no dark fringes).
    logo = Image.open(_LOGO_PATH).convert("RGBA")
    logo_w = round(logo.width * LOGO_HEIGHT / logo.height)
    logo = logo.convert("RGBa").resize((logo_w, LOGO_HEIGHT), Image.LANCZOS).convert("RGBA")
    base.paste(logo, ((CARD_WIDTH - logo_w) // 2, LOGO_TOP), logo)

    # Wordmark: SHIVIR, bold, light tracking, centred under the logo.
    draw = ImageDraw.Draw(base)
    font = _font(WORDMARK_SIZE, 700)
    word = "SHIVIR"
    widths = [font.getlength(ch) for ch in word]
    total = sum(widths) + WORDMARK_TRACKING * (len(word) - 1)
    x = (CARD_WIDTH - total) / 2
    for ch, w in zip(word, widths):
        draw.text((x, WORDMARK_BASELINE), ch, font=font, fill=TEXT, anchor="ls")
        x += w + WORDMARK_TRACKING
    return base


_static_lock = threading.Lock()
_static_layer: Image.Image | None = None


def _get_static_layer() -> Image.Image:
    global _static_layer
    if _static_layer is None:
        with _static_lock:
            if _static_layer is None:
                _static_layer = _build_static_layer()
    return _static_layer


def warm_up() -> None:
    """Build the cached static layer and load fonts now, off the request path."""
    _get_static_layer()
    _fit("Shivir")


# ============================================================================
# Message drawing
# ============================================================================

def _draw_line(
    image: Image.Image | None, draw: ImageDraw.ImageDraw, line: str, size: int, baseline: float, fill,
    origin: tuple[int, int] = (0, 0),
) -> None:
    """Draw one centred line. `origin` shifts into a sub-canvas (the halo layer)."""
    font = _font(size, MESSAGE_WEIGHT)
    x = (CARD_WIDTH - _measure(line, size)) / 2 - origin[0]
    baseline -= origin[1]
    for text, is_emoji in _split_runs(line):
        if is_emoji:
            bitmap = _emoji_bitmap(text)
            width, height = _emoji_size(size, bitmap)
            if image is not None:
                sprite = bitmap.convert("RGBa").resize((width, height), Image.LANCZOS).convert("RGBA")
                image.paste(sprite, (round(x + size * 0.04), round(baseline - height * 0.86)), sprite)
            x += width + size * 0.08
        else:
            draw.text((x, baseline), text, font=font, fill=fill, anchor="ls")
            x += font.getlength(text)


def render_share_card(message_body: str) -> bytes:
    """Render the share card for one anonymous message and return PNG bytes.

    Never raises for ordinary Unicode input; an empty/unrenderable message
    produces a valid card with an empty panel. Text never leaves the panel:
    the font shrinks (down to MESSAGE_MIN_FONT) and only then is the message
    shortened with an ellipsis."""
    text = _sanitize(message_body or "")
    size, lines = _fit(text) if text else (MESSAGE_MAX_FONT, [])

    image = _get_static_layer().copy()
    if lines:
        pitch = _line_pitch(size)
        panel_cy = (PANEL[1] + PANEL[3]) / 2
        first_baseline = panel_cy - _ink_height(len(lines), size) / 2 + size * _CAP_HEIGHT

        # Soft cyan halo behind the letters, then the crisp text on top.
        halo = Image.new("L", (PANEL[2] - PANEL[0], PANEL[3] - PANEL[1]), 0)
        halo_draw = ImageDraw.Draw(halo)
        for i, line in enumerate(lines):
            _draw_line(None, halo_draw, line, size, first_baseline + i * pitch, 255, origin=PANEL[:2])
        halo = halo.filter(ImageFilter.GaussianBlur(9)).point(lambda v: int(v * 0.30))
        image.paste(Image.new("RGB", halo.size, CYAN_500), PANEL[:2], halo)

        draw = ImageDraw.Draw(image)
        for i, line in enumerate(lines):
            _draw_line(image, draw, line, size, first_baseline + i * pitch, TEXT)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=3)
    return buffer.getvalue()
