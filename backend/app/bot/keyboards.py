"""Keyboard builders — all bottom (reply) keyboards.

Every builder returns ``(markup, mapping)``: the keyboard to send, and the
``{label: action}`` map that ``app/bot/menu.py`` stores so the resulting text message can
be routed back to an action. Handlers send both through ``_send_menu``.

Action grammar (unchanged from the inline era, so callbacks and taps share one dispatcher):
    br:{branch_id}          open a branch's vacancy list ('general' = unassigned vacancies)
    brpage:{n}              branch list pagination
    vac:{vacancy_id}[:{scope}]  open a vacancy card, remembering which list it came from
    page:{scope}:{n}        vacancy list pagination; scope = branch id | 'general' | 'all'
    apply:{vacancy_id}      start the application form
    back:branches           return to the branch list
    back:list:{scope}       return to a vacancy list
    opt:{index}             pick a single_choice option
    mopt:{index}            toggle a multi_choice option
    mdone                   finish a multi_choice question
    skip                    skip an optional question
    submit / restart        confirm or redo the whole form
    setlang:{code}          switch language
    menu                    back to the main menu

Labels must be unique within one keyboard — they are the routing key. ``_dedupe`` appends
an invisible marker to collisions (two branches genuinely can share a name) so both
buttons stay tappable and distinct.
"""

import uuid

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from app.bot.texts import t

PAGE_SIZE = 8

# Zero-width space: invisible to the candidate, but makes an otherwise duplicate label a
# distinct routing key.
_MARKER = "​"

Entry = tuple[str, str]  # (label, action)


def _dedupe(entries: list[Entry]) -> list[Entry]:
    seen: dict[str, int] = {}
    result: list[Entry] = []
    for label, action in entries:
        count = seen.get(label, 0)
        seen[label] = count + 1
        result.append((label + _MARKER * count if count else label, action))
    return result


def _build(rows: list[list[Entry]]) -> tuple[ReplyKeyboardMarkup, dict[str, str]]:
    flat = _dedupe([entry for row in rows for entry in row])

    # Re-chunk the deduped entries back into the original row shape.
    keyboard, mapping, index = [], {}, 0
    for row in rows:
        buttons = []
        for _ in row:
            label, action = flat[index]
            index += 1
            mapping[label] = action
            buttons.append(KeyboardButton(text=label))
        if buttons:
            keyboard.append(buttons)

    return (
        ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, is_persistent=True),
        mapping,
    )


def remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


# --------------------------------------------------------------------------- main menu


def _pairs(entries: list[Entry]) -> list[list[Entry]]:
    """Lay entries out two per row, leaving a lone final entry full-width."""
    return [entries[i : i + 2] for i in range(0, len(entries), 2)]


def main_menu(
    lang: str, multilingual: bool = False, branches: bool = False
) -> tuple[ReplyKeyboardMarkup, dict]:
    """Two-column main menu.

    Sections that do not apply to this company are omitted rather than shown disabled —
    Branches only when branch mode is on, Language only when more than one is published —
    and the remaining buttons reflow to keep the grid tidy instead of leaving a hole.
    """
    entries: list[Entry] = [(t(lang, "menu_about"), "about")]
    if branches:
        entries.append((t(lang, "menu_branches"), "branches"))
    entries += [
        (t(lang, "menu_vacancies"), "vacancies"),
        (t(lang, "menu_news"), "news"),
        (t(lang, "menu_contacts"), "contacts"),
        (t(lang, "menu_my_apps"), "my_apps"),
    ]
    if multilingual:
        entries.append((t(lang, "menu_language"), "language"))
    return _build(_pairs(entries))


def vacancy_types_keyboard(lang: str, show_hot: bool, show_branches: bool):
    """The 🔥 / 🌐 split. Only rendered when there is a genuine choice to make."""
    row: list[Entry] = []
    if show_hot:
        row.append((t(lang, "hot_vacancies"), "vac_hot"))
    if show_branches:
        row.append((t(lang, "by_branch_vacancies"), "vac_branches"))
    return _build([row, [(t(lang, "menu_back"), "menu")]])


def language_keyboard(
    enabled: list[str], current: str | None, lang: str
) -> tuple[ReplyKeyboardMarkup, dict]:
    """Language names are shown in their own language — never translated."""
    from app.core.i18n import LANGUAGE_NAMES

    rows: list[list[Entry]] = [
        [(("✅ " if code == current else "") + LANGUAGE_NAMES.get(code, code), f"setlang:{code}")]
        for code in enabled
    ]
    rows.append([(t(lang, "menu_back"), "menu")])
    return _build(rows)


# --------------------------------------------------------------------------- browsing


def _pagination(prefix: str, page: int, total_pages: int, lang: str) -> list[Entry]:
    if total_pages <= 1:
        return []
    row: list[Entry] = []
    if page > 0:
        row.append((t(lang, "page_prev"), f"{prefix}{page - 1}"))
    if page < total_pages - 1:
        row.append((t(lang, "page_next"), f"{prefix}{page + 1}"))
    return row


