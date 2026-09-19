"""Share card renderer: geometry, layout guarantees, determinism, privacy."""

import inspect
import io
import time
from pathlib import Path

import pytest
from PIL import Image, ImageChops

import cards.render as render
from cards.render import (
    CARD_HEIGHT,
    CARD_WIDTH,
    MESSAGE_MAX_FONT,
    MESSAGE_MIN_FONT,
    PANEL,
    TEMPLATE_VERSION,
    render_share_card,
)

LONG_UZ_200 = (
    "Bilasanmi, men senga aytmoqchi bo'lgan gaplarim juda ko'p edi, lekin hech qachon jur'at qilolmadim. "
    "Sen bilan tanishganimdan beri hayotim o'zgardi. Rahmat senga, doim shunday qol! "
    "Sen har doim yonimda eding va men buni hech qachon unutmayman."
)[:200]

CASES = {
    "short_uz": "Bir savolim bor...",
    "medium_uz": "Sen haqingda juda yaxshi fikrdaman. Har doim omad tilayman!",
    "long_uz_200": LONG_UZ_200,
    "russian": "Ты очень классный человек, я всегда рад с тобой общаться. Спасибо, что ты рядом — это многое значит!",
    "punctuation": "«Sen — eng yaxshisisan!» — dedi u; “o‘zbek”, g‘alaba, o‘qituvchi… Rostmi? Ha: albatta, ‘shunday’!",
    "mixed_word_lengths": "Ha. Tushunmoqchi bo'lganim: extraordinarily uncharacteristically internationalization — ya'ni, gaplashaylik!",
    "multiline": "Salom!\n\nBugun seni ko'rdim.\nJuda xursand bo'ldim.",
    "with_emoji": "Sen juda zo'rsan 🔥🔥 Har doim kulib yur 😊❤️",
}


