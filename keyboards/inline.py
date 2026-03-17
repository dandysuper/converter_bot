from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from bot.config import settings


def format_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 GIF", callback_data="format_gif"),
                InlineKeyboardButton(text="📹 MP4", callback_data="format_mp4"),
            ],
            [
                InlineKeyboardButton(text="🖼️ PNG", callback_data="format_png"),
                InlineKeyboardButton(text="🎞️ WebM", callback_data="format_webm"),
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
        ]
    )


def watermark_position_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="↖ Top Left", callback_data="pos_top_left"),
                InlineKeyboardButton(text="↗ Top Right", callback_data="pos_top_right"),
            ],
            [
                InlineKeyboardButton(text="↙ Bottom Left", callback_data="pos_bottom_left"),
                InlineKeyboardButton(text="↘ Bottom Right", callback_data="pos_bottom_right"),
            ],
            [InlineKeyboardButton(text="⊙ Center", callback_data="pos_center")],
            [InlineKeyboardButton(text="🔙 Back", callback_data="wm_back")],
        ]
    )


def watermark_settings_keyboard(webapp_url: str = None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="✏️ Set watermark text", callback_data="wm_set_text")],
        [InlineKeyboardButton(text="📍 Position", callback_data="wm_position")],
    ]
    if webapp_url:
        rows.append([
            InlineKeyboardButton(
                text="🔤 Choose font",
                web_app=WebAppInfo(url=f"{webapp_url}/fonts.html"),
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text="🎨 Choose color",
                web_app=WebAppInfo(url=f"{webapp_url}/color.html"),
            )
        ])
    rows.append([InlineKeyboardButton(text="🗑 Clear watermark", callback_data="wm_clear")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topup_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Pay with CryptoBot", callback_data="pay_crypto")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")],
        ]
    )


def admin_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Users", callback_data="admin_users")],
            [InlineKeyboardButton(text="💰 Add balance", callback_data="admin_balance")],
            [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        ]
    )
