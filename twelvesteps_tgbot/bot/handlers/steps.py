from typing import Optional
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    TOKEN_STORE,
    get_or_fetch_token,
    get_current_step_question,
    process_step_message,
)
from bot.config import (
    format_step_progress_indicator,
    build_exit_markup,
    build_main_menu_markup,
    build_error_markup,
    build_root_menu_markup,
    build_steps_list_markup,
    build_step_questions_markup,
    build_step_actions_markup,
    build_step_answer_mode_markup,
    build_template_selection_markup,
    build_template_filling_markup,
    build_steps_settings_markup,
    build_template_selection_settings_markup,
    build_progress_step_markup,
    build_progress_main_markup,
    build_progress_view_answers_steps_markup,
    build_progress_view_answers_questions_markup,
    build_progress_questions_group_markup,
    build_settings_steps_list_markup,
    build_settings_questions_list_markup,
    build_settings_select_step_for_question_markup,
    build_questions_group_markup,
    _clean_step_title,
)
from bot.utils import send_long_message, edit_long_message
from .shared import StepState, MAIN_MENU_TEXT, logger

async def handle_steps(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Сначала нажми /start для авторизации.")
            return

        templates_data = await BACKEND_CLIENT.get_templates(token)
        active_template_id = templates_data.get("active_template_id")

        if active_template_id is None:
            templates = templates_data.get("templates", [])
            author_template = None
            for template in templates:
                if template.get("template_type") == "AUTHOR":
                    author_template = template
                    break

            if author_template:
                await BACKEND_CLIENT.set_active_template(token, author_template.get("id"))

        step_info = await BACKEND_CLIENT.get_current_step_info(token)
        step_number = step_info.get("step_number")

        if step_number:
            progress_indicator = format_step_progress_indicator(
                step_number=step_number,
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            )

            step_data = await get_current_step_question(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )

            if step_data:
                response_text = step_data.get("message", "")
                is_completed = step_data.get("is_completed", False)

                if is_completed:
                    await message.answer("🎉 Ты уже прошел все доступные шаги!", reply_markup=build_main_menu_markup())
                    await state.clear()
                    return

                if response_text:
                    step_id = step_info.get("step_id")
                    question_id = None
                    template_progress = None

                    try:
                        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                        questions = questions_data.get("questions", [])
                        answered_count = step_info.get("answered_questions", 0)
                        if questions and answered_count < len(questions):
                            current_question = questions[answered_count]
                            question_id = current_question.get("id")

                            if step_id and question_id:
                                progress_data = await BACKEND_CLIENT.get_template_progress(token, step_id, question_id)
                                if progress_data and progress_data.get("status") in ["IN_PROGRESS", "PAUSED"]:
                                    template_progress = progress_data
                    except Exception as e:
                        logger.warning(f"Failed to check template progress: {e}")

                    full_text = f"{progress_indicator}\n\n{response_text}"

                    if template_progress:
                        full_text = f"{progress_indicator}\n\nЕсть сохранённый прогресс · {template_progress.get('progress_summary', '')}\n\n{response_text}"


                    await state.update_data(
                        step_description=step_info.get("step_description", ""),
                        nav_level="question",
                    )

                    await send_long_message(
                        message,
                        full_text,
                        reply_markup=build_step_actions_markup(has_template_progress=bool(template_progress))
                    )
                    await state.set_state(StepState.answering)
                else:
                    step_description = step_info.get("step_description", "")
                    full_text = progress_indicator
                    if step_description:
                        full_text += f"\n\n{step_description}"

                    await send_long_message(
                        message,
                        full_text,
                        reply_markup=build_step_actions_markup()
                    )
            else:
                step_description = step_info.get("step_description", "")
                full_text = progress_indicator
                if step_description:
                    full_text += f"\n\n{step_description}"

                await send_long_message(
                    message,
                    full_text,
                    reply_markup=build_step_actions_markup()
                )
        else:
            step_data = await get_current_step_question(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )

            if not step_data:
                await message.answer("Сначала нажми /start для авторизации.")
                return

            response_text = step_data.get("message", "")
            is_completed = step_data.get("is_completed", False)

            if is_completed:
                await message.answer("🎉 Ты уже прошел все доступные шаги!", reply_markup=build_main_menu_markup())
                await state.clear()
                return

            if response_text:
                await state.set_state(StepState.answering)
                await send_long_message(message, response_text, reply_markup=build_exit_markup())

    except Exception as exc:
        logger.exception("Error fetching steps for %s: %s", telegram_id, exc)
        await message.answer("Ошибка сервера. Попробуй позже.")
        return

async def handle_step_answer_mode(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    user_text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        action = state_data.get("action")

        if action == "save_draft":
            if len(user_text.strip()) < 5:
                await message.answer(
                    "⚠️ Слишком короткий текст. Минимум 5 символов.",
                    reply_markup=build_step_answer_mode_markup()
                )
                return
            logger.info(f"Saving draft for user {telegram_id}, text length: {len(user_text)}")
            save_result = await BACKEND_CLIENT.save_draft(token, user_text)
            logger.info(f"Draft save result for user {telegram_id}: {save_result}")
            await state.update_data(action=None, current_draft=user_text)

            step_info = await BACKEND_CLIENT.get_current_step_info(token)

            try:
                question_id_data = await BACKEND_CLIENT.get_current_question_id(token)
                question_id = question_id_data.get("question_id")

                response_text = ""
                if question_id:
                    step_id = step_info.get("step_id")
                    if step_id:
                        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                        questions = questions_data.get("questions", []) if questions_data else []
                        for q in questions:
                            if q.get("id") == question_id:
                                response_text = q.get("text", "")
                                break
            except Exception as e:
                logger.warning(f"Failed to get current question text: {e}")
                response_text = ""

            if step_info.get("step_number") and response_text:
                progress_indicator = format_step_progress_indicator(
                    step_number=step_info.get("step_number"),
                    total_steps=step_info.get("total_steps", 12),
                    step_title=step_info.get("step_title"),
                    answered_questions=step_info.get("answered_questions", 0),
                    total_questions=step_info.get("total_questions", 0)
                )

            await message.answer(
                "✅ Черновик сохранён!",
                reply_markup=build_step_answer_mode_markup()
            )
            return

        if action == "edit_answer":
            state_data = await state.get_data()
            question_id_to_edit = state_data.get("current_question_id")

            if not question_id_to_edit:
                await message.answer("Ошибка: не найден вопрос для редактирования. Начни заново.")
                await state.clear()
                return

            current_question_id = None
            try:
                current_question_id_data = await BACKEND_CLIENT.get_current_question_id(token)
                current_question_id = current_question_id_data.get("question_id")
            except Exception:
                pass

            try:
                await BACKEND_CLIENT.switch_to_question(token, question_id_to_edit)
            except Exception as e:
                logger.warning(f"Failed to switch to question {question_id_to_edit}: {e}")

            step_next = await process_step_message(
                telegram_id=telegram_id,
                text=user_text,
                username=username,
                first_name=first_name
            )

            if current_question_id and current_question_id != question_id_to_edit:
                try:
                    await BACKEND_CLIENT.switch_to_question(token, current_question_id)
                except Exception as e:
                    logger.warning(f"Failed to restore to question {current_question_id}: {e}")

            if not step_next:
                await message.answer("Сессия потеряна. Нажми /steps снова.")
                await state.clear()
                return

            if step_next.get("error"):
                error_message = step_next.get("message", "Ошибка валидации")
                await message.answer(
                    f"{error_message}\n\n"
                    "Попробуй ещё раз:",
                    reply_markup=build_step_answer_mode_markup()
                )
                return

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            response_text = step_next.get("message", "Ответ обновлён.")
            is_completed = step_next.get("is_completed", False)

            if step_info.get("step_number"):
                progress_indicator = format_step_progress_indicator(
                    step_number=step_info.get("step_number", 0),
                    total_steps=step_info.get("total_steps", 12),
                    step_title=step_info.get("step_title"),
                    answered_questions=step_info.get("answered_questions", 0),
                    total_questions=step_info.get("total_questions", 0)
                )
                full_response = f"{progress_indicator}\n\n✅ Ответ обновлён!\n\n{response_text}"
            else:
                full_response = f"✅ Ответ обновлён!\n\n{response_text}"

            await send_long_message(message, full_response, reply_markup=build_step_actions_markup())
            await state.update_data(action=None, current_question_id=None)
            await state.set_state(StepState.answering)

            if is_completed:
                await message.answer("Этап завершен! 🎉 Возвращаю в обычный режим.", reply_markup=build_main_menu_markup())
                await state.clear()
            return

        if action == "complete":
            step_next = await process_step_message(
                telegram_id=telegram_id,
                text=user_text,
                username=username,
                first_name=first_name
            )

            if not step_next:
                await message.answer("Сессия потеряна. Нажми /steps снова.")
                await state.clear()
                return

            if step_next.get("error"):
                error_message = step_next.get("message", "Ошибка валидации")
                error_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
                ])
                await message.answer(
                    f"{error_message}\n\n"
                    "Ответ должен быть достаточно подробным. Попробуй ещё раз:",
                    reply_markup=error_markup
                )
                return

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            response_text = step_next.get("message", "Ответ принят.")
            is_completed = step_next.get("is_completed", False)

            if step_info.get("step_number"):
                progress_indicator = format_step_progress_indicator(
                    step_number=step_info.get("step_number", 0),
                    total_steps=step_info.get("total_steps", 12),
                    step_title=step_info.get("step_title"),
                    answered_questions=step_info.get("answered_questions", 0),
                    total_questions=step_info.get("total_questions", 0)
                )
                full_response = f"{progress_indicator}\n\n{response_text}"
            else:
                full_response = response_text

            state_data = await state.get_data()
            if state_data.get("action") == "complete":
                complete_result_markup = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
                ])
                await send_long_message(message, full_response, reply_markup=complete_result_markup)
            else:
                await send_long_message(message, full_response, reply_markup=build_step_actions_markup())
            await state.update_data(action=None, current_draft="")
            await state.set_state(StepState.answering)

            if is_completed:
                await message.answer("Этап завершен! 🎉 Возвращаю в обычный режим.", reply_markup=build_main_menu_markup())
                await state.clear()
            return

        if len(user_text.strip()) < 5:
            await message.answer(
                "⚠️ Слишком короткий текст. Минимум 5 символов.",
                reply_markup=build_step_answer_mode_markup()
            )
            return

        logger.info(f"Auto-saving draft for user {telegram_id}, text length: {len(user_text)}")
        save_result = await BACKEND_CLIENT.save_draft(token, user_text)
        logger.info(f"Auto-save draft result for user {telegram_id}: {save_result}")
        await state.update_data(current_draft=user_text)
        await message.answer(
            "💾 Текст сохранён как черновик.",
            reply_markup=build_step_answer_mode_markup()
        )

    except Exception as exc:
        logger.exception("Error processing step answer mode: %s", exc)
        await message.answer("❌ Произошла ошибка. Попробуй ещё раз.")

