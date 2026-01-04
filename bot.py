import os, importlib, logging, sentry_sdk, asyncio
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
    async def __call__(self, m: types.Message) -> bool:
        return str(m.from_user.id) == os.getenv("ADMIN_ID")

class HistoryMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.text:
            if not event.text.startswith('/'):
                await save_message(event.from_user.id, "user", event.text)
        return await handler(event, data)

dp.message.outer_middleware(HistoryMiddleware())

def load_skills():
    dp.sub_routers.clear()
    if not os.path.exists("skills"): os.makedirs("skills")
    for f in os.listdir("skills"):
        if f.endswith(".py") and not f.startswith("__"):
            name = f"skills.{f[:-3]}"
            mod = importlib.import_module(name)
            importlib.reload(mod)
            if hasattr(mod, "setup"): dp.include_router(mod.setup())

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    await m.answer("Бот активен. Доступные команды: /plan, /reload, /new_skill, /review")

@dp.message(Command("plan"))
async def handle_plan(m: types.Message):
    task = m.text.replace("/plan", "").strip()
    if not task: return await m.answer("Напишите задачу после команды.")
    
    history = await get_user_context(m.from_user.id)
    plan = await planner.process(task, history)
    verified = await verifier.process(plan)
    
    reply = f"📋 **План:**
{plan}

✅ **Проверка:**
{verified}"
    await m.answer(reply, parse_mode="Markdown")
    await save_message(m.from_user.id, "assistant", plan)

@dp.message(Command("new_skill"), AdminFilter())
async def handle_new_skill(m: types.Message):
    try:
        parts = m.text.split(maxsplit=2)
        name, code = parts[1], parts[2]
        with open(f"skills/{name}.py", "w", encoding="utf-8") as f: f.write(code)
        await m.answer(f"Навык {name} сохранен. Используйте /reload")
    except: await m.answer("Формат: /new_skill название_файла код")

@dp.message(Command("reload"), AdminFilter())
async def handle_reload(m: types.Message):
    load_skills()
    await m.answer("🔄 Навыки перезагружены.")

@dp.message(Command("review"))
async def handle_review(m: types.Message):
    history = await get_user_context(m.from_user.id)
    text_history = "
".join([f"{i['role']}: {i['content']}" for i in history])
    review = await verifier.process(f"Проанализируй контекст диалога на наличие нерешенных проблем: {text_history}")
    
    with open("CLAUDE.md", "a", encoding="utf-8") as f:
        f.write(f"

### Review {datetime.now()}
{review}")
    await m.answer("Анализ завершен и записан в CLAUDE.md")

async def main():
    await init_db()
    load_skills()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
