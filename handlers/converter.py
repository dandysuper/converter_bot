import logging
import os
from io import BytesIO

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from keyboards.inline import format_keyboard
from services.converter import converter_service
from services.database import get_or_create_user, get_balance, deduct_balance, get_user

router = Router()
logger = logging.getLogger(__name__)


class ConvertState(StatesGroup):
    choosing_format = State()


@router.message(F.sticker)
async def handle_sticker(message: types.Message, state: FSMContext):
    """Receive a sticker and ask for output format."""
    # Ensure user exists
    await get_or_create_user(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )

    balance = await get_balance(message.from_user.id)
    if balance < settings.PAYMENT_RATE:
        await message.answer(
            f"❌ Insufficient balance.\n\n"
            f"💰 Your balance: <b>{balance:.2f}₽</b>\n"
            f"🔄 Cost per conversion: <b>{settings.PAYMENT_RATE:.0f}₽</b>\n\n"
            "Use /pay to top up your balance."
        )
        return

    # Store file_id in state
    sticker = message.sticker
    await state.update_data(
        file_id=sticker.file_id,
        file_unique_id=sticker.file_unique_id,
        is_animated=sticker.is_animated,
        is_video=sticker.is_video,
    )

    sticker_type = "🎬 Animated" if (sticker.is_animated or sticker.is_video) else "🖼️ Static"
    await message.answer(
        f"{sticker_type} sticker received!\n\n"
        f"💰 Balance: <b>{balance:.2f}₽</b> (costs {settings.PAYMENT_RATE:.0f}₽)\n\n"
        "Choose output format:",
        reply_markup=format_keyboard(),
    )
    await state.set_state(ConvertState.choosing_format)


@router.callback_query(F.data == "cancel", ConvertState.choosing_format)
async def handle_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Conversion cancelled.")
    await callback.answer()


@router.callback_query(F.data.startswith("format_"), ConvertState.choosing_format)
async def handle_format_selection(callback: types.CallbackQuery, state: FSMContext):
    """Download the sticker, convert it and send the result."""
    fmt = callback.data.split("_", 1)[1]  # gif, mp4, png, webm
    data = await state.get_data()
    await state.clear()

    await callback.message.edit_text(f"⏳ Converting to <b>{fmt.upper()}</b>…")

    # Check & deduct balance
    success = await deduct_balance(callback.from_user.id, settings.PAYMENT_RATE)
    if not success:
        await callback.message.edit_text(
            "❌ Insufficient balance. Use /pay to top up."
        )
        await callback.answer()
        return

    try:
        # Download sticker
        file = await callback.bot.get_file(data["file_id"])
        buf = BytesIO()
        await callback.bot.download_file(file.file_path, destination=buf)
        buf.seek(0)
        file_bytes = buf.read()

        # Fetch user watermark settings
        user = await get_user(callback.from_user.id)
        watermark_text = user.watermark_text if user else None
        font_name = user.watermark_font if user else None
        font_color = user.watermark_color if user else "#FFFFFF"
        position = user.watermark_position if user else "bottom_right"

        # Convert
        result_bytes = await converter_service.convert_sticker(
            file_bytes=file_bytes,
            output_format=fmt,
            watermark_text=watermark_text,
            font_name=font_name,
            font_color=font_color,
            position=position,
        )

        result_buf = BytesIO(result_bytes)
        result_buf.name = f"sticker.{fmt}"

        # Send result
        if fmt == "gif":
            await callback.message.answer_animation(
                types.BufferedInputFile(result_bytes, filename=f"sticker.gif"),
                caption="✅ Here's your GIF!" + (f"\n💧 Watermark: <i>{watermark_text}</i>" if watermark_text else ""),
            )
        elif fmt == "mp4":
            await callback.message.answer_video(
                types.BufferedInputFile(result_bytes, filename="sticker.mp4"),
                caption="✅ Here's your MP4!",
            )
        elif fmt == "webm":
            await callback.message.answer_document(
                types.BufferedInputFile(result_bytes, filename="sticker.webm"),
                caption="✅ Here's your WebM!",
            )
        elif fmt == "png":
            await callback.message.answer_photo(
                types.BufferedInputFile(result_bytes, filename="sticker.png"),
                caption="✅ Here's your PNG!",
            )

        await callback.message.edit_text("✅ Done!")

    except Exception as e:
        logger.error(f"Conversion error: {e}", exc_info=True)
        # Refund on error
        from services.database import add_balance
        await add_balance(callback.from_user.id, settings.PAYMENT_RATE, "Refund – conversion error")
        await callback.message.edit_text(
            "❌ Conversion failed. Your balance has been refunded.\n"
            "Please try again or contact support."
        )

    await callback.answer()
