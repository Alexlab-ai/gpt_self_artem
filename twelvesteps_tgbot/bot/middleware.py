from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from bot.backend import get_or_fetch_token
from repositories.SubscriptionRepository import SubscriptionRepository
from db.database import async_session_factory


class PremiumMiddleware(BaseMiddleware):
    """
    Aiogram middleware для проверки подписки.
    Кладёт в data["is_premium"] = True/False
    """

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        
        telegram_id = event.from_user.id

        # Быстро проверяем подписку
        token = await get_or_fetch_token(telegram_id)
        if not token:
            # Пользователь не авторизован — пропускаем (пусть /start сработает)
            return await handler(event, data)

        async with async_session_factory() as session:

            repo       = SubscriptionRepository(session)
            is_premium = await repo.is_premium_active(telegram_id)

            data["is_premium"] = is_premium

        # Можно сразу блокировать здесь, но лучше проверять в handler'ах (гибче)
        return await handler(event, data)