from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from src.bot import dp

# Create router for worker handlers
router = Router()


@router.message(Command("report"))
async def cmd_report(message: Message):
    """
    Handle /report command from workers.
    This will be implemented in Phase 4.
    """
    await message.answer(
        "📝 Функция отчетов будет доступна в следующей версии.\n"
        "Пожалуйста, обратитесь к менеджеру."
    )


# Register router with dispatcher
dp.include_router(router)
