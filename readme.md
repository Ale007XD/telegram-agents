🚀 Multi-Agent Telegram Bot
Мультиагентный Telegram бот на aiogram 3.x с динамическими навыками, историей чатов, OpenRouter AI и автоматическим деплоем на VPS.

[

✨ Функции
🧠 Мультиагенты: Planner (Qwen 2.5) + Verifier (Gemma 2) + DeepSeek Fallback

💾 История чатов: Асинхронный SQLite с изоляцией по пользователям

⚡ Динамические навыки: Создание новых команд через /new_skill

🔄 Hot Reload: Перезагрузка навыков без остановки бота

🛡️ Rate-limit: 5 запросов/мин на пользователя

📊 Аналитика: Sentry + CLAUDE.md логи

🚀 CI/CD: Автоматический деплой на VPS через GitHub Actions

📋 Быстрый запуск (локально)
1. Клонирование и установка
bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
2. Настройка ключей (.env)
bash
cp .env.example .env
Отредактируйте .env:

text
TELEGRAM_TOKEN=your_bot_token_from_botfather
OPENROUTER_API_KEY=sk-or-v1-... (https://openrouter.ai)
ADMIN_ID=123456789  # Ваш Telegram ID
SENTRY_DSN=optional
3. Первый запуск
bash
docker-compose up -d
# или
python bot.py
🐳 Docker (рекомендуется)
bash
# Сборка и запуск
docker-compose up --build -d

# Логи
docker-compose logs -f bot

# Остановка
docker-compose down
🔧 GitHub Actions (VPS деплой)
1. Настройка секретов GitHub
Settings → Secrets and variables → Actions → Добавить:

Secret	Значение
VPS_HOST	your.server.ip
VPS_USER	root или ubuntu
SSH_PRIVATE_KEY	-----BEGIN OPENSSH PRIVATE KEY-----...
TELEGRAM_TOKEN	Токен бота
OPENROUTER_API_KEY	OpenRouter ключ
ADMIN_ID	Ваш Telegram ID
2. SSH ключ для VPS
bash
# На VPS
mkdir -p /app/bot && cd /app/bot
ssh-keygen -t rsa -b 4096 -f ssh_key
cat ssh_key.pub >> ~/.ssh/authorized_keys

# Скопируйте содержимое ssh_key в GitHub Secret SSH_PRIVATE_KEY
3. Автоматический деплой
bash
git push origin main  # Автоматический деплой на VPS!
🎮 Команды бота
Команда	Описание	Доступ
/start	Запуск и справка	Все
/plan задача	AI планировщик	Все
/travel	Пример навыка	Все
/review	Анализ истории	Все
/new_skill имя код	Создать навык	Admin
/reload	Перезагрузка	Admin
🏗️ Архитектура
text
bot.py ← Middleware ← Dynamic Skills (skills/*.py)
         ↓
Database (history.db) ← ChatMessage (user_id, role, content)
         ↓
Agents: Planner → Verifier → Fallback (OpenRouter API)
         ↓
CLAUDE.md (долгосрочная память + логи верификации)
📁 Структура проекта
text
├── bot.py                 # Основной цикл
├── database.py           # SQLAlchemy async
├── agents/base.py        # Мультиагенты
├── skills/               # Динамические навыки
│   ├── travel.py        # Пример
│   └── template.py      # Шаблон
├── CLAUDE.md            # Контекст проекта
├── history.db           # История (auto)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/deploy.yml
🔍 Создание нового навыка
Через Telegram (Admin):

text
/new_skill weather
from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("weather"))
async def cmd_weather(message: types.Message):
    await message.answer("🌤️ Погода загружается...")

def setup():
    return router

/reload
🐛 Troubleshooting
Проблема	Решение
ModuleNotFoundError	pip install -r requirements.txt
history.db не создается	chmod 777 .
Permission denied skills/	mkdir -p skills && chmod 777 skills
Бот не отвечает	Проверьте .env ключи
Деплой не работает	Проверьте SSH секреты GitHub
📈 Мониторинг
Sentry: Автоматические ошибки (если настроен SENTRY_DSN)

CLAUDE.md: Логи верификации агентов

Docker logs: docker-compose logs -f

База данных: sqlite3 history.db "SELECT * FROM history LIMIT 10"

🤝 Контрибьютинг
Форкните репозиторий

Создайте навык в skills/

Протестируйте локально: docker-compose up

Push и PR!

📄 Лицензия
MIT License. Используйте свободно!

Статус: Готов к продакшену 🚀
