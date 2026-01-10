import os
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Импортируем агента и работу с БД
from agents.base import Planner
from database import save_message, get_user_context

# --- МЕТАДАННЫЕ ---
SKILL_METADATA = {
    "name": "taro",
    "desc": "🔮 AI-Репетитор Таро",
    "command": "/taro"
}

router = Router()
# Используем существующий ключ API
agent = Planner(os.getenv("OPENROUTER_API_KEY"))

# --- ТЕМАТИЧЕСКИЙ ПЛАН ---
TOPICS = {
    "intro": [
        "История и суть карт Таро (Райдер-Уайт)",
        "Структура колоды: Старшие и Младшие арканы",
        "Базовая символика: цвета, позы, элементы",
        "Подготовка к гаданию: настройка и тасовка",
        "Как читать карты: интуиция против зубрежки"
    ],
    "minor": [
        "Масть Жезлов: Огонь и Действие",
        "Масть Кубков: Вода и Чувства",
        "Масть Мечей: Воздух и Разум",
        "Масть Пентаклей: Земля и Ресурсы",
        "Придворные карты: Пажи, Рыцари, Королевы, Короли"
    ],
    "major": [
        "Путь Шута: Арканы 0-5 (Становление)",
        "Социализация: Арканы 6-10 (Выбор и Судьба)",
        "Темная ночь души: Арканы 11-15 (Испытания)",
        "Просветление: Арканы 16-21 (Освобождение)"
    ],
    "practice": [
        "Расклад 'Три карты': Прошлое, Настоящее, Будущее",
        "Расклад 'Выбор': Анализ двух вариантов",
        "Этика таролога: что можно и нельзя говорить"
    ]
}

# --- СОСТОЯНИЯ ---
class TaroStates(StatesGroup):
    menu = State()
    lesson_active = State()

# --- КЛАВИАТУРЫ ---
def get_main_menu():
    builder = InlineKeyboardBuilder()
    buttons = [
        ("👶 Введение", "topic_intro"),
        ("⚔️ Младшие Арканы", "topic_minor"),
        ("🌟 Старшие Арканы", "topic_major"),
        ("🃏 Практика", "topic_practice")
    ]
    for text, cb in buttons:
        builder.button(text=text, callback_data=cb)
    builder.adjust(2)
    return builder.as_markup()

def get_nav_keyboard(section_key, idx, total):
    builder = InlineKeyboardBuilder()
    if idx > 0: builder.button(text="⬅️ Назад", callback_data=f"nav_{section_key}_{idx-1}")
    if idx < total - 1: builder.button(text="Вперед ➡️", callback_data=f"nav_{section_key}_{idx+1}")
    
    builder.button(text="❓ Задать вопрос", callback_data="ask_hint")
    builder.button(text="🔝 Меню", callback_data="taro_menu")
    
    if idx > 0 and idx < total - 1: builder.adjust(2, 1, 1)
    else: builder.adjust(1, 1, 1)
    return builder.as_markup()

# --- ЛОГИКА ГЕНЕРАЦИИ ---
async def generate_lesson_content(user_id: int, topic: str):
    # Промпт настроен так, чтобы минимизировать ошибки разметки
    prompt = (
        f"Ты учитель Таро. Тема урока: '{topic}'.\n"
        f"1. Объясни суть кратко (до 250 слов).\n"
        f"2. Приведи пример.\n"
        f"3. Используй ТОЛЬКО безопасный Markdown: жирный шрифт (**текст**) и списки (- пункт).\n"
        f"4. НЕ используй символы '_', '`', '[', ']' чтобы не ломать парсинг Telegram."
    )
    
    try:
        content = await agent.process(prompt, [])
    except Exception as e:
        content = f"Ошибка генерации: {e}"
        
    await save_message(user_id, "assistant", f"Урок '{topic}':\n{content}")
    return content

# --- ХЕНДЛЕРЫ ---

@router.message(Command("taro"))
async def start_taro(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🔮 <b>AI-Школа Таро</b>\nЯ генерирую уроки персонально для вас.\nВыберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "taro_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🔮 <b>AI-Школа Таро</b>\nВыберите раздел:",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("topic_"))
async def open_section(callback: types.CallbackQuery, state: FSMContext):
    section_key = callback.data.split("_")[1]
    await run_lesson(callback, section_key, 0, state)

@router.callback_query(F.data.startswith("nav_"))
async def navigation(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        idx = int(parts[-1])
        section_key = "_".join(parts[1:-1])
        await run_lesson(callback, section_key, idx, state)
    except Exception as e:
        await callback.answer(f"Ошибка: {e}")

async def run_lesson(callback: types.CallbackQuery, section_key: str, idx: int, state: FSMContext):
    topics_list = TOPICS.get(section_key)
    if not topics_list: return
    
    current_topic = topics_list[idx]
    
    # 1. Показываем статус "Печатает..."
    await callback.message.edit_text(
        f"⏳ <b>Генерирую урок:</b> {current_topic}...\nПодождите пару секунд.",
        parse_mode="HTML"
    )
    
    # 2. Генерируем контент
    content = await generate_lesson_content(callback.from_user.id, current_topic)
    
    # 3. Отправляем (С ЗАЩИТОЙ ОТ ОШИБОК РАЗМЕТКИ)
    try:
        # Попытка 1: Красивый Markdown
        await callback.message.edit_text(
            f"🎓 *Тема: {current_topic}* ({idx+1}/{len(topics_list)})\n\n{content}",
            reply_markup=get_nav_keyboard(section_key, idx, len(topics_list)),
            parse_mode="Markdown"
        )
    except Exception:
        # Попытка 2: Если Markdown сломан, отправляем чистый текст (без parse_mode)
        # Убираем возможные теги из заголовка для чистоты
        clean_text = f"🎓 Тема: {current_topic} ({idx+1}/{len(topics_list)})\n\n{content}"
        await callback.message.edit_text(
            clean_text,
            reply_markup=get_nav_keyboard(section_key, idx, len(topics_list)),
            parse_mode=None # Безопасный режим
        )
    
    await state.set_state(TaroStates.lesson_active)

@router.callback_query(F.data == "ask_hint")
async def ask_hint_callback(callback: types.CallbackQuery):
    await callback.answer("Напишите ваш вопрос в чат!", show_alert=True)

@router.message(TaroStates.lesson_active)
async def handle_student_question(message: types.Message):
    user_id = message.from_user.id
    history = await get_user_context(user_id, limit=6)
    
    wait = await message.answer("🤔 ...")
    
    try:
        answer = await agent.process(message.text, history)
        # Тоже защищаем от ошибок разметки
        try:
            await wait.edit_text(f"💁‍♂️ **Ответ:**\n{answer}", parse_mode="Markdown")
        except:
            await wait.edit_text(f"💁‍♂️ Ответ:\n{answer}", parse_mode=None)
            
        await save_message(user_id, "assistant", answer)
    except Exception as e:
        await wait.edit_text(f"Ошибка: {e}")

def setup():
    return router
