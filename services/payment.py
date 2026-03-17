import logging
from typing import Optional

import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)


class CryptoBotPayment:
    """Integration with @CryptoBot for crypto payments."""

    BASE_URL = "https://pay.crypt.bot/api"  # production
    # For testnet use: "https://testnet-pay.crypt.bot/api"

    def __init__(self, api_token: str):
        self.api_token = api_token

    async def create_invoice(
        self,
        amount: float,
        currency: str = "USDT",
        description: str = "Balance top-up",
        payload: str = "",
    ) -> Optional[dict]:
        """Create a CryptoBot payment invoice. Returns invoice dict or None."""
        async with aiohttp.ClientSession() as session:
            headers = {
                "Crypto-Pay-API-Token": self.api_token,
                "Content-Type": "application/json",
            }
            payload_data = {
                "asset": currency,
                "amount": str(amount),
                "description": description,
                "payload": payload,
                "allow_comments": False,
                "allow_anonymous": False,
            }
            try:
                async with session.post(
                    f"{self.BASE_URL}/createInvoice",
                    headers=headers,
                    json=payload_data,
                ) as resp:
                    data = await resp.json()
                    if data.get("ok"):
                        return data["result"]
                    logger.error(f"CryptoBot error: {data}")
                    return None
            except Exception as e:
                logger.error(f"CryptoBot request failed: {e}")
                return None

    async def get_invoices(self, status: str = "paid") -> list:
        """Get invoices filtered by status."""
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": self.api_token}
            try:
                async with session.get(
                    f"{self.BASE_URL}/getInvoices",
                    headers=headers,
                    params={"status": status},
                ) as resp:
                    data = await resp.json()
                    return data.get("result", {}).get("items", [])
            except Exception as e:
                logger.error(f"CryptoBot get_invoices failed: {e}")
                return []


def get_payment_service() -> Optional[CryptoBotPayment]:
    if settings.CRYPTOBOT_TOKEN:
        return CryptoBotPayment(settings.CRYPTOBOT_TOKEN)
    return None
