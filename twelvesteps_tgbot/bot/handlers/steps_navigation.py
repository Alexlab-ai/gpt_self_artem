from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    get_or_fetch_token,
    get_current_step_question,
)
from bot.config import (
    format_step_progress_indicator,
    build_root_menu_markup,
    build_steps_list_markup,
    build_step_questions_markup,
    build_step_actions_markup,
    build_questions_group_markup,
)
from bot.utils import edit_long_message
from .shared import StepState, logger
from .steps_helpers import get_step_with_progress


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
                    step_info, progress_indicator = await get_step_with_progress(token)
                    if step_info:
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
            step_info, progress_indicator = await get_step_with_progress(token)
            step_description = step_info.get("step_description", "") if step_info else ""
            logger.info(f"Step {step_id} info retrieved: progress={progress_indicator[:50] if progress_indicator else None}")
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

            full_text = f"{progress_indicator}\n\n{response_text}" if progress_indicator else response_text

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

        step_info, progress_indicator = await get_step_with_progress(token)
        step_data = await get_current_step_question(telegram_id, username, first_name)

        if step_data and step_data.get("message"):
            response_text = step_data["message"]

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
