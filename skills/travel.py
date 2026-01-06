from aiogram import Router, types
from aiogram.filters import Command

router = Router(name="travel")

@router.message(Command("travel"))
async def cmd_travel(message: types.Message):
    await message.answer("✈️ Планировщик путешествий.\nНапишите город назначения.")

def setup():
    return router
