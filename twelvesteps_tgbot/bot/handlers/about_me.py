from .shared import *


async def _start_mini_survey(callback: CallbackQuery, state: FSMContext) -> None:
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    token = await get_or_fetch_token(telegram_id, username, first_name)
    if not token:
        await callback.message.edit_text(
            "❌ Ошибка авторизации. Нажми /start.",
            reply_markup=build_profile_settings_markup()
        )
        return

    sections_data = await BACKEND_CLIENT.get_profile_sections(token)
    sections = sections_data.get("sections", []) if sections_data else []
    if not sections:
        await callback.message.edit_text(
            "👣 Пройти мини-опрос\n\nВопросы пока не доступны. Разделы не найдены.",
            reply_markup=build_profile_settings_markup()
        )
        return

    first_question_data = await find_first_unanswered_question(token)
    if not first_question_data:
        await callback.message.edit_text(
            "✅ Мини-опрос уже пройден!\n\nВсе вопросы отвечены.",
            reply_markup=build_profile_settings_markup()
        )
        return

    section_id = first_question_data["section_id"]
    first_question = first_question_data["question"]
    await state.update_data(
        survey_section_id=section_id,
        survey_question_id=first_question.get("id"),
        survey_question_index=0,
        survey_mode=True,
        survey_is_generated=False
    )
    await state.set_state(ProfileStates.answering_question)

    question_text = first_question.get("question_text", "")
    is_optional = first_question.get("is_optional", False)
    await edit_long_message(
        callback,
        f"👣 Пройти мини-опрос\n\n❓ {question_text}",
        reply_markup=build_mini_survey_markup(first_question.get("id"), can_skip=is_optional)
    )


async def find_first_unanswered_question(token: str, start_from_section_id: Optional[int] = None) -> Optional[dict]:
    sections_data = await BACKEND_CLIENT.get_profile_sections(token)
    sections = sections_data.get("sections", []) if sections_data else []

    skip_until_found = start_from_section_id is not None
    found_start_section = False

    for section in sections:
        section_id = section.get("id")
        if not section_id:
            continue

        if skip_until_found:
            if section_id == start_from_section_id:
                found_start_section = True
                continue
            elif not found_start_section:
                continue

        section_detail = await BACKEND_CLIENT.get_section_detail(token, section_id)
        if not section_detail:
            continue

        section_info = section_detail.get("section", {})
        questions = section_info.get("questions", [])

        if not questions:
            continue

        try:
            answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
            answered_question_ids = set()
            if answers_data and "answers" in answers_data:
                for answer in answers_data["answers"]:
                    q_id = answer.get("question_id")
                    if q_id:
                        answered_question_ids.add(q_id)
        except Exception as e:
            logger.warning(f"Failed to get answers for section {section_id}: {e}")
            answered_question_ids = set()

        for question in questions:
            question_id = question.get("id")
            if question_id and question_id not in answered_question_ids:
                return {
                    "section_id": section_id,
                    "question": question,
                    "section_info": section_info
                }

        continue

    return None

