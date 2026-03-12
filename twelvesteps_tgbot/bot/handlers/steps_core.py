from typing import Optional
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    get_or_fetch_token,
    get_current_step_question,
    process_step_message,
)
from bot.config import (
    format_step_progress_indicator,
    build_exit_markup,
    build_main_menu_markup,
    build_error_markup,
    build_step_actions_markup,
    build_step_answer_mode_markup,
    build_steps_settings_markup,
    build_main_settings_markup,
)
from bot.utils import send_long_message, edit_long_message
from .shared import StepState, MAIN_MENU_TEXT, logger
from .steps_helpers import get_step_with_progress


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

        step_info, progress_indicator = await get_step_with_progress(token)
        step_number = step_info.get("step_number") if step_info else None

        if step_number:
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

            step_info, progress_indicator = await get_step_with_progress(token)
            response_text = step_next.get("message", "Ответ обновлён.")
            is_completed = step_next.get("is_completed", False)

            if progress_indicator:
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

            step_info, progress_indicator = await get_step_with_progress(token)
            response_text = step_next.get("message", "Ответ принят.")
            is_completed = step_next.get("is_completed", False)

            if progress_indicator:
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
        step_info, progress_indicator = await get_step_with_progress(token) if token else ({}, "")

        response_text = step_next.get("message", "Ответ принят.")
        is_completed = step_next.get("is_completed", False)

        if progress_indicator:
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

        step_info, progress_indicator = await get_step_with_progress(token)

        if not step_info or not step_info.get("step_number"):
            await message.answer("У тебя нет активного шага. Нажми /steps, чтобы начать.")
            return

        step_description = step_info.get("step_description", "")

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

        settings_text = "⚙️ Настройки шагов\n\nВыбери что настроить:"

        await message.answer(
            settings_text,
            reply_markup=build_steps_settings_markup()
        )

    except Exception as exc:
        logger.exception("Error handling steps settings for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при загрузке настроек. Попробуй позже.")

async def handle_steps_settings_callback(callback, state: FSMContext) -> None:
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
