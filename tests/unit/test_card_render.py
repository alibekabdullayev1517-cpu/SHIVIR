import io

from PIL import Image

from cards.render import CARD_HEIGHT, CARD_WIDTH, render_variant_a


def _decode(png_bytes: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png_bytes))


def test_renders_correct_dimensions():
    png = render_variant_a("Sen ajoyibsan!", "shivir.example/abc123")
    image = _decode(png)
    assert image.size == (CARD_WIDTH, CARD_HEIGHT)


def test_renders_uzbek_text_with_diacritics():
    png = render_variant_a("Ishlaring qalay? O'zingga yaxshi qara 👀", "shivir.example/xyz")
    assert _decode(png).size == (CARD_WIDTH, CARD_HEIGHT)


def test_renders_russian_cyrillic_text():
    png = render_variant_a("Ты очень крутой человек, продолжай в том же духе!", "shivir.example/ru1")
    assert _decode(png).size == (CARD_WIDTH, CARD_HEIGHT)


def test_renders_long_message_via_truncation():
    long_text = "A" * 1000
    png = render_variant_a(long_text, "shivir.example/long")
    assert _decode(png).size == (CARD_WIDTH, CARD_HEIGHT)


def test_renders_empty_message_without_crashing():
    png = render_variant_a("   ", "shivir.example/empty")
    assert _decode(png).size == (CARD_WIDTH, CARD_HEIGHT)


def test_no_sender_metadata_param_exists():
    """The function signature itself is the privacy guarantee: there is no
    parameter through which sender-identifying data could be injected."""
    import inspect

    params = set(inspect.signature(render_variant_a).parameters.keys())
    assert params == {"message_body", "cta_link"}
