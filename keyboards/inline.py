"""Inline keyboards for search results, settings, playlists, etc."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from utils.i18n import t, get_language_flag, get_language_name, SUPPORTED_LANGUAGES


# ───────────────────────── Search Results ─────────────────────────


def search_results_kb(
    query: str,
    page: int,
    total_pages: int,
    track_count: int,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """
    Build inline keyboard for search results.
    Grid: 4 columns × 2 rows for track selection + pagination row.
    """
    buttons = []

    # Track selection buttons (1-8 in two rows of 4)
    row1 = []
    row2 = []
    for i in range(1, min(track_count + 1, 9)):
        btn = InlineKeyboardButton(
            text=str(i) + "️⃣",
            callback_data=f"track:{page}:{i - 1}",
        )
        if i <= 4:
            row1.append(btn)
        else:
            row2.append(btn)

    if row1:
        buttons.append(row1)
    if row2:
        buttons.append(row2)

    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"page:prev:{query}:{page}",
            )
        )

    nav_row.append(
        InlineKeyboardButton(
            text=f"📄 {page + 1}/{total_pages}",
            callback_data="noop",
        )
    )

    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"page:next:{query}:{page}",
            )
        )

    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Video Actions (under downloaded video) ──────


def video_actions_kb(url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Buttons shown under a downloaded video: [🎵 MP3] [🖼 Thumbnail]."""
    # Trim URL for callback_data (max 64 bytes)
    url_hash = str(abs(hash(url)))[:12]
    buttons = [
        [
            InlineKeyboardButton(
                text="🎵 MP3",
                callback_data=f"vid2mp3:{url_hash}",
            ),
            InlineKeyboardButton(
                text="🖼 Thumbnail",
                callback_data=f"vidthumb:{url_hash}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Track Actions ─────────────────────────


def track_actions_kb(
    track_hash: str,
    query: str = "",
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Buttons shown after sending a track."""
    buttons = [
        [
            InlineKeyboardButton(
                text=t("btn_add_playlist", lang),
                callback_data=f"addpl:{track_hash}",
            ),
            InlineKeyboardButton(
                text=t("btn_more", lang),
                callback_data=f"more:{query}" if query else "noop",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Settings ─────────────────────────


def settings_kb(
    current_lang: str,
    current_quality: int,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Settings inline keyboard with toggleable options."""
    buttons = []

    # Language selection row
    lang_row = []
    for code in SUPPORTED_LANGUAGES:
        flag = get_language_flag(code)
        check = " ✅" if code == current_lang else ""
        lang_row.append(
            InlineKeyboardButton(
                text=f"{flag}{check}",
                callback_data=f"lang:{code}",
            )
        )
    buttons.append(lang_row)

    # Quality selection row
    quality_row = []
    for q in [128, 192, 320]:
        check = "✅ " if q == current_quality else ""
        quality_row.append(
            InlineKeyboardButton(
                text=f"{check}{q}",
                callback_data=f"quality:{q}",
            )
        )
    buttons.append(quality_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Playlist ─────────────────────────


def playlist_kb(
    items: list,
    page: int,
    total_pages: int,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Playlist inline keyboard with send/delete buttons per track."""
    buttons = []

    for i, item in enumerate(items):
        label = f"{i + 1}. {item.track_artist} — {item.track_title}"
        row = [
            InlineKeyboardButton(
                text=label[:40],
                callback_data=f"plsend:{item.id}",
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=f"pldel:{item.id}",
            ),
        ]
        buttons.append(row)

    # Pagination
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"plpage:{page - 1}")
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(text="➡️", callback_data=f"plpage:{page + 1}")
        )
    if nav_row:
        buttons.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Force Subscribe ─────────────────────────


def force_sub_kb(channel: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Force subscribe keyboard with channel link + check button."""
    channel_link = f"https://t.me/{channel.lstrip('@')}"
    buttons = [
        [InlineKeyboardButton(text="📢 " + channel, url=channel_link)],
        [InlineKeyboardButton(text=t("force_sub_check", lang), callback_data="checksub")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Shazam Result ─────────────────────────


def shazam_result_kb(
    artist: str, title: str, lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Button to download recognized track."""
    query = f"{artist} {title}"
    buttons = [
        [
            InlineKeyboardButton(
                text=t("shazam_download", lang),
                callback_data=f"shazamdl:{query[:50]}",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
