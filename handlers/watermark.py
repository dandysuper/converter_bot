import logging

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from keyboards.inline import watermark_settings_keyboard, watermark_position_keyboard
from services.database import get_user, update_watermark_settings

router = Router()
logger = logging.getLogger(__name__)


class WatermarkState(StatesGroup):
    entering_text = State()


async def _show_watermark_menu(message: types.Message):
    user = await get_user(message.from_user.id)
    wm_text = user.watermark_text if user else "None"
    wm_font = user.watermark_font if user else "default"
    wm_color = user.watermark_color if user else "#FFFFFF"
    wm_pos = user.watermark_position if user else "bottom_right"

    webapp_url = settings.WEBAPP_URL

    await message.answer(
        "⚙️ <b>Watermark Settings</b>\n\n"
        f"✏️ Text: <code>{wm_text or '—'}</code>\n"
        f"🔤 Font: <code>{wm_font}</code>\n"
        f"🎨 Color: <code>{wm_color}</code>\n"
        f"📍 Position: <code>{wm_pos.replace('_', ' ')}</code>\n\n"
        "Your watermark is added to every converted sticker.",
        reply_markup=watermark_settings_keyboard(webapp_url=webapp_url),
    )


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    await _show_watermark_menu(message)


@router.message(F.text == "⚙️ Watermark settings")
async def btn_settings(message: types.Message):
    await _show_watermark_menu(message)


# ── Set watermark text ────────────────────────────────────────────────────────

@router.callback_query(F.data == "wm_set_text")
async def wm_set_text(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "✏️ Send me the text you want to use as a watermark.\n"
        "Or send /cancel to abort."
    )
    await state.set_state(WatermarkState.entering_text)
    await callback.answer()


@router.message(WatermarkState.entering_text)
async def wm_receive_text(message: types.Message, state: FSMContext):
    if message.text and message.text.strip():
        text = message.text.strip()[:50]  # limit to 50 chars
        await update_watermark_settings(message.from_user.id, text=text)
        await state.clear()
        await message.answer(f"✅ Watermark text set to: <code>{text}</code>")
        await _show_watermark_menu(message)
    else:
        await message.answer("⚠️ Please send a text message.")


@router.message(Command("cancel"), WatermarkState.entering_text)
async def wm_cancel_text(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Cancelled.")


# ── Position ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "wm_position")
async def wm_position(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📍 Choose watermark position:",
        reply_markup=watermark_position_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pos_"))
async def wm_set_position(callback: types.CallbackQuery):
    position = callback.data[4:]  # e.g. "bottom_right"
    await update_watermark_settings(callback.from_user.id, position=position)
    await callback.answer(f"✅ Position set to {position.replace('_', ' ')}", show_alert=False)
    await _show_watermark_menu(callback.message)


@router.callback_query(F.data == "wm_back")
async def wm_back(callback: types.CallbackQuery):
    await _show_watermark_menu(callback.message)
    await callback.answer()


# ── Clear watermark ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "wm_clear")
async def wm_clear(callback: types.CallbackQuery):
    await update_watermark_settings(callback.from_user.id, text=None)
    await callback.answer("🗑 Watermark cleared!", show_alert=False)
    await _show_watermark_menu(callback.message)


# ── WebApp data (font/color picker) ──────────────────────────────────────────

@router.message(F.web_app_data)
async def handle_webapp_data(message: types.Message):
    import json
    try:
        data = json.loads(message.web_app_data.data)
        if "font" in data:
            font = data["font"]
            await update_watermark_settings(message.from_user.id, font=font)
            await message.answer(f"✅ Font set to: <b>{font}</b>")
        if "color" in data:
            color = data["color"]
            await update_watermark_settings(message.from_user.id, color=color)
            await message.answer(f"✅ Color set to: <code>{color}</code>")
    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("⚠️ Could not process selection. Please try again.")