async def handle_step_answer(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    user_text = message.text

    try:
        step_next = await process_step_message(
            telegram_id=telegram_id,
            text=user_text,
            username=username,
            first_name=first_name
        )

        if not step_next:
            await message.answer("Сессия потеряна. Нажми /steps снова.")
            await state.clear()
            return

        if step_next.get("error"):
            error_message = step_next.get("message", "Ошибка валидации")
            await message.answer(
                error_message,
                reply_markup=build_step_actions_markup()
            )
            return

        token = await get_or_fetch_token(telegram_id, username, first_name)
        step_info = await BACKEND_CLIENT.get_current_step_info(token) if token else {}

        response_text = step_next.get("message", "Ответ принят.")
        is_completed = step_next.get("is_completed", False)

        if step_info.get("step_number"):
            progress_indicator = format_step_progress_indicator(
                step_number=step_info.get("step_number", 0),
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            )
            full_response = f"{progress_indicator}\n\n{response_text}"

            await state.update_data(step_description=step_info.get("step_description", ""))
        else:
            full_response = response_text

        await send_long_message(message, full_response, reply_markup=build_step_actions_markup())

        if is_completed:
             await message.answer("Этап завершен! 🎉 Возвращаю в обычный режим.", reply_markup=build_main_menu_markup())
             await state.clear()

    except Exception as exc:
        logger.exception("Error processing step answer: %s", exc)
        error_text = (
            "❌ Произошла ошибка при сохранении ответа.\n\n"
            "Хочешь начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())

async def handle_about_step(message: Message, state: FSMContext) -> None:
    """Show description of current step"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Сначала нажми /start для авторизации.")
            return

        step_info = await BACKEND_CLIENT.get_current_step_info(token)

        if not step_info or not step_info.get("step_number"):
            await message.answer("У тебя нет активного шага. Нажми /steps, чтобы начать.")
            return

        step_number = step_info.get("step_number")
        step_title = step_info.get("step_title", f"Шаг {step_number}")
        step_description = step_info.get("step_description", "")
        total_steps = step_info.get("total_steps", 12)

        progress_indicator = format_step_progress_indicator(
            step_number=step_number,
            total_steps=total_steps,
            step_title=step_title,
            answered_questions=step_info.get("answered_questions", 0),
            total_questions=step_info.get("total_questions", 0)
        )

        about_text = f"📘 {progress_indicator}"
        if step_description:
            about_text += f"\n\n{step_description}"
        else:
            about_text += "\n\nОписание шага пока не добавлено."

        await send_long_message(
            message,
            about_text,
            reply_markup=build_step_actions_markup()
        )

    except Exception as exc:
        logger.exception("Error handling /about_step for %s: %s", telegram_id, exc)
        error_text = (
            "❌ Ошибка при получении информации о шаге.\n\n"
            "Хочешь начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())

async def handle_progress_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle progress view callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации")
            return
    except Exception as e:
        logger.exception("Error getting token: %s", e)
        await callback.answer("Ошибка авторизации")
        return

    logger.info("handle_progress_callback: data=%s, user=%s", data, telegram_id)

    if data == "progress_main" or data == "step_progress":
        try:
            logger.info("progress_main: fetching steps for user %s", telegram_id)
            steps_list = await BACKEND_CLIENT.get_steps_list(token)
            steps = steps_list.get("steps", []) if steps_list else []
            logger.info("progress_main: got %d steps", len(steps))

            try:
                await callback.message.edit_text(
                    "📋 Мой прогресс\n\nВыбери шаг, чтобы посмотреть свои ответы.",
                    reply_markup=build_progress_main_markup(steps)
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    logger.debug("progress_main: message not modified")
                else:
                    logger.exception("progress_main: edit_text failed: %s", e)
                    await callback.answer("Ошибка отображения")
        except Exception as e:
            logger.exception("progress_main: error loading steps: %s", e)
            await callback.answer("Ошибка загрузки")
        await callback.answer()
        return

    if data.startswith("progress_step_"):
        step_id = int(data.replace("progress_step_", ""))

        try:
            questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
            questions = questions_data.get("questions", []) if questions_data else []
            step_info = questions_data.get("step", {}) if questions_data else {}

            step_number = step_info.get("number", step_id)
            step_title = _clean_step_title(step_info.get("title", ""))

            await state.update_data(progress_view_step_id=step_id)

            await callback.message.edit_text(
                f"🪜 Шаг {step_number} — {step_title}\n\nВыбери вопрос:",
                reply_markup=build_progress_view_answers_questions_markup(questions, step_id, back_callback="progress_main")
            )
            await callback.answer()
        except Exception as e:
            logger.exception("Error loading questions for step %s: %s", step_id, e)
            await callback.answer("Ошибка загрузки вопросов")
        return

    if data == "progress_view_answers" or data.startswith("progress_answers_step_"):
        if data.startswith("progress_answers_step_"):
            step_id = int(data.replace("progress_answers_step_", ""))
        else:
            state_data = await state.get_data()
            step_id = state_data.get("progress_view_step_id")

        if step_id:
            try:
                questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                questions = questions_data.get("questions", []) if questions_data else []
                step_info = questions_data.get("step", {}) if questions_data else {}

                step_number = step_info.get("number", step_id)
                step_title = _clean_step_title(step_info.get("title", ""))

                await state.update_data(progress_view_step_id=step_id)

                await callback.message.edit_text(
                    f"🪜 Шаг {step_number} — {step_title}\n\nВыбери вопрос для просмотра ответа:",
                    reply_markup=build_progress_view_answers_questions_markup(questions, step_id)
                )
            except Exception as e:
                logger.exception("Error loading questions: %s", e)
                await callback.answer("Ошибка загрузки")
        else:
            try:
                steps_list = await BACKEND_CLIENT.get_steps_list(token)
                steps = steps_list.get("steps", []) if steps_list else []
                await callback.message.edit_text(
                    "📋 Мой прогресс\n\nВыбери шаг, чтобы посмотреть свои ответы.",
                    reply_markup=build_progress_main_markup(steps)
                )
            except Exception as e:
                logger.exception("Error loading steps: %s", e)
                await callback.answer("Ошибка загрузки")
        await callback.answer()
        return

    if data.startswith("progress_answers_question_"):
        question_id = int(data.replace("progress_answers_question_", ""))

        try:
            answer_data = await BACKEND_CLIENT.get_previous_answer(token, question_id)
            answer_text = answer_data.get("answer_text", "") if answer_data else ""

            state_data = await state.get_data()
            step_id_for_back = state_data.get("progress_view_step_id")

            current_question = None
            if step_id_for_back:
                questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id_for_back)
                questions = questions_data.get("questions", []) if questions_data else []
                for q in questions:
                    if q.get("id") == question_id:
                        current_question = q
                        break

            if not current_question:
                steps_list = await BACKEND_CLIENT.get_steps_list(token)
                steps = steps_list.get("steps", []) if steps_list else []

                for step in steps:
                    step_id = step.get("id")
                    questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                    questions = questions_data.get("questions", []) if questions_data else []

                    for q in questions:
                        if q.get("id") == question_id:
                            current_question = q
                            if not step_id_for_back:
                                step_id_for_back = step_id
                            break

                    if current_question:
                        break

            if current_question:
                question_text = current_question.get("text", "Вопрос")
            else:
                question_text = "Вопрос"

            if answer_text:
                display_text = (
                    f"📄 Ответ\n\n"
                    f"❓ {question_text}\n\n"
                    f"💬 Твой ответ:\n\n{answer_text}"
                )
            else:
                display_text = (
                    f"📄 Ответ\n\n"
                    f"❓ {question_text}\n\n"
                    f"💬 Ответ пока не сохранён."
                )

            back_button = [InlineKeyboardButton(text="◀️ Назад к вопросам", callback_data=f"progress_answers_step_{step_id_for_back}")] if step_id_for_back else []

            await callback.message.edit_text(
                display_text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_button] if back_button else [])
            )
        except Exception as e:
            logger.exception("Error loading answer: %s", e)
            await callback.answer("Ошибка загрузки ответа")
        await callback.answer()
        return

    await callback.answer()

async def handle_template_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle template selection callback"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data == "template_author":
            templates_data = await BACKEND_CLIENT.get_templates(token)
            templates = templates_data.get("templates", [])

            logger.info(f"Templates received: {len(templates)} templates")
            for t in templates:
                logger.info(f"Template: id={t.get('id')}, name={t.get('name')}, type={t.get('template_type')}")

            author_template = None
            for template in templates:
                template_type = template.get("template_type")
                if template_type == "AUTHOR" or (hasattr(template_type, 'value') and template_type.value == "AUTHOR"):
                    author_template = template
                    break

            if author_template:
                await BACKEND_CLIENT.set_active_template(token, author_template.get("id"))
                await callback.answer("✅ Авторский шаблон выбран")

                step_info = await BACKEND_CLIENT.get_current_step_info(token)

                if step_info:
                    step_number = step_info.get("step_number")
                    step_title = step_info.get("step_title") or step_info.get("step_description") or (f"Шаг {step_number}" if step_number else "Шаг")
                    total_steps = step_info.get("total_steps", 12)

                    if step_number is not None and total_steps is not None:
                        progress_bar = "█" * step_number + "░" * (total_steps - step_number)
                        progress_text = f"Шаг {step_number}/{total_steps}\n{progress_bar}"
                    else:
                        progress_text = "Начинаем работу по шагам..."

                    step_next = await BACKEND_CLIENT.get_next_step(token)

                    if step_next:
                        is_completed = step_next.get("is_completed", False)
                        question_text = step_next.get("message", "")

                        if is_completed or not question_text or question_text == "Program completed.":
                            await edit_long_message(
                                callback,
                                f"✅ Шаблон выбран!\n\n{progress_text}\n\n"
                                "⚠️ В базе данных пока нет шагов или вопросов.\n\n"
                                "Обратитесь к администратору для настройки шагов программы.",
                                reply_markup=None
                            )
                        else:
                            await edit_long_message(
                                callback,
                                f"✅ Шаблон выбран!\n\n{progress_text}\n\n📘 {step_title}\n\n{question_text}",
                                reply_markup=build_step_actions_markup()
                            )
                            await state.set_state(StepState.answering)
                    else:
                        await edit_long_message(
                            callback,
                            f"✅ Шаблон выбран!\n\n{progress_text}\n\n📘 {step_title}\n\nНачинаем работу по шагу...",
                            reply_markup=build_step_actions_markup()
                        )
                        await state.set_state(StepState.answering)
                else:
                    await edit_long_message(
                        callback,
                        "✅ Выбран авторский шаблон!\n\nТеперь можешь начать работу по шагу. Нажми /steps."
                    )
            else:
                await callback.answer("Авторский шаблон не найден")

        elif data == "template_custom":
            await edit_long_message(
                callback,
                "✍️ Для создания своего шаблона нужно:\n\n"
                "1. Определить структуру (поля) шаблона\n"
                "2. Создать шаблон через API или настройки\n\n"
                "Пока используй авторский шаблон, а свой создашь позже в настройках."
            )
            await callback.answer()

    except Exception as exc:
        logger.exception("Error handling template selection for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_template_filling_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle template filling FSM callbacks (pause, cancel, etc.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        state_data = await state.get_data()
        step_id = state_data.get("template_step_id")
        question_id = state_data.get("template_question_id")

        if data == "tpl_pause":
            if step_id and question_id:
                result = await BACKEND_CLIENT.pause_template_progress(token, step_id, question_id)

                if result and result.get("success"):
                    resume_info = result.get("resume_info", "")
                    progress_summary = result.get("progress_summary", "")
                    await edit_long_message(
                        callback,
                        f"⏸ Прогресс сохранён!\n\n"
                        f"{resume_info}\n\n"
                        f"📊 {progress_summary}\n\n"
                        f"💡 Чтобы продолжить:\n"
                        f"1. Вернись к этому вопросу (🪜 Работа по шагу)\n"
                        f"2. Нажми «🧩 Заполнить по шаблону»\n"
                        f"3. Система автоматически продолжит с того места, где остановился",
                        reply_markup=build_step_actions_markup()
                    )
                    await state.set_state(StepState.answering)
                    await callback.answer("Прогресс сохранён")
                else:
                    await callback.answer("Ошибка сохранения прогресса")
            else:
                await callback.answer("Данные шаблона потеряны")
                await state.set_state(StepState.answering)

        elif data == "tpl_cancel":
            if step_id and question_id:
                await BACKEND_CLIENT.cancel_template_progress(token, step_id, question_id)

            await edit_long_message(
                callback,
                "❌ Заполнение шаблона отменено.\n\n"
                "Ты можешь ответить на вопрос своими словами или начать заполнение заново.",
                reply_markup=build_step_actions_markup()
            )
            await state.set_state(StepState.answering)
            await callback.answer("Заполнение отменено")

        elif data == "tpl_next_situation":
            await callback.answer("Продолжаем...")

        elif data == "tpl_write_conclusion":
            await callback.answer("Напиши финальный вывод")

        else:
            await callback.answer("Неизвестная команда")

    except Exception as exc:
        logger.exception("Error handling template filling callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_steps_settings(message: Message, state: FSMContext) -> None:
    """Handle /steps_settings command - show simplified settings menu (only step and question selection)"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Сначала нажми /start для авторизации.")
            return

        settings_text = (
            "⚙️ Настройки работы по шагу\n\n"
            "Выбери шаг и вопрос для работы:"
        )

        await message.answer(
            settings_text,
            reply_markup=build_steps_settings_markup()
        )

    except Exception as exc:
        logger.exception("Error handling steps settings for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при загрузке настроек. Попробуй позже.")

async def handle_steps_settings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle steps settings callback buttons - simplified: only back button"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data == "settings_back":
            await callback.message.edit_text(
                "Настройки",
                reply_markup=build_main_settings_markup()
            )
            await callback.answer()
            return

        await callback.answer("Неизвестная команда")

    except Exception as exc:
        logger.exception("Error handling steps settings callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_step_action_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle step action callbacks (pause, template, etc.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data == "step_continue":
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
                    progress_indicator = format_step_progress_indicator(
                        step_number=step_info.get("step_number"),
                        total_steps=step_info.get("total_steps", 12),
                        step_title=step_info.get("step_title"),
                        answered_questions=step_info.get("answered_questions", 0),
                        total_questions=step_info.get("total_questions", 0)
                    )

                    draft_data = await BACKEND_CLIENT.get_draft(token)
                    draft_text = ""
                    if draft_data and draft_data.get("success"):
                        draft_value = draft_data.get("draft")
                        draft_text = draft_value if draft_value else ""

                    if draft_text:
                        full_text = (
                            f"{progress_indicator}\n\n"
                            f"{response_text}\n\n"
                            f"Черновик: {draft_text[:100]}{'...' if len(draft_text) > 100 else ''}"
                        )
                    else:
                        full_text = (
                            f"{progress_indicator}\n\n"
                            f"{response_text}"
                        )

                    await state.update_data(
                        step_description=step_info.get("step_description", ""),
                        current_draft=draft_text,
                        nav_level="question",
                    )

                    await edit_long_message(
                        callback,
                        full_text,
                        reply_markup=build_step_answer_mode_markup()
                    )
                    await state.set_state(StepState.answer_mode)
                    await callback.answer()
                return

        if data == "step_back_from_answer":
            # Clear action state to prevent stale "save_draft" action
            await state.update_data(action=None)

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
                    progress_indicator = format_step_progress_indicator(
                        step_number=step_info.get("step_number"),
                        total_steps=step_info.get("total_steps", 12),
                        step_title=step_info.get("step_title"),
                        answered_questions=step_info.get("answered_questions", 0),
                        total_questions=step_info.get("total_questions", 0)
                    )

                    # Check if there's a draft
                    draft_data = await BACKEND_CLIENT.get_draft(token)
                    has_draft = draft_data and draft_data.get("success") and draft_data.get("draft")

                    if has_draft:
                        draft_preview = draft_data["draft"][:100]
                        full_text = f"{progress_indicator}\n\n{response_text}\n\nЧерновик: {draft_preview}{'...' if len(draft_data['draft']) > 100 else ''}"
                    else:
                        full_text = f"{progress_indicator}\n\n{response_text}"

                    # Navigate back to step actions screen (not answer_mode loop)
                    await state.update_data(
                        step_description=step_info.get("step_description", ""),
                        nav_level="question",
                    )

                    await edit_long_message(callback, full_text, reply_markup=build_step_actions_markup())
                    await state.set_state(StepState.answering)
                    await callback.answer()
            return

        if data == "step_save_draft":
            draft_data = await BACKEND_CLIENT.get_draft(token)
            logger.info("step_save_draft: draft_data=%s", draft_data)
            existing_draft = ""
            if draft_data and draft_data.get("success"):
                draft_value = draft_data.get("draft")
                existing_draft = draft_value if draft_value else ""

            step_data = await get_current_step_question(telegram_id, username, first_name)
            current_question_text = step_data.get("message", "") if step_data else ""

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            progress_indicator = format_step_progress_indicator(
                step_number=step_info.get("step_number", 0),
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            ) if step_info else ""

            draft_text = f"{progress_indicator}\n\n" if progress_indicator else ""
            if current_question_text:
                draft_text += f"{current_question_text}\n\n"

            if existing_draft:
                draft_text += f"Черновик: {existing_draft[:200]}{'...' if len(existing_draft) > 200 else ''}\n\n"
            else:
                draft_text += "Черновика пока нет.\n\n"
            draft_text += "Напиши ответ:"

            await state.update_data(action="save_draft")
            draft_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
            ])

            await callback.message.edit_text(draft_text, reply_markup=draft_markup)
            await callback.answer()
            return

        if data == "step_edit_last":
            try:
                question_id_data = await BACKEND_CLIENT.get_last_answered_question_id(token)
                question_id = question_id_data.get("question_id")
            except Exception as e:
                logger.warning(f"Failed to get last answered question_id: {e}")
                question_id = None

            if not question_id:
                await callback.answer("Нет отвеченных вопросов для редактирования")
                return

            try:
                prev_answer_data = await BACKEND_CLIENT.get_previous_answer(token, question_id)
                prev_answer = prev_answer_data.get("answer_text", "") if prev_answer_data else ""
            except Exception as e:
                logger.warning(f"Failed to get previous answer: {e}")
                prev_answer = None

            if prev_answer:
                try:
                    step_info = await BACKEND_CLIENT.get_current_step_info(token)
                    step_id = step_info.get("step_id")
                    if step_id:
                        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                        questions = questions_data.get("questions", []) if questions_data else []
                        question_text = ""
                        for q in questions:
                            if q.get("id") == question_id:
                                question_text = q.get("text", "")
                                break

                        if not question_text:
                            question_text = "Вопрос"
                    else:
                        question_text = "Вопрос"
                except Exception as e:
                    logger.warning(f"Failed to get question text: {e}")
                    question_text = "Вопрос"

                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                progress_indicator = format_step_progress_indicator(
                    step_number=step_info.get("step_number"),
                    total_steps=step_info.get("total_steps", 12),
                    step_title=step_info.get("step_title"),
                    answered_questions=step_info.get("answered_questions", 0),
                    total_questions=step_info.get("total_questions", 0)
                )

                try:
                    await callback.message.edit_text(
                        f"{progress_indicator}\n\n"
                        f"{question_text}\n\n"
                        f"✏️ Редактировать последний ответ:\n\n"
                        f"Предыдущий ответ:\n{prev_answer}\n\n"
                        f"Введи новый ответ:",
                        reply_markup=build_step_answer_mode_markup(),
                        parse_mode=None
                    )
                except TelegramBadRequest as e:
                    error_message = str(e).lower()
                    if "message is not modified" in error_message:
                        logger.debug(f"Message not modified (content unchanged) for edit_answer: {e}")
                    elif "can't parse entities" in error_message or "unsupported start tag" in error_message:
                        logger.warning(f"Entity parsing error for edit_answer: {e}, trying without parse_mode")
                        try:
                            await callback.message.edit_text(
                                f"{progress_indicator}\n\n"
                                f"{question_text}\n\n"
                                f"✏️ Редактировать последний ответ:\n\n"
                                f"Предыдущий ответ:\n{prev_answer}\n\n"
                                f"Введи новый ответ:",
                                reply_markup=build_step_answer_mode_markup(),
                                parse_mode=None
                            )
                        except Exception as e2:
                            logger.error(f"Failed to edit message even without parse_mode: {e2}")
                            await callback.message.answer(
                                f"{progress_indicator}\n\n"
                                f"{question_text}\n\n"
                                f"✏️ Редактировать последний ответ:\n\n"
                                f"Предыдущий ответ:\n{prev_answer}\n\n"
                                f"Введи новый ответ:",
                                reply_markup=build_step_answer_mode_markup(),
                                parse_mode=None
                            )
                    else:
                        logger.warning(f"TelegramBadRequest when editing message for edit_answer: {e}")
                        raise

                await state.update_data(action="edit_answer", previous_answer=prev_answer, current_question_id=question_id)
                await state.set_state(StepState.answer_mode)
                await callback.answer()
            else:
                await callback.answer("Предыдущий ответ не найден")

        if data == "step_view_draft":
            logger.info(f"Getting draft for user {telegram_id}")
            draft_data = await BACKEND_CLIENT.get_draft(token)
            logger.info(f"Draft data received for user {telegram_id}: {draft_data}")
            if not draft_data:
                logger.warning(f"No draft_data returned for user {telegram_id}")
                await callback.answer("Черновик не найден. Сохрани черновик сначала.")
                return

            success = draft_data.get("success")
            existing_draft = draft_data.get("draft")
            logger.info(f"Draft check for user {telegram_id}: success={success}, draft={existing_draft[:50] if existing_draft else None}...")

            if not success:
                logger.warning(f"Draft success=False for user {telegram_id}")
                await callback.answer("Черновик не найден. Сохрани черновик сначала.")
                return

            if not existing_draft or existing_draft.strip() == "":
                logger.warning(f"Draft is None or empty for user {telegram_id}, success was {success}")
                await callback.answer("Черновик не найден. Сохрани черновик сначала.")
                return

            step_data = await get_current_step_question(telegram_id, username, first_name)
            current_question_text = step_data.get("message", "") if step_data else ""

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            progress_indicator = format_step_progress_indicator(
                step_number=step_info.get("step_number", 0),
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            ) if step_info else ""

            draft_text = f"{progress_indicator}\n\n" if progress_indicator else ""
            if current_question_text:
                draft_text += f"{current_question_text}\n\n"
            draft_text += f"Черновик: {existing_draft}\n\n"
            draft_text += "Напиши ответ:"

            await state.update_data(action="save_draft", current_draft=existing_draft)
            draft_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
            ])

            await callback.message.edit_text(draft_text, reply_markup=draft_markup)
            await callback.answer()
            return

        if data == "step_reset_draft":
            await BACKEND_CLIENT.save_draft(token, "")
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
                    progress_indicator = format_step_progress_indicator(
                        step_number=step_info.get("step_number"),
                        total_steps=step_info.get("total_steps", 12),
                        step_title=step_info.get("step_title"),
                        answered_questions=step_info.get("answered_questions", 0),
                        total_questions=step_info.get("total_questions", 0)
                    )
                    full_text = (
                        f"{progress_indicator}\n\n"
                        f"{response_text}"
                    )
                    await state.update_data(current_draft="")
                    await callback.message.edit_text(
                        full_text,
                        reply_markup=build_step_answer_mode_markup()
                    )
            await callback.answer("Поле очищено")
            return

        if data == "step_complete":
            # Check if draft exists — if so, submit it as the answer directly
            draft_data = await BACKEND_CLIENT.get_draft(token)
            existing_draft = ""
            if draft_data and draft_data.get("success"):
                existing_draft = draft_data.get("draft") or ""

            if existing_draft.strip():
                # Submit draft as answer
                step_next = await process_step_message(
                    telegram_id=telegram_id,
                    text=existing_draft,
                    username=username,
                    first_name=first_name
                )

                if not step_next:
                    await callback.answer("Сессия потеряна. Нажми /steps снова.")
                    await state.clear()
                    return

                if step_next.get("error"):
                    error_message = step_next.get("message", "Ошибка валидации")
                    await callback.message.edit_text(
                        f"{error_message}\n\nДополни ответ и попробуй снова.",
                        reply_markup=build_step_answer_mode_markup()
                    )
                    await callback.answer()
                    return

                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                response_text = step_next.get("message", "")
                is_completed = step_next.get("is_completed", False)

                if step_info and step_info.get("step_number"):
                    progress_indicator = format_step_progress_indicator(
                        step_number=step_info.get("step_number", 0),
                        total_steps=step_info.get("total_steps", 12),
                        step_title=step_info.get("step_title"),
                        answered_questions=step_info.get("answered_questions", 0),
                        total_questions=step_info.get("total_questions", 0)
                    )
                    full_text = f"{progress_indicator}\n\n{response_text}"
                else:
                    full_text = response_text

                await state.update_data(action=None, current_draft="", step_description=step_info.get("step_description", "") if step_info else "")
                await callback.message.edit_text(full_text, reply_markup=build_step_actions_markup())
                await state.set_state(StepState.answering)
                await callback.answer()

                if is_completed:
                    await callback.message.answer("Этап завершен! 🎉", reply_markup=build_main_menu_markup())
                    await state.clear()
                return

            # No draft — ask user to type answer
            await state.update_data(action="complete")
            step_data = await get_current_step_question(telegram_id, username, first_name)
            current_question_text = step_data.get("message", "") if step_data else ""

            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            progress_indicator = format_step_progress_indicator(
                step_number=step_info.get("step_number", 0),
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            ) if step_info else ""

            complete_text = f"{progress_indicator}\n\n" if progress_indicator else ""
            if current_question_text:
                complete_text += f"{current_question_text}\n\n"
            complete_text += "Напиши ответ и отправь:"

            complete_markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
            ])

            await callback.message.edit_text(complete_text, reply_markup=complete_markup)
            await callback.answer()
            return

        if data == "step_show_description":
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                description = ""
                if step_info:
                    description = (
                        step_info.get("step_description") or
                        step_info.get("description") or
                        ""
                    )
                logger.info(f"step_show_description: desc_len={len(description)}, keys={list(step_info.keys()) if step_info else None}")

                if not description:
                    await callback.answer("Описание пока не загружено", show_alert=True)
                    return

                await edit_long_message(
                    callback,
                    f"📖 О шаге\n\n{description}",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️ Назад", callback_data="step_continue")]
                    ])
                )
                await callback.answer()
            except Exception as e:
                logger.exception(f"step_show_description error: {e}")
                await callback.answer(f"Ошибка: {e}", show_alert=True)
            return

        elif data == "step_progress":
            steps_list = await BACKEND_CLIENT.get_steps_list(token)
            steps = steps_list.get("steps", []) if steps_list else []

            await callback.message.edit_text(
                "📋 Мой прогресс\n\nВыбери шаг, чтобы посмотреть свои ответы.",
                reply_markup=build_progress_main_markup(steps)
            )
            await callback.answer()
            return

        elif data == "step_template":
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_id = step_info.get("step_id")

            step_data = await get_current_step_question(telegram_id, username, first_name)
            if not step_data:
                await callback.answer("Нет активного вопроса")
                return

            questions_data = await BACKEND_CLIENT.get_current_step_questions(token)
            questions = questions_data.get("questions", []) if questions_data else []

            current_question_text = step_data.get("message", "")
            question_id = None
            for q in questions:
                if q.get("text") == current_question_text:
                    question_id = q.get("id")
                    break

            if not question_id and questions:
                question_id = questions[0].get("id")

            if not step_id or not question_id:
                await callback.answer("Не удалось определить вопрос")
                return

            progress = await BACKEND_CLIENT.start_template_progress(token, step_id, question_id)

            if not progress:
                await callback.answer("Ошибка при запуске шаблона")
                return

            await state.update_data(
                template_step_id=step_id,
                template_question_id=question_id
            )

            is_resumed = progress.get("is_resumed", False)
            field_info = progress.get("field_info", {})
            current_situation = progress.get("current_situation", 1)
            progress_summary = progress.get("progress_summary", "")

            if is_resumed:
                field_name = field_info.get("name", "поле")
                situations = progress.get("situations", [])

                filled_info = ""
                if situations:
                    completed_count = sum(1 for s in situations if s.get("complete"))
                    filled_info = f"\n✅ Заполнено ситуаций: {completed_count}/3\n"

                    for i, situation in enumerate(situations[:completed_count], 1):
                        if situation.get("complete"):
                            where = situation.get("where", "")[:50]
                            if where:
                                filled_info += f"   Ситуация {i}: {where}...\n"

                intro_text = (
                    f"📋 Продолжаем заполнение шаблона!\n\n"
                    f"⏸ Ты остановился на:\n"
                    f"   Ситуация {current_situation}/3\n"
                    f"   Поле: {field_name}\n"
                    f"{filled_info}\n"
                    f"📊 {progress_summary}\n\n"
                    f"💡 Продолжай с того места, где остановился.\n"
                    f"👁️ Нажми «Посмотреть что заполнено» чтобы увидеть все детали.\n\n"
                )
            else:
                intro_text = (
                    f"📋 Заполнение по шаблону\n\n"
                    f"Шаблон включает:\n"
                    f"• 3 ситуации (по 6 полей каждая)\n"
                    f"• Финальный вывод\n\n"
                    f"📝 Ситуация {current_situation}/3\n\n"
            )

            field_name = field_info.get("name", "Поле")
            field_description = field_info.get("description", "")
            min_items = field_info.get("min_items")

            field_text = intro_text
            field_text += f"**{field_name}**\n"
            if field_description:
                field_text += f"{field_description}\n"
            if min_items:
                field_text += f"\n⚠️ Нужно указать минимум {min_items} (через запятую)\n"
            field_text += "\nВведи значение:"

            await edit_long_message(callback, field_text, reply_markup=build_template_filling_markup())
            await state.set_state(StepState.filling_template)
            await callback.answer()

        elif data == "step_switch_question":
            try:
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                step_id = step_info.get("step_id") if step_info else None

                if step_id:
                    try:
                        questions_data = await BACKEND_CLIENT.get_current_step_questions(token)
                        questions = questions_data.get("questions", []) if questions_data else []

                        if questions:
                            await edit_long_message(
                                callback,
                                "📋 Выбери вопрос для перехода:",
                                reply_markup=build_step_questions_markup(questions, step_id)
                            )
                            await callback.answer()
                        else:
                            await callback.answer("Вопросы не найдены")
                    except Exception as e:
                        logger.error(f"Error getting questions: {e}")
                        await callback.answer("Ошибка получения списка вопросов")
                else:
                    await callback.answer("Шаг не выбран")
            except Exception as e:
                logger.error(f"Error in step_switch_question: {e}")
                await callback.answer("Ошибка. Попробуй позже.")

        elif data == "step_view_template":
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_id = step_info.get("step_id")

            questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
            questions = questions_data.get("questions", [])
            answered_count = step_info.get("answered_questions", 0)

            if not questions or answered_count >= len(questions):
                await callback.answer("Нет активного вопроса")
                return

            current_question = questions[answered_count]
            question_id = current_question.get("id")

            progress = await BACKEND_CLIENT.get_template_progress(token, step_id, question_id)

            if not progress:
                await callback.answer("Нет сохранённых данных по шаблону")
                return

            situations = progress.get("situations", [])
            conclusion = progress.get("conclusion")
            current_situation = progress.get("current_situation", 1)
            current_field = progress.get("current_field", "")

            view_text = "📋 Что уже заполнено по шаблону:\n\n"

            if situations:
                for i, situation in enumerate(situations, 1):
                    if situation.get("complete"):
                        view_text += f"📌 Ситуация {i}:\n"
                        if situation.get("where"):
                            view_text += f"  Где: {situation.get('where')}\n"
                        if situation.get("thoughts"):
                            view_text += f"  Мысли: {situation.get('thoughts')}\n"
                        if situation.get("feelings_before"):
                            feelings = situation.get("feelings_before", [])
                            if isinstance(feelings, list):
                                feelings_str = ", ".join(feelings)
                            else:
                                feelings_str = str(feelings)
                            view_text += f"  Чувства (до): {feelings_str}\n"
                        if situation.get("actions"):
                            view_text += f"  Действие: {situation.get('actions')}\n"
                        if situation.get("healthy_feelings"):
                            view_text += f"  Здоровые чувства: {situation.get('healthy_feelings')}\n"
                        if situation.get("next_step"):
                            view_text += f"  Следующий шаг: {situation.get('next_step')}\n"
                        view_text += "\n"
                    elif i == current_situation:
                        view_text += f"📌 Ситуация {i} (заполняется):\n"
                        if situation.get("where"):
                            view_text += f"  Где: {situation.get('where')}\n"
                        if situation.get("thoughts"):
                            view_text += f"  Мысли: {situation.get('thoughts')}\n"
                        if situation.get("feelings_before"):
                            feelings = situation.get("feelings_before", [])
                            if isinstance(feelings, list):
                                feelings_str = ", ".join(feelings)
                            else:
                                feelings_str = str(feelings)
                            view_text += f"  Чувства (до): {feelings_str}\n"
                        if situation.get("actions"):
                            view_text += f"  Действие: {situation.get('actions')}\n"
                        if situation.get("healthy_feelings"):
                            view_text += f"  Здоровые чувства: {situation.get('healthy_feelings')}\n"
                        if situation.get("next_step"):
                            view_text += f"  Следующий шаг: {situation.get('next_step')}\n"
                        view_text += f"  ⏸ Остановился на поле: {current_field}\n"
                        view_text += "\n"

            if conclusion:
                view_text += f"📌 Финальный вывод:\n{conclusion}\n"

            view_text += f"\n{progress.get('progress_summary', '')}"

            await send_long_message(
                callback.message,
                view_text,
                reply_markup=build_step_actions_markup(has_template_progress=True)
            )
            await callback.answer()
            return

        elif data == "step_previous":
            try:
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                step_id = step_info.get("step_id") if step_info else None

                if step_id:
                    try:
                        questions_data = await BACKEND_CLIENT.get_current_step_questions(token)
                        questions = questions_data.get("questions", []) if questions_data else []

                        if questions and len(questions) > 1:
                            current_question_text = await get_current_step_question(
                                telegram_id=telegram_id,
                                username=username,
                                first_name=first_name
                            )
                            current_text = current_question_text.get("message", "") if current_question_text else ""

                            current_idx = -1
                            for i, q in enumerate(questions):
                                if q.get("text") == current_text:
                                    current_idx = i
                                    break

                            if current_idx > 0:
                                prev_question = questions[current_idx - 1]
                                await BACKEND_CLIENT.switch_to_question(token, prev_question.get("id"))
                                await edit_long_message(
                                    callback,
                                    f"📜 Предыдущий вопрос:\n\n{prev_question.get('text', '')}",
                                    reply_markup=build_step_actions_markup()
                                )
                                await state.set_state(StepState.answering)
                                await callback.answer()
                            else:
                                await callback.answer("Это первый вопрос в шаге")
                        else:
                            await callback.answer("Нет предыдущего вопроса")
                    except Exception as e:
                        logger.error(f"Error getting previous question: {e}")
                        await callback.answer("Ошибка получения вопросов")
                else:
                    await callback.answer("Шаг не выбран")
            except Exception as e:
                logger.error(f"Error in step_previous: {e}")
                await callback.answer("Ошибка. Попробуй позже.")

    except Exception as exc:
        logger.exception("Error handling step action callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_steps_navigation_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle steps navigation callbacks (select step, show questions, continue, back)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    logger.info(f"Steps navigation callback received: {data} from user {telegram_id}")

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data == "steps_select":
            logger.info(f"Fetching steps list for user {telegram_id}")
            try:
                steps_data = await BACKEND_CLIENT.get_steps_list(token)
                steps = steps_data.get("steps", [])

                logger.info(f"Received {len(steps)} steps for user {telegram_id}")

                if steps:
                    await state.update_data(nav_level="list")
                    await callback.answer()
                    logger.info(f"Building steps list markup for {len(steps)} steps")
                    markup = build_steps_list_markup(steps)
                    logger.info(f"Markup created, attempting to edit message")

                    try:
                        await callback.message.edit_text(
                            "🔢 Выбери шаг для работы:",
                            reply_markup=markup
                        )
                        logger.info(f"Successfully edited message with steps list")
                    except TelegramBadRequest as e:
                        if "message is not modified" in str(e).lower():
                            logger.debug(f"Message not modified (user clicked button again): {e}")
                        else:
                            logger.warning(f"TelegramBadRequest when editing message: {e}")
                            await callback.message.answer(
                                "🔢 Выбери шаг для работы:",
                                reply_markup=markup
                            )
                            logger.info(f"Sent new message as fallback")
                    except Exception as edit_error:
                        logger.exception(f"Failed to edit message: {edit_error}")
                        await callback.message.answer(
                            "🔢 Выбери шаг для работы:",
                            reply_markup=markup
                        )
                        logger.info(f"Sent new message as fallback")
                else:
                    await callback.answer("Шаги не найдены")
            except Exception as e:
                logger.exception(f"Error in steps_select for user {telegram_id}: {e}")
                await callback.answer("Ошибка получения списка шагов")
            return

        if data == "steps_questions":
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            step_id = step_info.get("step_id")

            if step_id:
                questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                questions = questions_data.get("questions", [])

                if questions:
                    await callback.answer()
                    await edit_long_message(
                        callback,
                        "📋 Вопросы в этом шаге:",
                        reply_markup=build_step_questions_markup(questions, step_id)
                    )
                else:
                    await callback.answer("Вопросы не найдены")
            else:
                await callback.answer("Шаг не выбран")
            return

        if data == "steps_continue":
            step_data = await get_current_step_question(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )

            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
                    step_info = await BACKEND_CLIENT.get_current_step_info(token)
                    progress_indicator = ""
                    if step_info and step_info.get("step_number"):
                        progress_indicator = format_step_progress_indicator(
                            step_number=step_info.get("step_number"),
                            total_steps=step_info.get("total_steps", 12),
                            step_title=step_info.get("step_title"),
                            answered_questions=step_info.get("answered_questions", 0),
                            total_questions=step_info.get("total_questions", 0)
                        )
                        await state.update_data(
                            step_description=step_info.get("step_description", ""),
                            nav_level="question",
                        )

                    full_text = f"{progress_indicator}\n\n{response_text}" if progress_indicator else response_text
                    await callback.answer()
                    await edit_long_message(
                        callback,
                        full_text,
                        reply_markup=build_step_actions_markup()
                    )
                    await state.set_state(StepState.answering)
                else:
                    await callback.answer("Нет текущего вопроса")
            else:
                await callback.answer("Ошибка получения вопроса")
            return

        if data == "steps_back":
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                step_data = await get_current_step_question(telegram_id, username, first_name)

                if step_data and step_info:
                    step_number = step_info.get("step_number")
                    step_title = step_info.get("step_title", "")
                    answered = step_info.get("answered_questions", 0)
                    total_q = step_info.get("total_questions", 0)

                    header = format_step_progress_indicator(
                        step_number=step_number,
                        total_steps=12,
                        step_title=step_title,
                        answered_questions=answered,
                        total_questions=total_q
                    )
                    question_text = step_data.get("message", "")
                    full_text = f"{header}\n\n {question_text}"

                    await state.update_data(step_description=step_info.get("step_description", ""))
                    await edit_long_message(callback, full_text, reply_markup=build_step_actions_markup())
                    await state.set_state(StepState.answering)
                else:
                    await edit_long_message(callback, "Меню", reply_markup=build_root_menu_markup())
            except Exception as e:
                logger.exception(f"steps_back error: {e}")
            await callback.answer()
            return

        if data == "steps_to_main":
            try:
                await callback.message.edit_text(
                    "Меню",
                    reply_markup=build_root_menu_markup(),
                )
            except TelegramBadRequest:
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer("Меню", reply_markup=build_root_menu_markup())
            await state.clear()
            await callback.answer()
            return

        await callback.answer("Неизвестная команда")

    except Exception as exc:
        logger.exception("Error handling steps navigation callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_step_selection_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle step selection callback (step_select_1, step_select_2, etc.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    logger.info(f"Step selection callback received: {data} from user {telegram_id}")

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        step_id = int(data.split("_")[-1])
        logger.info(f"Switching to step {step_id} for user {telegram_id}")

        await callback.answer(f"Переключаю на шаг {step_id}...")

        try:
            await BACKEND_CLIENT.switch_step(token, step_id)
            logger.info(f"Successfully switched to step {step_id}")
        except Exception as switch_error:
            logger.exception(f"Failed to switch to step {step_id}: {switch_error}")
            await callback.answer(f"Ошибка переключения на шаг {step_id}")
            return

        try:
            step_info = await BACKEND_CLIENT.get_current_step_info(token)
            step_number = step_info.get("step_number")
            step_title = step_info.get("step_title", "")
            step_description = step_info.get("step_description", "")

            logger.info(f"Step {step_id} info retrieved: step_number={step_number}, title={step_title[:50] if step_title else None}")
        except Exception as info_error:
            logger.exception(f"Failed to get step info for step {step_id}: {info_error}")
            await callback.answer("Ошибка получения информации о шаге")
            return

        try:
            step_data = await get_current_step_question(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name
            )
        except Exception as question_error:
            logger.exception(f"Failed to get current question for step {step_id}: {question_error}")
            await callback.answer("Ошибка получения вопроса")
            return

        if step_data:
            response_text = step_data.get("message", "")
            progress_indicator = format_step_progress_indicator(
                step_number=step_number,
                total_steps=step_info.get("total_steps", 12),
                step_title=step_title,
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0)
            )

            full_text = f"{progress_indicator}\n\n{response_text}"

            await state.update_data(step_description=step_description, nav_level="question")

            try:
                await edit_long_message(
                    callback,
                    full_text,
                    reply_markup=build_step_actions_markup()
                )
            except TelegramBadRequest as e:
                if "message is not modified" in str(e).lower():
                    logger.debug(f"Message not modified when selecting step {step_id}: {e}")
                else:
                    logger.warning(f"TelegramBadRequest when editing message for step {step_id}: {e}")
                    await callback.message.answer(
                        full_text,
                        reply_markup=build_step_actions_markup()
                    )
            except Exception as edit_error:
                logger.exception(f"Failed to edit message for step {step_id}: {edit_error}")
                await callback.message.answer(
                    full_text,
                    reply_markup=build_step_actions_markup()
                )

            await state.set_state(StepState.answering)
        else:
            await callback.answer("Ошибка получения вопроса")

    except Exception as exc:
        logger.exception("Error handling step selection callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_question_view_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle question view callback (question_view_123)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        question_id = int(data.split("_")[-1])

        question_data = await BACKEND_CLIENT.get_question_detail(token, question_id)
        question_text = question_data.get("question_text", "")
        question_number = question_data.get("question_number", 0)
        total_questions = question_data.get("total_questions", 0)

        if question_text:
            text = f"📋 Вопрос {question_number} из {total_questions}\n\n{question_text}"
            await edit_long_message(
                callback,
                text,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="steps_questions")]
                ])
            )
            await callback.answer()
        else:
            await callback.answer("Вопрос не найден")

    except Exception as exc:
        logger.exception("Error handling question view callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_template_field_input(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    field_value = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        step_id = state_data.get("template_step_id")
        question_id = state_data.get("template_question_id")

        if not step_id or not question_id:
            await message.answer("Ошибка: данные шаблона потеряны. Начни заново.")
            await state.clear()
            return

        result = await BACKEND_CLIENT.submit_template_field(
            token, step_id, question_id, field_value
        )

        if not result:
            await message.answer("Ошибка сервера. Попробуй ещё раз.")
            return

        if not result.get("success"):
            error_msg = result.get("error", "Ошибка валидации")
            validation_error = result.get("validation_error", False)

            if validation_error and result.get("current_feelings"):
                current_feelings = result.get("current_feelings", [])
                current_count = result.get("current_count", 0)
                if current_feelings:
                    feelings_text = ", ".join(current_feelings)
                    error_msg = f"{error_msg}\n\n📝 Уже указано ({current_count}): {feelings_text}"

            await message.answer(
                f"⚠️ {error_msg}\n\n💡 Совет: можешь написать все чувства через запятую в одном сообщении, или добавлять по одному.",
                reply_markup=build_template_filling_markup()
            )
            return

        if result.get("is_complete"):
            formatted_answer = result.get("formatted_answer", "")

            success = await BACKEND_CLIENT.submit_step_answer(token, formatted_answer, is_template_format=True)

            if success:
                step_next = await BACKEND_CLIENT.get_next_step(token)

                if step_next:
                    response_text = step_next.get("message", "")
                    is_completed = step_next.get("is_completed", False)

                    await send_long_message(
                        message,
                        response_text,
                        reply_markup=build_step_actions_markup()
                    )

                    if is_completed:
                        await message.answer(
                            "Этап завершен! 🎉",
                            reply_markup=build_main_menu_markup()
                        )
                        await state.clear()
                    else:
                        await state.set_state(StepState.answering)
                else:
                    await state.set_state(StepState.answering)
            else:
                await message.answer("Ошибка при сохранении. Попробуй ещё раз.")
            return

        field_info = result.get("field_info", {})
        current_situation = result.get("current_situation", 1)
        is_situation_complete = result.get("is_situation_complete", False)
        ready_for_conclusion = result.get("ready_for_conclusion", False)
        progress_summary = result.get("progress_summary", "")

        if ready_for_conclusion:
            await message.answer(
                f"✅ Ситуация {current_situation - 1} завершена!\n\n"
                f"🎯 Все 3 ситуации заполнены!\n\n"
                f"Теперь напиши **Финальный вывод**:\n\n"
                f"• Как ты теперь видишь ситуацию?\n"
                f"• Что на самом деле происходило?\n"
                f"• Как повторялись чувства/мысли/действия?\n"
                f"• Где была болезнь, где был ты?",
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )
        elif is_situation_complete:
            await message.answer(
                f"✅ Ситуация {current_situation - 1} завершена!\n\n"
                f"📝 Переходим к Ситуации {current_situation}\n\n"
                f"**{field_info.get('name', 'Поле')}**\n"
                f"{field_info.get('description', '')}\n\n"
                f"Введи значение:",
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )
        else:
            min_items = field_info.get("min_items")
            field_text = f"✅ Сохранено!\n\n"
            field_text += f"📝 Ситуация {current_situation}/3\n\n"
            field_text += f"**{field_info.get('name', 'Поле')}**\n"
            field_text += f"{field_info.get('description', '')}\n"
            if min_items:
                field_text += f"\n⚠️ Нужно указать минимум {min_items} (через запятую)\n"
            field_text += "\nВведи значение:"

            await message.answer(
                field_text,
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )

    except Exception as exc:
        logger.exception("Error handling template field input for %s: %s", telegram_id, exc)
        await message.answer("Произошла ошибка. Попробуй ещё раз.")
        await state.clear()


async def handle_questions_group_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle questions_group_{step_id}_{group_index} callback — show questions within a group."""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        parts = data.split("_")
        step_id = int(parts[2])
        group_index = int(parts[3])

        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
        questions = questions_data.get("questions", []) if questions_data else []

        if not questions:
            await callback.answer("Вопросы не найдены")
            return

        GROUP_SIZE = 15
        start = group_index * GROUP_SIZE + 1
        end = min((group_index + 1) * GROUP_SIZE, len(questions))

        try:
            await callback.message.edit_text(
                f"📋 Вопросы {start}–{end}",
                reply_markup=build_questions_group_markup(questions, step_id, group_index),
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                raise
        await callback.answer()

    except Exception as exc:
        logger.exception("Error handling questions group callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")


async def handle_progress_questions_group_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle progress_qgroup_{step_id}_{group_index} — show questions within a group in progress view."""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        parts = data.split("_")
        step_id = int(parts[2])
        group_index = int(parts[3])

        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
        questions = questions_data.get("questions", []) if questions_data else []

        if not questions:
            await callback.answer("Вопросы не найдены")
            return

        GROUP_SIZE = 15
        start = group_index * GROUP_SIZE + 1
        end = min((group_index + 1) * GROUP_SIZE, len(questions))

        try:
            await callback.message.edit_text(
                f"📋 Вопросы {start}–{end}",
                reply_markup=build_progress_questions_group_markup(questions, step_id, group_index),
            )
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                raise
        await callback.answer()

    except Exception as exc:
        logger.exception("Error handling progress questions group callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")


async def handle_question_select_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle question_select_{question_id} callback — switch to a specific question."""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        question_id = int(data.split("_")[-1])

        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        await BACKEND_CLIENT.switch_to_question(token, question_id)

        step_info = await BACKEND_CLIENT.get_current_step_info(token)
        step_data = await get_current_step_question(telegram_id, username, first_name)

        if step_data and step_data.get("message"):
            response_text = step_data["message"]
            progress_indicator = format_step_progress_indicator(
                step_number=step_info.get("step_number"),
                total_steps=step_info.get("total_steps", 12),
                step_title=step_info.get("step_title"),
                answered_questions=step_info.get("answered_questions", 0),
                total_questions=step_info.get("total_questions", 0),
            ) if step_info else ""

            full_text = f"{progress_indicator}\n\n{response_text}" if progress_indicator else response_text

            await state.update_data(
                step_description=step_info.get("step_description", "") if step_info else "",
                nav_level="question",
            )
            await edit_long_message(callback, full_text, reply_markup=build_step_actions_markup())
            await state.set_state(StepState.answering)
            await callback.answer()
        else:
            await callback.answer("Ошибка получения вопроса")

    except Exception as exc:
        logger.exception("Error handling question select callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")


async def handle_step_questions_list_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle step_questions_list_{step_id} callback — show questions list (back from group)."""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        step_id = int(data.split("_")[-1])

        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
        questions = questions_data.get("questions", []) if questions_data else []

        if questions:
            try:
                await callback.message.edit_text(
                    "📋 Вопросы в этом шаге:",
                    reply_markup=build_step_questions_markup(questions, step_id),
                )
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    raise
            await callback.answer()
        else:
            await callback.answer("Вопросы не найдены")

    except Exception as exc:
        logger.exception("Error handling step questions list callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")
