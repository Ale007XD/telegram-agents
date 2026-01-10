import os
import sys
import signal
import importlib
import logging
import sentry_sdk
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types, BaseMiddleware
from aiogram.filters import Command, BaseFilter
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from database import init_db, save_message, get_user_context
from agents.base import Planner, Verifier

# --- Конфигурация ---
load_dotenv()
sentry_sdk.init(dsn=os.getenv("SENTRY_DSN", ""))
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

bot = Bot(token=os.getenv("TELEGRAM_TOKEN"))
dp = Dispatcher(storage=MemoryStorage())
planner = Planner(os.getenv("OPENROUTER_API_KEY"))
verifier = Verifier(os.getenv("OPENROUTER_API_KEY"))

# Глобальное хранилище метаданных навыков для меню
# Формат: [{"name": "travel", "description": "✈️ Путешествия", "command": "/travel"}]
REGISTERED_SKILLS = []

# --- Middleware & Filters ---
class AdminFilter(BaseFilter):
    async def __call__(self, m: types.Message) -> bool:
        return str(m.from_user.id) == os.getenv("ADMIN_ID")

class HistoryMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        if isinstance(event, types.Message) and event.text and not event.text.startswith('/'):
            await save_message(event.from_user.id, "user", event.text)
        return await handler(event, data)

dp.message.outer_middleware(HistoryMiddleware())

# --- Логика загрузки навыков ---
def load_skills():
    global REGISTERED_SKILLS
    REGISTERED_SKILLS = []
    dp.sub_routers.clear()
    
    if not os.path.exists("skills"): os.makedirs("skills")
    
    for f in os.listdir("skills"):
        if f.endswith(".py") and not f.startswith("__"):
            try:
                module_name = f"skills.{f[:-3]}"
                
                # Полная очистка модуля для корректной перезагрузки
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                mod = importlib.import_module(module_name)
                
                # 1. Регистрация роутера
                if hasattr(mod, "setup"): 
                    dp.include_router(mod.setup())
                    logging.info(f"✅ Loaded router: {module_name}")
                
                # 2. Сбор метаданных для меню
                # Ищем переменную SKILL_METADATA = {"name": "...", "desc": "..."}
                if hasattr(mod, "SKILL_METADATA"):
                    meta = mod.SKILL_METADATA
                    REGISTERED_SKILLS.append(meta)
                else:
                    # Если метаданных нет, пробуем угадать из имени файла
                    cmd = f"/{f[:-3]}"
                    REGISTERED_SKILLS.append({
                        "name": f[:-3],
                        "desc": f"🛠 {f[:-3].capitalize()}",
                        "command": cmd
                    })
                    
            except Exception as e:
                logging.error(f"❌ Error loading {f}: {e}")
    
    # Сортируем навыки по алфавиту для красоты
    REGISTERED_SKILLS.sort(key=lambda x: x["name"])
    logging.info(f"Total skills: {len(REGISTERED_SKILLS)}")

# --- Хендлеры ---

@dp.message(Command("start"))
async def cmd_start(m: types.Message):
    # Динамическое построение меню
    builder = InlineKeyboardBuilder()
    
    text = "🤖 <b>Мульти-Агентный Бот</b>\n\nВыберите навык из списка ниже:"
    
    # Добавляем кнопки для каждого загруженного навыка
    for skill in REGISTERED_SKILLS:
        # command может быть просто строкой "/travel"
        # Для кнопок используем callback, если это не ссылка
        # Но проще написать команду в чат, если нажать кнопку (switch_inline_query) или просто callback
        # Здесь мы сделаем кнопки, которые пишут команду за юзера (через callback hack или просто описание)
        
        # Вариант А: Кнопка-ссылка (неудобно)
        # Вариант Б: Callback, который триггерит команду
        builder.button(text=skill["desc"], callback_data=f"cmd_{skill['name']}")
    
    builder.adjust(2) # По 2 кнопки в ряд
    
    # Системные кнопки
    sys_builder = InlineKeyboardBuilder()
    sys_builder.button(text="🔄 Обновить навыки", callback_data="sys_reload")
    if str(m.from_user.id) == os.getenv("ADMIN_ID"):
        sys_builder.button(text="📝 Создать навык", callback_data="sys_new_skill_hint")
    
    builder.attach(sys_builder)
    
    await m.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")

# Обработка нажатий на кнопки меню (эмуляция команд)
@dp.callback_query(lambda c: c.data.startswith("cmd_"))
async def handle_menu_click(callback: types.CallbackQuery):
    skill_name = callback.data.split("_")[1]
    # Ищем метаданные
    skill = next((s for s in REGISTERED_SKILLS if s["name"] == skill_name), None)
    
    if skill:
        # Отправляем сообщение как будто юзер написал команду
        # Это хак, но он работает для триггера хендлеров
        # Лучше просто подсказать команду
        await callback.message.answer(f"Запускаю {skill['desc']}...\nВведите: {skill['command']}")
    else:
        await callback.answer("Навык не найден", show_alert=True)

@dp.callback_query(lambda c: c.data == "sys_reload")
async def callback_reload(c: types.CallbackQuery):
    if str(c.from_user.id) != os.getenv("ADMIN_ID"):
        return await c.answer("Только для админа", show_alert=True)
    load_skills()
    await c.answer("Навыки обновлены!")
    await cmd_start(c.message) # Обновляем меню

@dp.callback_query(lambda c: c.data == "sys_new_skill_hint")
async def callback_new_skill(c: types.CallbackQuery):
    await c.message.answer("Используйте: <code>/new_skill name code</code>", parse_mode="HTML")

# Стандартные команды
@dp.message(Command("plan"))
async def handle_plan(m: types.Message):
    task = m.text.replace("/plan", "").strip()
    if not task: return await m.answer("Укажите задачу.")
    history = await get_user_context(m.from_user.id)
    plan = await planner.process(task, history)
    await m.answer(f"📋 <b>План:</b>\n{plan}", parse_mode="HTML")

@dp.message(Command("new_skill"), AdminFilter())
async def handle_new_skill(m: types.Message):
    try:
        parts = m.text.split(maxsplit=2)
        if len(parts) < 3: return await m.answer("Ошибка формата")
        filename, code = parts[1], parts[2]
        if not filename.endswith(".py"): filename += ".py"
        with open(f"skills/{filename}", "w", encoding="utf-8") as f: f.write(code)
        await m.answer(f"✅ Создан {filename}. Нажмите 'Обновить навыки'.")
    except Exception as e:
        await m.answer(f"Error: {e}")

@dp.message(Command("reload"), AdminFilter())
async def handle_reload(m: types.Message):
    load_skills()
    await m.answer("🔄 Перезагружено.")

# --- Запуск ---
async def main():
    await init_db()
    load_skills()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    def signal_handler(sig, frame):
        sys.exit(0)
    signal.signal(signal.SIGTERM, signal_handler)
    asyncio.run(main())
