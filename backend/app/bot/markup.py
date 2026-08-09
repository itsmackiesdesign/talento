"""Turn the HR's simple Markdown into Telegram markup.

Authors write ordinary Markdown in the panel (usually by clicking toolbar buttons rather
than typing symbols). This module converts it for Telegram.

**Why the output is HTML and not MarkdownV2.** Telegram's MarkdownV2 requires escaping
``_*[]()~`>#+-=|{}.!`` — every one of them, everywhere. An HR writing a perfectly ordinary
line like ``Зарплата 3.000.000 сум!`` produces a message Telegram rejects with a 400, and
the candidate simply never receives that question. Telegram's HTML mode only cares about
``&``, ``<`` and ``>``, which we escape ourselves up front. So Markdown is the *authoring*
format and HTML is the wire format, and the author can type any character they like.

The conversion is also designed so nothing a human can type is invalid: unpaired markers
are left alone as literal text rather than producing broken output. There is no error path,
which is why there is no validation step and no "format" setting to get wrong.
"""

import re
from html import escape

# Only these schemes may appear in a link. Without this check an author (or anyone who can
# reach the panel) could smuggle in a `javascript:` URI.
_SAFE_SCHEMES = ("http://", "https://", "tg://", "mailto:")

_PLACEHOLDER = "\x00{}\x00"


def _protect(text: str, pattern: re.Pattern, store: list, render) -> str:
    """Replace matches with placeholders so later passes cannot rewrite their insides."""

    def swap(match: re.Match) -> str:
        store.append(render(match))
        return _PLACEHOLDER.format(len(store) - 1)

    return pattern.sub(swap, text)


_PRE = re.compile(r"```(.*?)```", re.S)
_CODE = re.compile(r"`([^`\n]+)`")
# The URL half allows one level of balanced parentheses, so links like
# `https://ru.wikipedia.org/wiki/Ключ_(значения)` survive and a stray `)` is not left behind.
_LINK = re.compile(r"\[([^\]\n]+)\]\(((?:[^()\s]|\([^()\s]*\))+)\)")

# Doubled markers are unambiguous. Single `_` additionally requires a non-word character on
# each side, so `snake_case_name` and `file_1_v2` survive untouched.
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
_UNDERLINE = re.compile(r"__(?=\S)(.+?)(?<=\S)__", re.S)
_STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~", re.S)
_ITALIC = re.compile(r"(?<![\w\\])_(?=\S)(.+?)(?<=\S)_(?!\w)", re.S)


def _safe_url(url: str) -> str | None:
    lowered = url.strip().lower()
    return url.strip() if lowered.startswith(_SAFE_SCHEMES) else None


def to_telegram_html(text: str) -> str:
    """Render authored Markdown as Telegram-safe HTML."""
    if not text:
        return ""

    # Escape first: after this point no user character can become markup by accident, and
    # every tag in the output is one we put there.
    out = escape(text, quote=False)

    protected: list[str] = []
    out = _protect(
        out, _PRE, protected, lambda m: f"<pre>{m.group(1).strip('\n')}</pre>"
    )
    out = _protect(out, _CODE, protected, lambda m: f"<code>{m.group(1)}</code>")

    def render_link(match: re.Match) -> str:
        label, raw = match.group(1), match.group(2)
        # `escape` already ran, so unescape the ampersands a query string needs.
        url = _safe_url(raw.replace("&amp;", "&"))
        if url is None:
            return label  # Unsafe scheme: keep the words, drop the link.
        return f'<a href="{escape(url, quote=True)}">{label}</a>'

    out = _protect(out, _LINK, protected, render_link)

    out = _BOLD.sub(r"<b>\1</b>", out)
    out = _UNDERLINE.sub(r"<u>\1</u>", out)
    out = _STRIKE.sub(r"<s>\1</s>", out)
    out = _ITALIC.sub(r"<i>\1</i>", out)

    for index, value in enumerate(protected):
        out = out.replace(_PLACEHOLDER.format(index), value)
    return out


def to_plain(text: str) -> str:
    """Strip formatting markers, leaving the words. Used where markup cannot be rendered."""
    if not text:
        return ""
    out = _PRE.sub(lambda m: m.group(1).strip("\n"), text)
    out = _CODE.sub(r"\1", out)
    out = _LINK.sub(r"\1", out)
    out = _BOLD.sub(r"\1", out)
    out = _UNDERLINE.sub(r"\1", out)
    out = _STRIKE.sub(r"\1", out)
    out = _ITALIC.sub(r"\1", out)
    return out
