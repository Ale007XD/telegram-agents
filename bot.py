import os
import importlib
import logging
import sentry_sdk
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from database import init_db, save_message, get_user_context
from agents.base import Planner, Verifier

load_dotenv()
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""))
logging.basicConfig(level=logging.INFO)

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
planner = Planner(os.getenv("OPENROUTER_API_KEY"))
verifier = Verifier(os.getenv("OPENROUTER_API_KEY"))

class AdminFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        return str(message.from_user.id) == os.getenv("ADMIN_ID")

class HistoryMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.text and not event.text.startswith('/'):
            await save_message(event.from_user.id, "user", event.text)
        return await handler(event, data)

dp.message.outer_middleware(HistoryMiddleware())

def load_skills():
    dp.sub_routers.clear()
    try:
        import skills
        for f in os.listdir("skills"):
            if f.endswith(".py") and not f.startswith("__"):
                module_name = f"skills.{f[:-3]}"
                module = importlib.import_module(module_name)
                importlib.reload(module)
                if hasattr(module, "setup"):
                    dp.include_router(module.setup())
                    logging.info(f"Loaded skill: {module_name}")
    except Exception as e:
        logging.error(f"Skill load error: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚀 Мультиагентный бот активен!\n\n"
        "📋 /plan - Создать план задачи\n"
        "✈️ /travel - Планировщик путешествий\n"
        "🔄 /reload - Перезагрузка навыков (admin)\n"
        "📝 /new_skill - Новый навык (admin)\n"
        "🔍 /review - Анализ истории"
    )

@dp.message(Command("plan"))
async def cmd_plan(message: types.Message):
    task = message.text.replace("/plan", "").strip()
    if not task:
        return await message.answer("Напишите задачу после /plan")
    
    history = await get_user_context(message.from_user.id)
    plan = await planner.process(task, history)
    verified = await verifier.process(plan)
    
    reply = f"📋 **План:**\n{plan}\n\n✅ **Проверка:**\n{verified}"
    await message.answer(reply, parse_mode="Markdown")
    await save_message(message.from_user.id, "assistant", plan)

@dp.message(Command("new_skill"), AdminFilter())
async def handle_new_skill(m: types.Message):
    try:
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3:
            return await m.answer("Формат: /new_skill file_name code")
        
        # Определяем name ЗДЕСЬ
        filename = parts[1]
        code = parts[2]
        
        # Проверка на расширение
        if not filename.endswith(".py"): 
            filename += ".py"
            
        filepath = os.path.join("skills", filename)
        
        with open(filepath, "w", encoding="utf-8") as f: 
            f.write(code)
            
        await m.answer(f"✅ Навык `{filename}` записан. Используйте /reload")
    except Exception as e:
        await m.answer(f"❌ Ошибка записи: {e}")


@dp.message(Command("reload"), AdminFilter())
async def cmd_reload(message: types.Message):
    load_skills()
    await message.answer("🔄 Все навыки перезагружены!")

@dp.message(Command("review"))
async def cmd_review(message: types.Message):
    history = await get_user_context(message.from_user.id)
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    review = await verifier.process(f"Анализируй историю диалога: {history_text}")
    
    with open("CLAUDE.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n## Review {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"User: {message.from_user.id}\n{review}\n")
    
    await message.answer("📊 Анализ завершен и записан в CLAUDE.md")

async def main():
    await init_db()
    load_skills()
    print("🚀 Bot started")
    await dp.start_polling(bot)

import signal
import sys

def signal_handler(sig, frame):
    logging.info("Graceful shutdown...")
    asyncio.create_task(bot.session.close())
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    asyncio.run(main())
