"""Markdown → Telegram HTML conversion, and the end-to-end path through the bot.

The design constraint driving this module: there is no validation step and no way for the
author to produce a message Telegram rejects. Every test here is really checking one of two
things — that recognised syntax renders, or that everything else survives untouched.
"""

from app.bot.markup import to_plain, to_telegram_html


def test_plain_text_is_only_escaped():
    assert to_telegram_html("Ismingiz nima?") == "Ismingiz nima?"


def test_html_special_characters_are_escaped():
    assert to_telegram_html("5 < 10 & 10 > 5") == "5 &lt; 10 &amp; 10 &gt; 5"


def test_bold():
    assert to_telegram_html("**Ismingiz**") == "<b>Ismingiz</b>"


def test_italic():
    assert to_telegram_html("_Iltimos_") == "<i>Iltimos</i>"


def test_underline():
    assert to_telegram_html("__Diqqat__") == "<u>Diqqat</u>"


def test_strikethrough():
    assert to_telegram_html("~~eski~~") == "<s>eski</s>"


def test_inline_code():
    assert to_telegram_html("`+998901234567`") == "<code>+998901234567</code>"


def test_code_block():
    assert to_telegram_html("```\nline one\nline two\n```") == "<pre>line one\nline two</pre>"


def test_link():
    out = to_telegram_html("[Oferta](https://telegra.ph/oferta)")
    assert out == '<a href="https://telegra.ph/oferta">Oferta</a>'


def test_link_with_parentheses_in_the_url_is_not_truncated():
    out = to_telegram_html("[Wiki](https://ru.wikipedia.org/wiki/A_(disambiguation))")
    assert out == (
        '<a href="https://ru.wikipedia.org/wiki/A_(disambiguation)">Wiki</a>'
    )


def test_multiple_markers_combine():
    out = to_telegram_html("**Ism** va _familiya_")
    assert out == "<b>Ism</b> va <i>familiya</i>"


def test_newlines_are_preserved():
    out = to_telegram_html("Birinchi qator\nIkkinchi qator")
    assert out == "Birinchi qator\nIkkinchi qator"


# --------------------------------------------------------------------------- "just works"
# The core promise: nothing a simple user types can produce broken output. No exceptions,
# no rejected questions, no explaining escaping rules to an HR who just wants to ask about
# a salary number.


def test_sentence_with_a_decimal_number_and_bang():
    # In MarkdownV2 this would need four characters escaped by hand; here it just works.
    assert to_telegram_html("Зарплата 3.000.000 сум!") == "Зарплата 3.000.000 сум!"


def test_percent_sign_and_dash():
    assert to_telegram_html("Скидка 50% — выгодно!") == "Скидка 50% — выгодно!"


def test_lone_asterisk_is_left_alone():
    assert to_telegram_html("Оцените от 1 до 5 *") == "Оцените от 1 до 5 *"


def test_unclosed_bold_marker_is_left_alone():
    assert to_telegram_html("Bold not closed: **oops") == "Bold not closed: **oops"


def test_snake_case_survives_underscore_rule():
    """A single `_` only opens italics with a non-word boundary on both sides."""
    assert to_telegram_html("snake_case_name va file_1_v2") == "snake_case_name va file_1_v2"


def test_underscore_pair_with_word_boundary_is_italic():
    assert to_telegram_html("bu _muhim_ savol") == "bu <i>muhim</i> savol"


# --------------------------------------------------------------------------- safety


def test_html_injection_is_neutralised():
    assert to_telegram_html("<script>alert(1)</script>") == "&lt;script&gt;alert(1)&lt;/script&gt;"


def test_html_injection_inside_code_is_still_escaped():
    out = to_telegram_html("`<img src=x onerror=alert(1)>`")
    assert out == "<code>&lt;img src=x onerror=alert(1)&gt;</code>"


def test_javascript_scheme_link_is_stripped_to_plain_text():
    out = to_telegram_html("[click](javascript:alert(1))")
    assert out == "click"
    assert "javascript:" not in out


def test_data_scheme_link_is_stripped():
    out = to_telegram_html("[open](data:text/html,<script>alert(1)</script>)")
    assert "data:" not in out
    assert "<script>" not in out.replace("&lt;script&gt;", "")


def test_only_recognised_tags_are_ever_produced():
    """Nothing the author types should be able to introduce a tag we did not put there."""
    out = to_telegram_html("<b>already html</b> and <script>bad</script>")
    assert "<b>already html</b>" not in out  # the input's own tags are escaped, not trusted
    assert "&lt;" in out


def test_unsafe_scheme_inside_a_wikipedia_style_url_pattern_is_still_rejected():
    out = to_telegram_html("[x](vbscript:msgbox(1))")
    assert out == "x"


# --------------------------------------------------------------------------- to_plain


def test_to_plain_strips_markers_but_keeps_words():
    assert to_plain("**Ism** va _familiya_ bilan `kod`") == "Ism va familiya bilan kod"


def test_to_plain_keeps_link_label_only():
    assert to_plain("[Oferta](https://telegra.ph/oferta) bilan tanishing") == (
        "Oferta bilan tanishing"
    )


def test_to_plain_of_empty_string():
    assert to_plain("") == ""
    assert to_telegram_html("") == ""