async def handle_about_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle callback queries for the legacy about-me/free-story flow."""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        if data == "about_back":
            await callback.answer()
            await callback.message.edit_text(
                "🪪 Мой профиль\n\nВыбери раздел:",
                reply_markup=build_profile_settings_markup()
            )
            return

        if data == "about_free_story":
            await callback.answer()
            current_state = await state.get_state()
            if current_state == AboutMeStates.adding_entry:
                await state.clear()
            await callback.message.edit_text(
                "✍️ Свободный рассказ\n\nЗдесь ты можешь свободно рассказать о себе.",
                reply_markup=build_free_story_markup()
            )
            return

        if data == "about_add_free":
            await callback.answer()
            await state.update_data(about_section="about_free")
            await state.set_state(AboutMeStates.adding_entry)
            await callback.message.edit_text(
                "✍️ Свободный рассказ\n\nНапиши то, что хочешь добавить:",
                reply_markup=build_free_story_add_entry_markup()
            )
            return

        if data == "about_history_free":
            await callback.answer()
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if not token:
                await edit_long_message(
                    callback,
                    "❌ Ошибка авторизации. Нажми /start.",
                    reply_markup=build_profile_settings_markup()
                )
                return
            history_data = await BACKEND_CLIENT.get_free_text_history(token)
            entries = history_data.get("entries", []) if history_data else []
            total = history_data.get("total", 0) if history_data else 0
            if not entries:
                await edit_long_message(
                    callback,
                    "🗃️ История\n\nИстория пока пуста.",
                    reply_markup=build_free_story_history_markup()
                )
                return
            entry_buttons = []
            for i, entry in enumerate(entries[:10], 1):
                entry_id = entry.get("id")
                section_name = entry.get("section_name", "Раздел")
                preview = entry.get("preview", "")
                button_text = f"📝 {i}. {section_name}: {preview}"[:64]
                entry_buttons.append([InlineKeyboardButton(text=button_text, callback_data=f"profile_entry_{entry_id}")])
            markup = InlineKeyboardMarkup(inline_keyboard=entry_buttons + build_free_story_history_markup().inline_keyboard)
            await edit_long_message(
                callback,
                f"🗃️ История\n\nВсего записей: {total}",
                reply_markup=markup
            )
            return

        if data == "about_mini_survey":
            await callback.answer("Загружаю вопросы...")
            try:
                await _start_mini_survey(callback, state)
            except Exception as e:
                logger.exception("Error starting survey: %s", e)
                await edit_long_message(
                    callback,
                    f"❌ Ошибка загрузки опроса: {str(e)[:100]}\n\nПопробуй позже.",
                    reply_markup=build_profile_settings_markup()
                )
            return

        if data == "about_survey_skip":
            await callback.answer("Пропускаю вопрос...")
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if not token:
                await edit_long_message(
                    callback,
                    "❌ Ошибка авторизации. Нажми /start.",
                    reply_markup=build_profile_settings_markup()
                )
                return
            state_data = await state.get_data()
            current_section_id = state_data.get("survey_section_id")
            current_question_id = state_data.get("survey_question_id")
            try:
                result = await BACKEND_CLIENT.submit_profile_answer(token, current_section_id, current_question_id, "[Пропущено]")
                next_question_data = result.get("next_question")
            except Exception as submit_error:
                logger.warning("Failed to skip via submit_profile_answer: %s", submit_error)
                next_question_data = None

            if next_question_data:
                question_text = next_question_data.get("text", "")
                is_optional = next_question_data.get("is_optional", True)
                is_generated = next_question_data.get("is_generated", False)
                next_question_id = next_question_data.get("id")
                await state.update_data(
                    survey_section_id=current_section_id,
                    survey_question_id=next_question_id,
                    survey_is_generated=is_generated,
                )
                await edit_long_message(
                    callback,
                    f"👣 Пройти мини-опрос\n\n❓ {question_text}",
                    reply_markup=build_mini_survey_markup(next_question_id if next_question_id else -1, can_skip=is_optional)
                )
                return

            next_question_data = await find_first_unanswered_question(token)
            if next_question_data:
                section_id = next_question_data["section_id"]
                next_question = next_question_data["question"]
                await state.update_data(
                    survey_section_id=section_id,
                    survey_question_id=next_question.get("id"),
                    survey_is_generated=False,
                )
                await edit_long_message(
                    callback,
                    f"👣 Пройти мини-опрос\n\n❓ {next_question.get('question_text', '')}",
                    reply_markup=build_mini_survey_markup(next_question.get("id"), can_skip=next_question.get("is_optional", False))
                )
                return

            await state.clear()
            await edit_long_message(
                callback,
                "✅ Мини-опрос завершён!\n\nСпасибо за ответы.",
                reply_markup=build_profile_settings_markup()
            )
            return

        if data == "about_survey_pause":
            await callback.answer()
            await state.clear()
            await callback.message.edit_text(
                "⏸ Мини-опрос поставлен на паузу.\n\nМожешь продолжить позже.",
                reply_markup=build_profile_settings_markup()
            )
            return

        await callback.answer()
    except Exception as e:
        logger.exception("Error in handle_about_callback: %s", e)
        try:
            await callback.answer("Ошибка. Попробуй позже.")
        except Exception:
            pass


async def handle_about_entry_input(message: Message, state: FSMContext) -> None:
    """Handle input for about me section entry"""
    text = message.text
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    data = await state.get_data()
    section = data.get("about_section", "about_free")

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        logger.info(f"User {telegram_id} submitting general free text: {text[:100]}...")
        result = await BACKEND_CLIENT.submit_general_free_text(token, text)
        logger.info(f"Free text submission result: {result}")

        saved_sections = result.get("saved_sections", [])
        status = result.get("status", "unknown")

        await state.clear()

        if status == "success" and saved_sections:
            sections_list = ", ".join([s.get("section_name", "раздел") for s in saved_sections[:3]])
            if len(saved_sections) > 3:
                sections_list += f" и ещё {len(saved_sections) - 3}"

            await message.answer(
                f"✅ Записано!\n\n"
                f"Информация сохранена в разделы: {sections_list}.\n\n"
                f"Можешь посмотреть историю, чтобы увидеть все записи.",
                reply_markup=build_free_story_markup()
            )
        elif status == "success":
            await message.answer(
                f"✅ Записано!\n\n"
                f"Твоя информация сохранена.",
                reply_markup=build_free_story_markup()
            )
        elif status == "no_info":
            await message.answer(
                f"⚠️ Не удалось автоматически определить раздел для этой информации.\n\n"
                f"Проверь историю — возможно, запись была сохранена в раздел «Свободный рассказ».",
                reply_markup=build_free_story_markup()
            )
        else:
            await message.answer(
                f"⚠️ Запись обработана, но возможны проблемы.\n\n"
                f"Проверь историю, чтобы убедиться, что всё сохранилось.",
                reply_markup=build_free_story_markup()
            )
    except Exception as exc:
        logger.exception("Error saving free story entry: %s", exc)
        await state.clear()
        await message.answer(
            "❌ Ошибка при сохранении. Попробуй ещё раз.",
            reply_markup=build_free_story_markup()
        )
