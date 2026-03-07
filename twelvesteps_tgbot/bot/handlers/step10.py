from .shared import *

async def handle_day(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    current_state = await state.get_state()
    if current_state == StepState.answering or current_state == StepState.filling_template:
        await state.clear()
        logger.info(f"Cleared step state for user {telegram_id} when switching to /day")

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("❌ Ошибка аутентификации. Попробуй /start")
            return

        data = await BACKEND_CLIENT.start_step10_analysis(token)

        if not data:
            await message.answer("❌ Не удалось начать самоанализ. Попробуй позже.")
            return

        if data.get("is_resumed"):
            resume_text = f"⏸ Продолжаем с того места, где остановились.\n\n"
        else:
            resume_text = ""

        question_data = data.get("question_data", {})
        question_number = question_data.get("number", 1)
        question_text = question_data.get("text", "")
        question_subtext = question_data.get("subtext", "")

        question_msg = (
            f"{resume_text}"
            f"📘 Ежедневный самоанализ (10 шаг)\n\n"
            f"Вопрос {question_number}/10:\n"
            f"{question_text}\n"
        )
        if question_subtext:
            question_msg += f"\n{question_subtext}\n"

        await state.set_state(Step10States.answering_question)
        await state.update_data(
            step10_analysis_id=data.get("analysis_id"),
            step10_current_question=question_number,
            step10_is_complete=data.get("is_complete", False)
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏸ Пауза", callback_data="step10_pause")],
            [InlineKeyboardButton(text="◀️", callback_data="step10_back")]
        ])

        await send_long_message(message, question_msg, reply_markup=markup)

    except Exception as exc:
        logger.exception("Failed to start step10 analysis: %s", exc)
        error_text = (
            "❌ Не удалось начать самоанализ.\n\n"
            "Произошла ошибка. Хочешь начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())

async def handle_step10_answer(message: Message, state: FSMContext) -> None:
    """Обработка ответа на вопрос самоанализа по 10 шагу"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    answer_text = message.text

    if not answer_text or not answer_text.strip():
        await message.answer("Пожалуйста, напиши ответ на вопрос.")
        return

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("❌ Ошибка аутентификации.")
            await state.clear()
            return

        state_data = await state.get_data()
        current_question = state_data.get("step10_current_question", 1)

        data = await BACKEND_CLIENT.submit_step10_answer(
            token, current_question, answer_text
        )

        if not data or not data.get("success"):
            error_msg = data.get("error", "Не удалось сохранить ответ. Попробуй позже.")
            await message.answer(f"❌ {error_msg}")
            return

        if data.get("is_complete"):
            await state.clear()
            completion_msg = (
                "✅ Самоанализ за сегодня завершён!\n\n"
                "Спасибо. Самоанализ за сегодня завершён, жду тебя завтра."
            )
            await message.answer(completion_msg, reply_markup=build_main_menu_markup())
            return

        next_question_data = data.get("next_question_data", {})
        if not next_question_data:
            await message.answer("❌ Ошибка: не удалось получить следующий вопрос.")
            await state.clear()
            return

        next_question_number = next_question_data.get("number", current_question + 1)
        next_question_text = next_question_data.get("text", "")
        next_question_subtext = next_question_data.get("subtext", "")

        await state.update_data(
            step10_current_question=next_question_number
        )

        next_question_msg = (
            f"📘 Ежедневный самоанализ (10 шаг)\n\n"
            f"Вопрос {next_question_number}/10:\n"
            f"{next_question_text}\n"
        )
        if next_question_subtext:
            next_question_msg += f"\n{next_question_subtext}\n"

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏸ Пауза", callback_data="step10_pause")],
            [InlineKeyboardButton(text="◀️", callback_data="step10_back")]
        ])

        await send_long_message(message, next_question_msg, reply_markup=markup)

    except Exception as exc:
        logger.exception("Failed to submit step10 answer: %s", exc)
        await message.answer("❌ Произошла ошибка. Попробуй позже.")

async def handle_step10_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Обработка callback для Step 10 (пауза и т.д.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        await callback.answer()

        if data == "step10_pause":
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if not token:
                await callback.message.answer("❌ Ошибка аутентификации.")
                return

            pause_data = await BACKEND_CLIENT.pause_step10_analysis(token)

            if not pause_data or not pause_data.get("success"):
                error_msg = pause_data.get("error", "Не удалось поставить на паузу.")
                await callback.message.answer(f"❌ {error_msg}")
                return

            await state.clear()

            pause_msg = (
                f"⏸ Самоанализ поставлен на паузу.\n\n"
                f"{pause_data.get('resume_info', '')}\n\n"
                f"При следующем входе в раздел «📖 Самоанализ» сможешь продолжить с того же места."
            )
            await callback.message.answer(pause_msg, reply_markup=build_main_menu_markup())

    except Exception as exc:
        logger.exception("Failed to handle step10 callback: %s", exc)
        await callback.message.answer("❌ Произошла ошибка. Попробуй позже.")

