"""Запуск бота в режиме polling: python -m app.bot"""
import asyncio

from app.bot.factory import create_bot, create_dispatcher


async def main() -> None:
    bot = create_bot()
    dp = create_dispatcher()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот запущен (polling)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
