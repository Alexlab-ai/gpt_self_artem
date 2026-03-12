from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    get_or_fetch_token,
    get_current_step_question,
    process_step_message,
)
from bot.config import (
    format_step_progress_indicator,
    build_main_menu_markup,
    build_step_actions_markup,
    build_step_answer_mode_markup,
    build_step_questions_markup,
    build_template_filling_markup,
    build_progress_main_markup,
)
from bot.utils import send_long_message, edit_long_message
from .shared import StepState, logger
from .steps_helpers import get_step_with_progress


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
            step_info, progress_indicator = await get_step_with_progress(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
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

            step_info, progress_indicator = await get_step_with_progress(token)
            if not step_info:
                await callback.answer("Не удалось получить информацию о шаге")
                return

            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text:
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

            step_info, progress_indicator = await get_step_with_progress(token)

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

                _, progress_indicator = await get_step_with_progress(token)

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

            step_info, progress_indicator = await get_step_with_progress(token)

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
            step_info, progress_indicator = await get_step_with_progress(token)
            step_data = await get_current_step_question(telegram_id, username, first_name)
            if step_data:
                response_text = step_data.get("message", "")
                if response_text and progress_indicator:
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

                step_info, progress_indicator = await get_step_with_progress(token)
                response_text = step_next.get("message", "")
                is_completed = step_next.get("is_completed", False)

                if progress_indicator:
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

            step_info, progress_indicator = await get_step_with_progress(token)

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
