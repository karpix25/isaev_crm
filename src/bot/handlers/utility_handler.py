from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot import dp
from src.services.telegram_notification_service import TOPIC_SETTINGS, TelegramRecipient, telegram_notification_service

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
    results = []
    for topic in TOPIC_SETTINGS:
        resolution = telegram_notification_service.resolve_recipients(topic)
        sent = await telegram_notification_service.send_to_managers(
            f"{telegram_notification_service.TOPIC_LABELS[topic]}\nТестовое уведомление из /notifytest",
            topic=topic,
        )
        results.append(
            "\n".join(
                [
                    f"{telegram_notification_service.TOPIC_LABELS[topic]}: отправлено {sent}/{len(resolution.recipients)}",
                    f"  env: {resolution.setting_name}",
                    f"  source: {_source_label(resolution.source)}",
                    f"  recipients: {_format_recipients(resolution.recipients)}",
                ]
            )
        )

    await message.answer("Проверка уведомлений:\n" + "\n".join(results))


@router.message(Command("notifytopics"))
async def cmd_notifytopics(message: Message) -> None:
    lines = [
        "Темы уведомлений:",
        "",
        "1. В нужной теме группы отправьте /chatid.",
        "2. Скопируйте готовую строку в переменную Coolify.",
        "3. После деплоя проверьте /notifytest.",
        "",
    ]
    for topic, setting_name in TOPIC_SETTINGS.items():
        resolution = telegram_notification_service.resolve_recipients(topic)
        lines.extend(
            [
                f"{telegram_notification_service.TOPIC_LABELS[topic]}",
                f"env: {setting_name.upper()}",
                f"сейчас: {_format_recipients(resolution.recipients)} ({_source_label(resolution.source)})",
                "",
            ]
        )
    await message.answer("\n".join(lines))


def _format_recipients(recipients: tuple[TelegramRecipient, ...] | list[TelegramRecipient]) -> str:
    if not recipients:
        return "не настроено"
    return ", ".join(
        f"{recipient.chat_id}:{recipient.message_thread_id}"
        if recipient.message_thread_id is not None
        else str(recipient.chat_id)
        for recipient in recipients
    )


def _source_label(source: str) -> str:
    return {
        "topic": "конкретная тема",
        "fallback": "fallback MANAGER_TELEGRAM_IDS",
        "manager": "MANAGER_TELEGRAM_IDS",
        "empty": "пусто",
    }.get(source, source)


dp.include_router(router)
