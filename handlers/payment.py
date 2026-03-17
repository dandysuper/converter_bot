import logging

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.config import settings
from keyboards.inline import topup_keyboard
from services.database import add_balance, get_balance
from services.payment import get_payment_service

router = Router()
logger = logging.getLogger(__name__)


class PaymentState(StatesGroup):
    choosing_amount = State()


async def _show_balance(message: types.Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"💰 <b>Your balance: {balance:.2f}₽</b>\n\n"
        f"🔄 Each conversion costs <b>{settings.PAYMENT_RATE:.0f}₽</b>\n\n"
        "Choose a top-up method:",
        reply_markup=topup_keyboard(),
    )


@router.message(Command("pay"))
async def cmd_pay(message: types.Message):
    await _show_balance(message)


@router.message(F.text == "💳 Top up")
async def btn_topup(message: types.Message):
    await _show_balance(message)


@router.message(F.text == "💰 Balance")
async def btn_balance(message: types.Message):
    balance = await get_balance(message.from_user.id)
    await message.answer(
        f"💰 <b>Your balance: {balance:.2f}₽</b>\n\n"
        f"🔄 Each conversion costs <b>{settings.PAYMENT_RATE:.0f}₽</b>"
    )


@router.callback_query(F.data == "pay_crypto")
async def pay_with_crypto(callback: types.CallbackQuery):
    svc = get_payment_service()
    if svc is None:
        await callback.answer(
            "❌ Crypto payments are not configured yet.\n"
            "Please contact the admin to top up your balance.",
            show_alert=True,
        )
        return

    # Create a 1 USDT invoice (≈ enough for 10 conversions example)
    invoice = await svc.create_invoice(
        amount=1.0,
        currency="USDT",
        description="Balance top-up for Sticker Converter Bot",
        payload=str(callback.from_user.id),
    )

    if invoice:
        await callback.message.answer(
            f"💎 <b>Pay with CryptoBot</b>\n\n"
            f"Amount: <b>1 USDT</b>\n\n"
            f"👉 <a href='{invoice['pay_url']}'>Click here to pay</a>\n\n"
            "After payment your balance will be credited automatically.",
            disable_web_page_preview=True,
        )
    else:
        await callback.answer("❌ Failed to create invoice. Try again later.", show_alert=True)

    await callback.answer()
