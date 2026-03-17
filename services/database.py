import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Float, DateTime, select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, sessionmaker

from bot.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(String, unique=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    balance = Column(Float, default=0.0)
    conversions_count = Column(Integer, default=0)
    watermark_text = Column(String, nullable=True)
    watermark_font = Column(String, default="default")
    watermark_color = Column(String, default="#FFFFFF")
    watermark_position = Column(String, default="bottom_right")
    created_at = Column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)  # 'payment', 'conversion', 'bonus'
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# Engine & session
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized.")


# ─── User helpers ──────────────────────────────────────────────────────────────

async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
) -> User:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == str(telegram_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=str(telegram_id),
                username=username,
                first_name=first_name,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user


async def get_user(telegram_id: int) -> Optional[User]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == str(telegram_id))
        )
        return result.scalar_one_or_none()


async def get_balance(telegram_id: int) -> float:
    user = await get_user(telegram_id)
    return user.balance if user else 0.0


async def deduct_balance(telegram_id: int, amount: float) -> bool:
    """Deduct balance and increment conversion count. Returns True on success."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == str(telegram_id))
        )
        user = result.scalar_one_or_none()
        if user is None or user.balance < amount:
            return False
        user.balance -= amount
        user.conversions_count += 1
        session.add(
            Transaction(
                user_id=str(telegram_id),
                amount=-amount,
                type="conversion",
                description="Sticker conversion",
            )
        )
        await session.commit()
        return True


async def add_balance(telegram_id: int, amount: float, description: str = "Top up"):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == str(telegram_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            return
        user.balance += amount
        session.add(
            Transaction(
                user_id=str(telegram_id),
                amount=amount,
                type="payment",
                description=description,
            )
        )
        await session.commit()


async def update_watermark_settings(
    telegram_id: int,
    text: Optional[str] = None,
    font: Optional[str] = None,
    color: Optional[str] = None,
    position: Optional[str] = None,
):
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == str(telegram_id))
        )
        user = result.scalar_one_or_none()
        if user is None:
            return
        if text is not None:
            user.watermark_text = text
        if font is not None:
            user.watermark_font = font
        if color is not None:
            user.watermark_color = color
        if position is not None:
            user.watermark_position = position
        await session.commit()


# ─── Admin helpers ─────────────────────────────────────────────────────────────

async def get_stats() -> dict:
    async with async_session() as session:
        total_users = await session.scalar(select(func.count(User.id)))
        total_conversions = await session.scalar(
            select(func.sum(User.conversions_count))
        )
        total_revenue = await session.scalar(
            select(func.sum(Transaction.amount)).where(
                Transaction.type == "payment"
            )
        )
        return {
            "total_users": total_users or 0,
            "total_conversions": total_conversions or 0,
            "total_revenue": round(total_revenue or 0.0, 2),
        }


async def get_all_user_ids() -> list[str]:
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        return [row[0] for row in result.fetchall()]