def branches_keyboard(
    branches: list[tuple[uuid.UUID | None, str, str | None, int]], page: int, lang: str
) -> tuple[ReplyKeyboardMarkup, dict]:
    """``branches`` items are (id | None for general, name, city, active_vacancy_count)."""
    total_pages = max(1, (len(branches) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = branches[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    rows: list[list[Entry]] = []
    for branch_id, name, city, count in chunk:
        if branch_id is None:
            rows.append([(f"{t(lang, 'general_vacancies')} ({count})", "br:general")])
        else:
            label = f"📍 {name}" + (f" — {city}" if city else "") + f" ({count})"
            rows.append([(label, f"br:{branch_id.hex}")])

    pagination = _pagination("brpage:", page, total_pages, lang)
    if pagination:
        rows.append(pagination)
    rows.append([(t(lang, "menu_back"), "menu")])
    return _build(rows)


def vacancies_keyboard(
    vacancies: list[tuple[uuid.UUID, str]],
    page: int,
    scope: str,
    lang: str,
    show_back_to_branches: bool,
) -> tuple[ReplyKeyboardMarkup, dict]:
    total_pages = max(1, (len(vacancies) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    chunk = vacancies[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    # The scope travels with the action so the card's Back button returns to the list the
    # candidate actually came from — otherwise a hot vacancy would send them to a branch
    # list they never visited.
    rows: list[list[Entry]] = [[(title, f"vac:{vid.hex}:{scope}")] for vid, title in chunk]

    pagination = _pagination(f"page:{scope}:", page, total_pages, lang)
    if pagination:
        rows.append(pagination)
    rows.append(
        [(t(lang, "back_to_branches"), "back:branches")]
        if show_back_to_branches
        else [(t(lang, "menu_back"), "menu")]
    )
    return _build(rows)


def branch_info_keyboard(
    branches: list[tuple[uuid.UUID, str, str | None]], lang: str
) -> tuple[ReplyKeyboardMarkup, dict]:
    """Branch directory — two per row, with the back button sharing the last row when odd."""
    entries: list[Entry] = [
        (f"📍 {name}" + (f" — {city}" if city else ""), f"binfo:{bid.hex}")
        for bid, name, city in branches
    ]
    rows = _pairs(entries)
    back: Entry = (t(lang, "menu_back"), "menu")
    if rows and len(rows[-1]) == 1:
        rows[-1].append(back)
    else:
        rows.append([back])
    return _build(rows)


def news_keyboard(lang: str, has_more: bool, next_page: int):
    rows: list[list[Entry]] = []
    if has_more:
        rows.append([(t(lang, "news_more"), f"newspage:{next_page}")])
    rows.append([(t(lang, "menu_back"), "menu")])
    return _build(rows)


def back_only_keyboard(lang: str, action: str = "menu"):
    return _build([[(t(lang, "menu_back"), action)]])


def vacancy_card_keyboard(
    vacancy_id: uuid.UUID, scope: str, lang: str
) -> tuple[ReplyKeyboardMarkup, dict]:
    return _build(
        [
            [(t(lang, "apply"), f"apply:{vacancy_id.hex}")],
            [(t(lang, "back"), f"back:list:{scope}")],
        ]
    )


# --------------------------------------------------------------------------- the form


def single_choice_keyboard(
    options: list[str], lang: str, allow_skip: bool
) -> tuple[ReplyKeyboardMarkup, dict]:
    rows: list[list[Entry]] = [[(opt, f"opt:{i}")] for i, opt in enumerate(options)]
    if allow_skip:
        rows.append([(t(lang, "skip"), "skip")])
    rows.append([(t(lang, "cancel_button"), "cancel")])
    return _build(rows)


def multi_choice_keyboard(
    options: list[str], selected: list[int], lang: str, allow_skip: bool
) -> tuple[ReplyKeyboardMarkup, dict]:
    """``selected`` holds option *indexes*, so the same state renders in any language.

    A reply keyboard cannot be edited in place the way an inline one can, so each toggle
    re-sends the keyboard with the checkmarks redrawn.
    """
    rows: list[list[Entry]] = [
        [(("✅ " if i in selected else "▫️ ") + opt, f"mopt:{i}")] for i, opt in enumerate(options)
    ]
    controls: list[Entry] = [(t(lang, "done"), "mdone")]
    if allow_skip:
        controls.append((t(lang, "skip"), "skip"))
    rows.append(controls)
    rows.append([(t(lang, "cancel_button"), "cancel")])
    return _build(rows)


def text_answer_keyboard(lang: str, allow_skip: bool) -> tuple[ReplyKeyboardMarkup, dict]:
    """Free-text questions still need a way out, so Cancel (and Skip) stay on screen."""
    rows: list[list[Entry]] = []
    if allow_skip:
        rows.append([(t(lang, "skip"), "skip")])
    rows.append([(t(lang, "cancel_button"), "cancel")])
    return _build(rows)


def phone_keyboard(lang: str, allow_skip: bool) -> tuple[ReplyKeyboardMarkup, dict]:
    """``request_contact`` is the fastest path to a verified number — one tap, no typing."""
    share = t(lang, "share_contact")
    rows = [[KeyboardButton(text=share, request_contact=True)]]
    mapping: dict[str, str] = {}
    if allow_skip:
        rows.append([KeyboardButton(text=t(lang, "skip"))])
        mapping[t(lang, "skip")] = "skip"
    rows.append([KeyboardButton(text=t(lang, "cancel_button"))])
    mapping[t(lang, "cancel_button")] = "cancel"

    return (
        ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True),
        mapping,
    )


def confirm_keyboard(lang: str) -> tuple[ReplyKeyboardMarkup, dict]:
    return _build(
        [
            [(t(lang, "submit"), "submit")],
            [(t(lang, "restart_form"), "restart")],
            [(t(lang, "cancel_button"), "cancel")],
        ]
    )
