"""Share Card Variant A — the quote card (master plan's SHARE CARD MASTER
DESIGN / §13). 1080x1920, brand gradient, centered message, wordmark + CTA.

Privacy: this function's signature is deliberately narrow — it accepts only the
message text and the CTA link, nothing sender-identifying, nothing timestamped.
There is no code path that could add sender metadata to a card later without
also changing this signature.
"""

import io
import re

from PIL import Image, ImageDraw, ImageFont

# Pillow's bundled default font has no emoji glyphs — rendering them produces
# visible "tofu" boxes, which reads as broken rather than premium. Strip
# pictographic ranges before drawing rather than shipping a color-emoji font.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U0000FE0F"
    "\U0000200D"
    "]+",
    flags=re.UNICODE,
)


def _strip_unsupported_glyphs(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()

CARD_WIDTH = 1080
CARD_HEIGHT = 1920

COLOR_GRADIENT_TOP = (91, 79, 232)  # brand indigo #5B4FE8
COLOR_GRADIENT_BOTTOM = (45, 212, 191)  # brand teal #2DD4BF
COLOR_TEXT = (255, 255, 255)
COLOR_WORDMARK = (255, 255, 255)

MAX_RENDERED_CHARS = 280  # beyond this, Variant A stops being the right fit (see spec)


def _vertical_gradient(width: int, height: int, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    base = Image.new("RGB", (width, height), top)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * ratio)
        g = int(top[1] + (bottom[1] - top[1]) * ratio)
        b = int(top[2] + (bottom[2] - top[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Older Pillow without the `size` kwarg on load_default().
        return ImageFont.load_default()


def _wrap_to_fit(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            width = draw.textlength(candidate, font=font)
            if width <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def render_variant_a(message_body: str, cta_link: str) -> bytes:
    """Renders the quote card and returns PNG bytes. Never raises on ordinary
    Unicode input (Uzbek Latin, Russian Cyrillic, emoji) — falls back to a safe
    truncation rather than crashing the send pipeline's success path."""
    text = _strip_unsupported_glyphs(message_body) or " "
    if len(text) > MAX_RENDERED_CHARS:
        text = text[: MAX_RENDERED_CHARS - 1].rstrip() + "…"

    image = _vertical_gradient(CARD_WIDTH, CARD_HEIGHT, COLOR_GRADIENT_TOP, COLOR_GRADIENT_BOTTOM)
    draw = ImageDraw.Draw(image)

    max_text_width = int(CARD_WIDTH * 0.8)
    min_font_size = 32
    font_size = 72
    font = _load_font(font_size)
    lines = _wrap_to_fit(draw, text, font, max_text_width)
    line_height = font_size * 1.3
    block_height = line_height * len(lines)

    while block_height > CARD_HEIGHT * 0.55 and font_size > min_font_size:
        font_size -= 4
        font = _load_font(font_size)
        lines = _wrap_to_fit(draw, text, font, max_text_width)
        line_height = font_size * 1.3
        block_height = line_height * len(lines)

    start_y = (CARD_HEIGHT - block_height) / 2

    for i, line in enumerate(lines):
        width = draw.textlength(line, font=font)
        x = (CARD_WIDTH - width) / 2
        y = start_y + i * line_height
        draw.text((x, y), line, font=font, fill=COLOR_TEXT)

    wordmark_font = _load_font(40)
    wordmark = "shivir"
    wm_width = draw.textlength(wordmark, font=wordmark_font)
    draw.text(
        ((CARD_WIDTH - wm_width) / 2, CARD_HEIGHT - 220),
        wordmark,
        font=wordmark_font,
        fill=COLOR_WORDMARK,
    )

    cta_font = _load_font(34)
    cta_text = "Menga anonim xabar yubor"
    cta_width = draw.textlength(cta_text, font=cta_font)
    draw.text(
        ((CARD_WIDTH - cta_width) / 2, CARD_HEIGHT - 160),
        cta_text,
        font=cta_font,
        fill=COLOR_WORDMARK,
    )

    link_font = _load_font(30)
    link_width = draw.textlength(cta_link, font=link_font)
    draw.text(
        ((CARD_WIDTH - link_width) / 2, CARD_HEIGHT - 110),
        cta_link,
        font=link_font,
        fill=COLOR_WORDMARK,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
