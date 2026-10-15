from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from config import ADMIN_ID
from database.queries import get_user


class AccessMiddleware(BaseMiddleware):
    """Пропускает только одобренных пользователей и админа."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user = None
        message = None
        callback = None

        if isinstance(event, Update):
            if event.message:
                tg_user = event.message.from_user
                message = event.message
            elif event.callback_query:
                tg_user = event.callback_query.from_user
                callback = event.callback_query
            elif event.edited_message:
                tg_user = event.edited_message.from_user

        if tg_user is None:
            return await handler(event, data)

        if tg_user.id == ADMIN_ID:
            data["user"] = await get_user(tg_user.id)
            return await handler(event, data)

        user = await get_user(tg_user.id)

        if user is None:
            if message and message.text and message.text.startswith("/start"):
                return await handler(event, data)
            await self._deny(message, callback, tg_user.id, pending=False)
            return None

        if not user["is_approved"]:
            if message and message.text and message.text.startswith("/start"):
                return await handler(event, data)
            await self._deny(message, callback, tg_user.id, pending=True)
            return None

        data["user"] = user
        return await handler(event, data)

    @staticmethod
    async def _deny(message, callback, user_id: int, pending: bool) -> None:
        if pending:
            text = (
                "⏳ Ваша заявка на доступ ещё не одобрена.\n"
                "Организатор увидит её и подтвердит доступ.\n\n"
                f"Ваш ID: <code>{user_id}</code>"
            )
        else:
            text = (
                "🚫 Доступ к боту ограничен.\n"
                "Отправьте /start, чтобы оставить заявку на доступ.\n\n"
                f"Ваш ID: <code>{user_id}</code>"
            )

        if message:
            await message.answer(text)
        elif callback:
            await callback.answer(
                "Доступ ещё не одобрен. Обратитесь к организатору.",
                show_alert=True,
            )