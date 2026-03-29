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
    Build inline keyboard for search results matching specific 1-8 layout.
    """
    buttons = []

    # Track selection buttons (1-8 in two rows of 4)
    row1 = []
    row2 = []
    for i in range(1, 9):
        # We always want 1-8 buttons, if track doesn't exist, we can handle it in callback or grey it out
        # But usually we show 1-8, if only 3 tracks, 4-8 will just say 'track_not_found' or we can conditionally hide them
        # The user wants exactly this layout. Let's show buttons 1-8. If clicked on empty, do nothing.
        cb_data = f"track:{page}:{i - 1}" if i <= track_count else "noop"
        btn = InlineKeyboardButton(text=str(i), callback_data=cb_data)
        if i <= 4:
            row1.append(btn)
        else:
            row2.append(btn)

    buttons.append(row1)
    buttons.append(row2)

    # Pagination row
    nav_row = []
    nav_row.append(
        InlineKeyboardButton(
            text="⬅️",
            callback_data=f"page:prev:{query}:{page}" if page > 0 else "noop",
        )
    )
    nav_row.append(
        InlineKeyboardButton(
            text="❌",
            callback_data="close_msg",
        )
    )
    nav_row.append(
        InlineKeyboardButton(
            text="➡️",
            callback_data=f"page:next:{query}:{page}" if page < total_pages - 1 else "noop",
        )
    )
    buttons.append(nav_row)

    # Options row: √ | BR: * | ? Lossless | Title
    options_row = [
        InlineKeyboardButton(text="√", callback_data="noop"),
        InlineKeyboardButton(text="BR: *", callback_data="noop"),
        InlineKeyboardButton(text="? Lossless", callback_data="noop"),
        InlineKeyboardButton(text="Title", callback_data="noop"),
    ]
    buttons.append(options_row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Video Actions (under downloaded video) ──────


def video_actions_kb(url: str, lang: str = "ru") -> InlineKeyboardMarkup:
    """Buttons shown under a downloaded video."""
    # Trim URL for callback_data (max 64 bytes)
    url_hash = str(abs(hash(url)))[:12]
    buttons = [
        [
            InlineKeyboardButton(
                text="💾 Saqlash",
                callback_data=f"vid2sav:{url_hash}", # We can map this to a save playlist action
            )
        ],
        [
            InlineKeyboardButton(
                text="📥 Qo'shiqni yuklab olish",
                callback_data=f"vid2mp3:{url_hash}",
            )
        ],
        [
            InlineKeyboardButton(
                text="Guruhga qo'shish ↗️",
                url="https://t.me/your_bot_username?startgroup=true", # Typically how add to group works
            )
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
                text="❤️/💔",
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="🎛",
                callback_data=f"addpl:{track_hash}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="Guruhga qo'shish ↗️",
                url="https://t.me/your_bot_username?startgroup=true",
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ───────────────────────── Settings ─────────────────────────


def settings_kb(
    user,
    lang: str = "ru",
) -> InlineKeyboardMarkup:
    """Settings inline keyboard with the new requested layout."""
    buttons = []

    # 1. Language
    buttons.append([InlineKeyboardButton(text="🌐 Язык", callback_data="set_lang")])

    # 2. Bitrate Preview: √
    bp_check = "√" if user.bitrate_preview else "❌"
    buttons.append([InlineKeyboardButton(text=f"📊 Превью битрейта: {bp_check}", callback_data="toggle_bp")])

    # 3. Likes buttons: √
    lb_check = "√" if user.likes_buttons else "❌"
    buttons.append([InlineKeyboardButton(text=f"❤️ Кнопки лайков: {lb_check}", callback_data="toggle_lb")])

    # 4. Audio Caption
    buttons.append([InlineKeyboardButton(text=f"🎵 Подпись к аудио: {user.audio_caption}", callback_data="toggle_caption")])

    # 5. Advanced Search
    as_check = "√" if user.advanced_search else "❌"
    buttons.append([InlineKeyboardButton(text=f"🔍 Расширенный поиск: {as_check}", callback_data="toggle_as")])

    # 6. Theme
    buttons.append([InlineKeyboardButton(text=f"√ Тема: {user.theme}", callback_data="theme_menu")])

    # 7. Close
    buttons.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_msg")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def themes_kb() -> InlineKeyboardMarkup:
    """Themes selection keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="Нет", callback_data="settheme:none"),
            InlineKeyboardButton(text="🍃 android", callback_data="settheme:android"),
        ],
        [
            InlineKeyboardButton(text="🦄 angel_@endlesslypainful", callback_data="settheme:angel_@endlesslypainful"),
            InlineKeyboardButton(text="🎨 autumn_@pintura_pinn", callback_data="settheme:autumn_@pintura_pinn"),
        ],
        [
            InlineKeyboardButton(text="💗 pink", callback_data="settheme:pink"),
            InlineKeyboardButton(text="pixel", callback_data="settheme:pixel"),
        ],
        [
            InlineKeyboardButton(text="👾 vector", callback_data="settheme:vector"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings"),
            InlineKeyboardButton(text="❌ Закрыть", callback_data="close_msg"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def languages_kb(current_lang: str) -> InlineKeyboardMarkup:
    """Language selection keyboard."""
    buttons = []
    
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
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_settings"),
        InlineKeyboardButton(text="❌ Закрыть", callback_data="close_msg"),
    ])
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
