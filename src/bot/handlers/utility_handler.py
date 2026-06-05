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
            "Готовое значение:",
            recipient,
            "",
            "Куда можно вставить:",
            f"HOT_LEAD_TELEGRAM_IDS={recipient}",
            f"ESTIMATE_REQUEST_TELEGRAM_IDS={recipient}",
            f"MEASUREMENT_TELEGRAM_IDS={recipient}",
            f"MANUAL_HELP_TELEGRAM_IDS={recipient}",
            f"SYSTEM_ALERT_TELEGRAM_IDS={recipient}",
            "",
            f"Или в общий fallback: MANAGER_TELEGRAM_IDS={recipient}",
            "",
            "Также теперь можно вставить ссылку на тему вида:",
            "https://t.me/c/3734786933/12",
        ]
    )
    await message.answer("\n".join(lines))


dp.include_router(router)
