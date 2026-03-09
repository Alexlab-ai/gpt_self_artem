# twelvesteps_tgbot/bot/handlers/steps.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from ..backend import get_step_service, get_profile_service

router = Router()

@router.message(F.text == "Работа по шагам")
async def start_steps(message: Message):
    user_id = message.from_user.id
    recommended = await get_step_service().recommend_step(user_id)
    text = f"Рекомендую начать/продолжить с Шага {recommended}. Выбери шаг:"
    # клавиатура с шагами 1-12 + "Повторить предыдущий"
    await message.answer(text, reply_markup=steps_keyboard)

@router.callback_query(F.data.startswith("step:"))
async def process_step(callback: CallbackQuery):
    # логика показа введения, вопросов, прогресс-бара
    pass  # реализуй по аналогии с твоим текущим кодом

@router.message(F.text)  # обработка ответа на вопрос шага
async def handle_step_answer(message: Message):
    # ... получить текущий вопрос/шаг из состояния
    result = await get_step_service().process_answer(
        message.from_user.id, current_step, current_question, message.text
    )
    await message.answer(result["feedback"])
    # Если есть theme → кнопка "Обновить профиль?"
