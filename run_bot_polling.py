"""
Telegram Bot Polling Mode - For Local Development

This script runs the bot in polling mode, which means it actively checks
for new messages from Telegram servers. This is perfect for local testing
without needing webhooks or public URLs.

Usage:
    python run_bot_polling.py
"""
import asyncio
import sys
sys.path.insert(0, '/Users/nadaraya/Desktop/Расул СРМ')

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode

from src.config import settings
from src.bot import dp, bot


async def main():
    """Start bot in polling mode"""
    
    if not bot:
        print("❌ Bot not initialized! Check your TELEGRAM_BOT_TOKEN in .env")
        return
    
    print("=" * 60)
    print("🤖 Starting Telegram Bot in POLLING mode...")
    print("=" * 60)
    
    try:
        # Get bot info
        bot_info = await bot.get_me()
        print(f"\n✅ Bot connected: @{bot_info.username}")
        print(f"   Bot ID: {bot_info.id}")
        print(f"   Bot Name: {bot_info.first_name}")
        
        # Delete webhook (in case it was set before)
        await bot.delete_webhook(drop_pending_updates=True)
        print("\n✅ Webhook deleted (polling mode enabled)")
        
        print("\n" + "=" * 60)
        print("🎧 Bot is now listening for messages...")
        print("=" * 60)
        print("\n📱 Open Telegram and send a message to your bot!")
        print(f"   Bot username: @{bot_info.username}")
        print("\n💡 Press Ctrl+C to stop the bot\n")
        
        # Start polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Bot stopped by user")
