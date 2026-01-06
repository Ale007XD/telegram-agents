from aiogram import Router, types
from aiogram.filters import Command

router = Router()

@router.message(Command("template"))
async def cmd_template(message: types.Message):
    await message.answer("Это шаблонный навык!")

def setup():
    return router
