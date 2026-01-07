import os
from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем наш класс Planner
from agents.base import Planner

# Создаем состояния
class TravelStates(StatesGroup):
    waiting_for_city = State()

router = Router()

# Инициализируем агента (берем ключ из переменных окружения)
# Это сработает, так как .env загружен в процессе бота
planner_agent = Planner(os.getenv("OPENROUTER_API_KEY"))

@router.message(Command("travel"))
async def start_travel(message: types.Message, state: FSMContext):
    await message.answer("✈️ **Тревел-агент готов!**\nНапишите город или страну, куда планируете поездку.", parse_mode="Markdown")
    await state.set_state(TravelStates.waiting_for_city)

@router.message(TravelStates.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    city = message.text
    status_msg = await message.answer(f"⏳ Составляю план путешествия в **{city}**... Это займет около 10-15 секунд.", parse_mode="Markdown")
    
    try:
        # Формируем промпт для AI
        task = f"Составь краткий туристический план на 3 дня для поездки в {city}. Включи главные достопримечательности и местную еду."
        
        # Вызываем агента (историю передаем пустую, так как это новый запрос)
        ai_response = await planner_agent.process(task, [])
        
        # Удаляем сообщение "Загрузка..." и отправляем результат
        await status_msg.delete()
        await message.answer(f"🌍 **Ваш план для {city}:**\n\n{ai_response}", parse_mode="Markdown")
        
    except Exception as e:
        await message.answer(f"❌ Произошла ошибка при генерации: {e}")
    
    # Сбрасываем состояние
    await state.clear()

def setup():
    return router
