import logging

from aiogram import Router, F, types
from aiogram.filters import Command, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from keyboards.inline import admin_keyboard
from services.database import get_stats, get_all_user_ids, add_balance

router = Router()
logger = logging.getLogger(__name__)


class IsAdmin(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return str(message.from_user.id) == str(settings.ADMIN_ID)


class AdminState(StatesGroup):
    entering_user_id = State()
    entering_balance_amount = State()
    entering_broadcast = State()


async def _show_admin_panel(message: types.Message):
    stats = await get_stats()
    await message.answer(
        "📊 <b>Admin Panel</b>\n\n"
        f"👥 Total users: <b>{stats['total_users']}</b>\n"
        f"🔄 Total conversions: <b>{stats['total_conversions']}</b>\n"
        f"💸 Total revenue: <b>{stats['total_revenue']}₽</b>",
        reply_markup=admin_keyboard(),
    )


@router.message(Command("admin"), IsAdmin())
async def cmd_admin(message: types.Message):
    await _show_admin_panel(message)


@router.message(F.text == "📊 Admin panel", IsAdmin())
async def btn_admin(message: types.Message):
    await _show_admin_panel(message)


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users", IsAdmin())
async def admin_users(callback: types.CallbackQuery):
    stats = await get_stats()
    user_ids = await get_all_user_ids()
    preview = ", ".join(user_ids[:10])
    more = f" (+{len(user_ids) - 10} more)" if len(user_ids) > 10 else ""
    await callback.message.answer(
        f"👥 <b>Users ({stats['total_users']} total)</b>\n\n"
        f"IDs: <code>{preview}{more}</code>"
    )
    await callback.answer()


# ── Add balance ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_balance", IsAdmin())
async def admin_balance_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "💰 Enter the Telegram user ID to add balance to:"
    )
    await state.set_state(AdminState.entering_user_id)
    await callback.answer()


@router.message(AdminState.entering_user_id, IsAdmin())
async def admin_balance_user(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await state.update_data(target_user_id=user_id)
        await message.answer(f"Enter the amount (₽) to add to user <code>{user_id}</code>:")
        await state.set_state(AdminState.entering_balance_amount)
    except ValueError:
        await message.answer("⚠️ Please send a valid numeric Telegram ID.")


@router.message(AdminState.entering_balance_amount, IsAdmin())
async def admin_balance_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip())
        data = await state.get_data()
        target_id = data["target_user_id"]
        await add_balance(target_id, amount, description=f"Admin grant by {message.from_user.id}")
        await state.clear()
        await message.answer(f"✅ Added <b>{amount:.2f}₽</b> to user <code>{target_id}</code>.")
        # Notify the user
        try:
            await message.bot.send_message(
                target_id,
                f"💰 Your balance has been topped up by <b>{amount:.2f}₽</b> by the admin!",
            )
        except Exception:
            pass
    except ValueError:
        await message.answer("⚠️ Please send a valid number.")


# ── Broadcast ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast", IsAdmin())
async def admin_broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "📢 Send the message you want to broadcast to all users:"
    )
    await state.set_state(AdminState.entering_broadcast)
    await callback.answer()


@router.message(AdminState.entering_broadcast, IsAdmin())
async def admin_broadcast_send(message: types.Message, state: FSMContext):
    await state.clear()
    user_ids = await get_all_user_ids()
    sent = 0
    failed = 0
    status_msg = await message.answer(f"📢 Sending to {len(user_ids)} users…")

    for uid in user_ids:
        try:
            await message.bot.send_message(uid, message.text)
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ Broadcast complete!\n\n"
        f"✉️ Sent: <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>"
    )
