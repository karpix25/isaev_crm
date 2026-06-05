from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot import dp

router = Router()


@router.message(Command("chatid"))
async def cmd_chatid(message: Message) -> None:
    thread_id = message.message_thread_id
    recipient = f"{message.chat.id}:{thread_id}" if thread_id else str(message.chat.id)

    lines = [
        "ID для уведомлений:",
        f"chat_id: {message.chat.id}",
    ]
    if thread_id:
        lines.append(f"message_thread_id: {thread_id}")
    lines.extend(
        [
            "",
            "Добавьте в MANAGER_TELEGRAM_IDS:",
            recipient,
        ]
    )
    await message.answer("\n".join(lines))


dp.include_router(router)
