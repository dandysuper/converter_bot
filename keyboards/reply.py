from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

remove_keyboard = ReplyKeyboardRemove()


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="⚙️ Watermark settings"), KeyboardButton(text="💰 Balance")],
        [KeyboardButton(text="💳 Top up"), KeyboardButton(text="ℹ️ Help")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="📊 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