def _decode(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGB")


def _ink_bbox(png: bytes):
    """Bounding box of bright text ink (the soft cyan halo is far below this threshold)."""
    diff = ImageChops.difference(_decode(png), render._get_static_layer()).convert("L")
    return diff.point(lambda v: 255 if v > 70 else 0).getbbox()


# --- Output format -----------------------------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_output_is_png_exactly_1080_square(name):
    png = render_share_card(CASES[name])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert _decode(png).size == (1080, 1080) == (CARD_WIDTH, CARD_HEIGHT)


def test_empty_and_whitespace_messages_still_render_a_valid_card():
    for body in ("", "   ", "\n\n", None):
        assert _decode(render_share_card(body)).size == (1080, 1080)


# --- Privacy: the signature is the guarantee ----------------------------------

def test_signature_takes_only_the_message_body():
    assert list(inspect.signature(render_share_card).parameters) == ["message_body"]


def test_only_the_panel_changes_with_the_message():
    """Everything outside the glass panel (background, logo, wordmark) is
    byte-identical for any message — so nothing else (URL, metadata) can appear."""
    a = _decode(render_share_card("Birinchi xabar"))
    b = _decode(render_share_card("Совсем другое сообщение 🔥 " * 3))
    diff = ImageChops.difference(a, b).convert("L").point(lambda v: 255 if v else 0)
    x0, y0, x1, y1 = PANEL
    outside = diff.copy()
    outside.paste(0, (x0, y0, x1, y1))
    assert outside.getbbox() is None


def test_output_is_deterministic():
    for body in CASES.values():
        assert render_share_card(body) == render_share_card(body)


def test_template_version_is_declared():
    assert TEMPLATE_VERSION


# --- Layout: no clipping, readable, centred -------------------------------------

@pytest.mark.parametrize("name", CASES)
def test_text_stays_inside_the_glass_panel(name):
    x0, y0, x1, y1 = PANEL
    left, top, right, bottom = _ink_bbox(render_share_card(CASES[name]))
    margin = 40  # the panel radius/border must never be touched
    assert left >= x0 + margin and right <= x1 - margin
    assert top >= y0 + margin and bottom <= y1 - margin


@pytest.mark.parametrize("name", ["short_uz", "medium_uz", "long_uz_200", "russian", "multiline"])
def test_message_is_optically_centred_in_the_panel(name):
    x0, y0, x1, y1 = PANEL
    left, top, right, bottom = _ink_bbox(render_share_card(CASES[name]))
    assert abs((top + bottom) / 2 - (y0 + y1) / 2) <= 22
    assert abs((left + right) / 2 - (x0 + x1) / 2) <= 12


def test_short_message_uses_the_largest_size_and_one_line():
    size, lines = render._fit(render._sanitize("Rahmat!"))
    assert size == MESSAGE_MAX_FONT and lines == ["Rahmat!"]


def test_200_character_message_stays_comfortably_readable():
    assert len(LONG_UZ_200) == 200
    size, lines = render._fit(render._sanitize(LONG_UZ_200))
    assert size >= 34  # well above the hard floor: no unreadable shrinking
    assert " ".join(lines).replace("  ", " ") == LONG_UZ_200
    for line in lines:
        assert render._measure(line, size) <= render._INNER_W + 1


def test_size_decreases_gradually_with_length():
    sizes = [render._fit(render._sanitize("So'z " * n))[0] for n in (2, 12, 25, 39)]
    assert sizes == sorted(sizes, reverse=True) and sizes[0] > sizes[-1] >= MESSAGE_MIN_FONT


def test_wrapped_lines_are_balanced_not_ragged():
    _, lines = render._fit(render._sanitize(CASES["medium_uz"]))
    widths = [render._measure(line, MESSAGE_MAX_FONT) for line in lines]
    assert len(lines) >= 2 and min(widths) > 0.45 * max(widths)  # no lone tiny last word


def test_explicit_line_breaks_are_kept():
    _, lines = render._fit(render._sanitize(CASES["multiline"]))
    assert lines[0] == "Salom!" and "" in lines and lines[-1] == "Juda xursand bo'ldim."


def test_over_limit_message_is_shortened_never_clipped():
    body = "Uzun matn " * 80  # 800 chars, far beyond the 200-char design limit
    x0, y0, x1, y1 = PANEL
    png = render_share_card(body)
    left, top, right, bottom = _ink_bbox(png)
    assert top >= y0 + 40 and bottom <= y1 - 40 and left >= x0 + 40 and right <= x1 - 40
    _, lines = render._fit(render._sanitize(body))
    assert lines[-1].endswith("…")


def test_unbroken_giant_token_is_split_not_overflowed():
    x0, y0, x1, y1 = PANEL
    left, _, right, _ = _ink_bbox(render_share_card("A" * 190))
    assert left >= x0 + 40 and right <= x1 - 40


# --- Text support ------------------------------------------------------------------

def test_cyrillic_and_uzbek_use_real_glyphs_not_tofu():
    font = render._font(40, 400)
    notdef = render._notdef_mask()  # Inter's own missing-glyph box
    for ch in "ШОЖўқғ" + "ʻʼ‘’“”«»…—":
        assert bytes(font.getmask(ch)) != notdef, f"missing glyph for {ch!r}"
    assert bytes(font.getmask("Ш")) != bytes(font.getmask("О"))


def test_sanitize_keeps_uzbek_and_russian_text_intact():
    for text in (CASES["punctuation"], CASES["russian"], "o‘zbek g‘oya Ўзбек Қиз"):
        assert render._sanitize(text) == text


def test_sanitize_drops_control_and_unsupported_characters_without_crashing():
    cleaned = render._sanitize("Salom\x00\x07 ​dunyo 你好 ok")
    assert cleaned == "Salom dunyo ok"


def test_bundled_emoji_font_is_present_and_is_the_one_loaded():
    path = render._EMOJI_FONT_PATH
    assert path == Path(render.__file__).parent / "fonts" / "NotoColorEmoji.ttf"
    assert path.is_file() and path.stat().st_size > 1_000_000
    assert (path.parent / "OFL-NotoColorEmoji.txt").is_file()  # licence ships with the font
    font = render._emoji_font()
    assert font is not None and Path(font.path) == path


def test_emoji_font_is_never_downloaded_or_taken_from_the_system():
    source = inspect.getsource(render)
    assert "/usr/share" not in source and "/System/" not in source
    for network_module in ("urllib", "requests", "httpx", "http.client", "socket", "aiohttp"):
        assert network_module not in source


def test_emoji_are_rendered_in_color_from_the_bundled_font():
    assert render._sanitize("a 👀 b") == "a 👀 b"
    left, top, right, bottom = _ink_bbox(render_share_card("👀"))
    assert right > left and bottom > top
    region = _decode(render_share_card("👀")).crop((left, top, right, bottom))
    assert any(abs(r - b) > 40 for r, _, b in region.get_flattened_data())  # coloured, not monochrome


@pytest.mark.parametrize("cluster", ["🔥", "😊", "❤️", "👍🏽", "👨‍👩‍👧", "🇺🇿", "✨", "🙏"])
def test_common_emoji_clusters_render_from_the_bundle(cluster):
    assert render._emoji_bitmap(cluster) is not None
    assert render._sanitize(f"a {cluster} b") == f"a {cluster} b"
    assert _ink_bbox(render_share_card(cluster)) is not None


def _without_emoji_font(monkeypatch):
    monkeypatch.setattr(render, "_EMOJI_FONT_PATH", Path("/nonexistent/NotoColorEmoji.ttf"))
    render._emoji_font.cache_clear()
    render._emoji_bitmap.cache_clear()


def test_missing_bundle_falls_back_to_dropping_emoji_never_boxes(monkeypatch):
    _without_emoji_font(monkeypatch)
    try:
        assert render._emoji_font() is None
        assert render._sanitize("Sen zo'rsan 👀🔥 rostdan") == "Sen zo'rsan rostdan"
        assert _decode(render_share_card("👀🔥")).size == (1080, 1080)
        assert _decode(render_share_card("Faqat matn 🔥")).size == (1080, 1080)
    finally:
        monkeypatch.undo()
        render._emoji_font.cache_clear()
        render._emoji_bitmap.cache_clear()
    assert render._emoji_font() is not None  # restored: later tests see the real bundle


# --- Performance ----------------------------------------------------------------

def test_warm_render_is_fast():
    render.warm_up()
    render_share_card(CASES["medium_uz"])
    start = time.perf_counter()
    for body in (CASES["short_uz"], CASES["medium_uz"], CASES["long_uz_200"]):
        render_share_card(body)
    per_card = (time.perf_counter() - start) / 3
    assert per_card < 1.0  # generous CI bound; typically ~0.13s
