from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command

from bot.config import settings
from keyboards.reply import main_menu_keyboard
from services.database import get_or_create_user

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    user = await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )
    is_admin = str(message.from_user.id) == str(settings.ADMIN_ID)

    await message.answer(
        f"👋 Hello, <b>{message.from_user.first_name}</b>!\n\n"
        "🎯 I convert Telegram stickers and emoji to:\n"
        "  • 🎬 GIF\n"
        "  • 📹 MP4 / 🎞️ WebM\n"
        "  • 🖼️ PNG\n\n"
        "✨ Supports custom watermarks with your own font & color!\n\n"
        f"💰 Your balance: <b>{user.balance:.2f}₽</b>\n"
        f"🔄 Cost per conversion: <b>{settings.PAYMENT_RATE:.0f}₽</b>\n\n"
        "👇 Just send me a sticker to get started!",
        reply_markup=main_menu_keyboard(is_admin=is_admin),
    )


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📖 <b>How to use this bot:</b>\n\n"
        "1️⃣ Send any Telegram sticker\n"
        "2️⃣ Choose your output format (GIF / MP4 / PNG / WebM)\n"
        "3️⃣ Get your file instantly!\n\n"
        "⚙️ <b>Commands:</b>\n"
        "/start — Main menu\n"
        "/help — This message\n"
        "/balance — Check your balance\n"
        "/pay — Top up balance\n"
        "/settings — Watermark settings\n\n"
        "💡 <b>Tip:</b> Set a watermark in ⚙️ Watermark settings to brand your GIFs!",
    )


@router.message(Command("balance"))
async def cmd_balance(message: types.Message):
    from services.database import get_balance
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"💰 Your balance: <b>{balance:.2f}₽</b>\n"
        f"🔄 Each conversion costs <b>{settings.PAYMENT_RATE:.0f}₽</b>\n\n"
        "Use /pay to top up.",
    )


@router.message(F.text == "ℹ️ Help")
async def handle_help_text(message: types.Message):
    await cmd_help(message)
