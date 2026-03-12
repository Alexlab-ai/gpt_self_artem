from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    get_or_fetch_token,
)
from bot.config import (
    build_progress_main_markup,
    build_progress_view_answers_questions_markup,
    build_progress_questions_group_markup,
    _clean_step_title,
)
from .shared import logger


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
