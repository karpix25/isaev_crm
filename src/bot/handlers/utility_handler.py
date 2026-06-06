from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot import dp
from src.services.telegram_notification_service import TOPIC_SETTINGS, telegram_notification_service

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


@router.message(Command("notifytest"))
async def cmd_notifytest(message: Message) -> None:
    topic_labels = {
        "hot_lead": "🔥 Горячий лид",
        "estimate_request": "🧮 Просчет сметы",
        "measurement": "📅 Замеры",
        "manual_help": "💬 Ручная помощь",
        "system_alert": "⚠️ Тех. уведомления",
    }
    results = []
    for topic in TOPIC_SETTINGS:
        recipients = telegram_notification_service.recipients_for(topic)
        sent = await telegram_notification_service.send_to_managers(
            f"{topic_labels[topic]}\nТестовое уведомление из /notifytest",
            topic=topic,
        )
        results.append(f"{topic_labels[topic]}: отправлено {sent}/{len(recipients)}")

    await message.answer("Проверка уведомлений:\n" + "\n".join(results))


dp.include_router(router)
