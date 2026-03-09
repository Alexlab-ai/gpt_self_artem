# twelvesteps_tgbot/bot/handlers/steps.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from ..backend import get_step_service, get_profile_service, get_tracker_service  # предполагаем импорты из backend
from ..config import steps_keyboard  # твоя клавиатура для шагов (1-12 + повтор)

router = Router()

class StepStates(StatesGroup):
    selecting_step = State()
    answering_question = State()

@router.message(Command(commands=["steps"]))  # или F.text == "Работа по шагам"
async def start_steps(message: Message, state: FSMContext):
    user_id = message.from_user.id
    recommended = await get_step_service().recommend_step(user_id)  # новая рекомендация
    text = f"Рекомендую начать/продолжить с Шага {recommended}, но можешь выбрать любой (как в АН).\nВыбери шаг:"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Шаг {i}", callback_data=f"step:{i}") for i in range(1, 13)],
        [InlineKeyboardButton(text="Повторить предыдущий", callback_data="step:repeat")]
    ])
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(StepStates.selecting_step)

@router.callback_query(F.data.startswith("step:"))
async def process_step_selection(callback: CallbackQuery, state: FSMContext):
    step_id = callback.data.split(":")[1]
    if step_id == "repeat":
        step_id = await get_step_service().get_last_completed_step(callback.from_user.id) or 1
    await state.update_data(current_step=step_id)

    # Показать введение + персонализация
    intro = await get_step_service().get_step_intro(step_id, callback.from_user.id)  # добавь метод в service, если нужно
    progress = await get_step_service().get_progress(callback.from_user.id, step_id)  # "Вопрос 5/10 | Общий: 25%"
    await callback.message.answer(f"Шаг {step_id}: {intro}\nПрогресс: {progress}")

    # Получить следующий вопрос
    next_question = await get_step_service().get_next_question(callback.from_user.id, step_id)
    await callback.message.answer(next_question["text"])
    await state.set_state(StepStates.answering_question)
    await callback.answer()

@router.message(StepStates.answering_question)
async def handle_step_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    step_id = data["current_step"]
    question_id = data.get("current_question_id")  # предполагаем, что сохранили

    # Проверить лимит токенов
    if not await get_step_service().check_token_limit(message.from_user.id, "step"):
        await message.answer("Лимит исчерпан (1 в день на PRO). Переходим на GPT-3.5 или ULTRA?")
        # fallback модель

    # Обработать ответ
    result = await get_step_service().process_answer(
        message.from_user.id, step_id, question_id, message.text
    )
    await message.answer(result["feedback"])

    # Предложения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    if result.get("profile_theme"):
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"Обновить раздел '{result['profile_theme']}' в профиле?", callback_data="update_profile")])
    keyboard.inline_keyboard.append([InlineKeyboardButton(text="Запустить трекер чувств?", callback_data="tracker_feeling")])
    await message.answer("Что дальше?", reply_markup=keyboard)

    # Если шаг завершён
    if await get_step_service().is_step_complete(message.from_user.id, step_id):
        summary = await get_step_service().complete_step(message.from_user.id, step_id)
        await message.answer(summary["summary"])

    await state.clear()  # или переход к следующему вопросу

@router.callback_query(F.data == "update_profile")
async def suggest_profile_update(callback: CallbackQuery):
    # Логика перехода в профиль (вызов profile handlers)
    await callback.message.answer("Переходим в 'Рассказать о себе'...")
    await callback.answer()

@router.callback_query(F.data == "tracker_feeling")
async def launch_tracker_feeling(callback: CallbackQuery):
    # Вызов трекера
    await get_tracker_service().start_feeling_tracker(callback.from_user.id)
    await callback.message.answer("Запустили трекер чувств...")
    await callback.answer()
