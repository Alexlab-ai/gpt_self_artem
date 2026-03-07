from .shared import *

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
    """Handle about me section callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        if data == "about_back":
            await callback.answer()
            await callback.message.edit_text(
                "🪪 Расскажи о себе\n\n"
                "Выбери способ:",
                reply_markup=build_about_me_main_markup()
            )
            return

        if data == "about_free_story":
            await callback.answer()
            current_state = await state.get_state()
            if current_state == AboutMeStates.adding_entry:
                await state.clear()
            markup = build_free_story_markup()
            logger.info(f"Showing free story section with {len(markup.inline_keyboard)} button rows")
            try:
                await callback.message.edit_text(
                    "✍️ Свободный рассказ\n\n"
                    "Здесь ты можешь свободно рассказать о себе.",
                    reply_markup=markup
                )
                logger.info(f"Successfully edited message for free story with buttons")
            except Exception as e:
                logger.warning(f"Failed to edit message for free story: {e}, trying to send new message")
                try:
                    await callback.message.answer(
                        "✍️ Свободный рассказ\n\n"
                        "Здесь ты можешь свободно рассказать о себе.",
                        reply_markup=markup
                    )
                    logger.info(f"Successfully sent new message for free story with buttons")
                except Exception as e2:
                    logger.error(f"Failed to send new message for free story: {e2}")
            return

        if data == "about_add_free":
            await callback.answer()
            await state.update_data(about_section="about_free")
            await state.set_state(AboutMeStates.adding_entry)

            await callback.message.edit_text(
                "✍️ Свободный рассказ\n\n"
                "Напиши то, что хочешь добавить:",
                reply_markup=build_free_story_add_entry_markup()
            )
            return

        if data == "about_history_free":
            await callback.answer()
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if not token:
                    await edit_long_message(
                        callback,
                        "❌ Ошибка авторизации. Нажми /start.",
                        reply_markup=build_free_story_markup()
                    )
                    return

                history_data = await BACKEND_CLIENT.get_free_text_history(token)
                entries = history_data.get("entries", []) if history_data else []
                total = history_data.get("total", 0) if history_data else 0

                if not entries:
                    history_text = "🗃️ История\n\n(История пока пуста)"
                    markup = build_free_story_markup()
                else:
                    history_text = f"🗃️ История\n\nВсего записей: {total}\n\n"
                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    entry_buttons = []

                    for i, entry in enumerate(entries[:10], 1):
                        entry_id = entry.get("id")
                        section_name = entry.get("section_name", "Неизвестный раздел")
                        preview = entry.get("preview", "")
                        created_at = entry.get("created_at", "")
                        subblock = entry.get("subblock_name")

                        date_str = ""
                        if created_at:
                            try:
                                from datetime import datetime
                                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                                date_str = dt.strftime("%d.%m.%Y %H:%M")
                            except:
                                pass

                        history_text += f"{i}. {section_name}\n"
                        if subblock:
                            history_text += f"   📌 {subblock}\n"
                        if preview:
                            history_text += f"   {preview}\n"
                        if date_str:
                            history_text += f"   📅 {date_str}\n"
                        history_text += "\n"

                        button_text = f"📝 {i}. {section_name}"
                        if subblock:
                            button_text += f" ({subblock})"
                        if len(button_text) > 60:
                            button_text = button_text[:57] + "..."
                        entry_buttons.append([
                            InlineKeyboardButton(
                                text=button_text,
                                callback_data=f"profile_entry_{entry_id}"
                            )
                        ])

                    if total > 10:
                        history_text += f"\n... и ещё {total - 10} записей"

                    free_story_markup = build_free_story_markup()
                    combined_buttons = entry_buttons + free_story_markup.inline_keyboard
                    markup = InlineKeyboardMarkup(inline_keyboard=combined_buttons)

                try:
                    await edit_long_message(
                        callback,
                        history_text,
                        reply_markup=markup
                    )
                    logger.info(f"Successfully showed free story history with {len(entry_buttons) if entries else 0} entry buttons")
                except Exception as e:
                    logger.warning(f"Failed to edit message for free story history: {e}, sending new message")
                    try:
                        await callback.message.answer(
                            history_text,
                            reply_markup=markup
                        )
                        logger.info(f"Successfully sent new message for free story history with entry buttons")
                    except Exception as e2:
                        logger.error(f"Failed to send new message for free story history: {e2}")
            except Exception as e:
                logger.exception("Error loading history: %s", e)
                await edit_long_message(
                    callback,
                    "🗃️ История\n\n❌ Ошибка при загрузке истории. Попробуй позже.",
                    reply_markup=build_free_story_markup()
                )
            return

        if data == "about_mini_survey":
            await callback.answer("Загружаю вопросы...")

            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if not token:
                    await callback.message.edit_text(
                        "❌ Ошибка авторизации. Нажми /start.",
                        reply_markup=build_about_me_main_markup()
                    )
                    return

                logger.info(f"Loading profile sections for user {telegram_id}")

                sections_data = await BACKEND_CLIENT.get_profile_sections(token)
                logger.info(f"Received sections_data: {sections_data}")

                sections = sections_data.get("sections", []) if sections_data else []
                logger.info(f"Found {len(sections)} sections")

                if not sections:
                    logger.warning("No sections found in response")
                    await callback.message.edit_text(
                        "👣 Пройти мини-опрос\n\n"
                        "Вопросы пока не доступны. Разделы не найдены.",
                        reply_markup=build_about_me_main_markup()
                    )
                    return

                first_question_data = await find_first_unanswered_question(token)

                if not first_question_data:
                    await callback.message.edit_text(
                        "✅ Мини-опрос уже пройден!\n\n"
                        "Все вопросы отвечены.",
                        reply_markup=build_about_me_main_markup()
                    )
                    return

                section_id = first_question_data["section_id"]
                first_question = first_question_data["question"]
                section_info = first_question_data["section_info"]

                logger.info(f"Found first question: id={first_question.get('id')}, text={first_question.get('question_text', '')[:50]}...")

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
                    f"👣 Пройти мини-опрос\n\n"
                    f"❓ {question_text}",
                    reply_markup=build_mini_survey_markup(first_question.get("id"), can_skip=is_optional)
                )
            except Exception as e:
                logger.exception("Error starting survey: %s", e)
                try:
                    await edit_long_message(
                        callback,
                        f"❌ Ошибка загрузки опроса: {str(e)[:100]}\n\nПопробуй позже.",
                        reply_markup=build_about_me_main_markup()
                    )
                except Exception as edit_error:
                    logger.exception("Error editing error message: %s", edit_error)
            return

        if data == "about_survey_skip":
            await callback.answer("Пропускаю вопрос...")
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if token:
                    state_data = await state.get_data()
                    current_section_id = state_data.get("survey_section_id")
                    current_question_id = state_data.get("survey_question_id")

                    try:
                        result = await BACKEND_CLIENT.submit_profile_answer(
                            token, current_section_id, current_question_id, "[Пропущено]"
                        )
                        next_question_data = result.get("next_question")

                        if next_question_data:
                            question_text = next_question_data.get("text", "")
                            is_optional = next_question_data.get("is_optional", True)
                            is_generated = next_question_data.get("is_generated", False)
                            next_question_id = next_question_data.get("id")

                            await state.update_data(
                                survey_section_id=current_section_id,
                                survey_question_id=next_question_id,
                                survey_is_generated=is_generated
                            )

                            await callback.message.edit_text(
                                f"👣 Пройти мини-опрос\n\n"
                                f"❓ {question_text}",
                                reply_markup=build_mini_survey_markup(next_question_id if next_question_id else -1, can_skip=is_optional)
                            )
                        else:
                            await state.clear()
                            await callback.message.edit_text(
                                "✅ Мини-опрос завершён!\n\n"
                                "Спасибо за ответы.",
                                reply_markup=build_about_me_main_markup()
                            )
                    except Exception as submit_error:
                        logger.warning(f"Failed to skip via submit_profile_answer: {submit_error}, trying manual search")
                        next_question_data = await find_first_unanswered_question(token)

                        if next_question_data:
                            section_id = next_question_data["section_id"]
                            next_question = next_question_data["question"]
                            question_text = next_question.get("question_text", "")
                            is_optional = next_question.get("is_optional", False)

                            await state.update_data(
                                survey_section_id=section_id,
                                survey_question_id=next_question.get("id"),
                                survey_is_generated=False
                            )

                            await edit_long_message(
                                callback,
                                f"👣 Пройти мини-опрос\n\n"
                                f"❓ {question_text}",
                                reply_markup=build_mini_survey_markup(next_question.get("id"), can_skip=is_optional)
                            )
                        else:
                            await state.clear()
                            await edit_long_message(
                                callback,
                                "✅ Мини-опрос завершён!\n\n"
                                "Спасибо за ответы.",
                                reply_markup=build_about_me_main_markup()
                            )
            except Exception as e:
                logger.exception("Error skipping question: %s", e)
                try:
                    await edit_long_message(
                        callback,
                        "❌ Ошибка при пропуске вопроса. Попробуй позже.",
                        reply_markup=build_about_me_main_markup()
                    )
                except Exception as edit_error:
                    logger.exception("Error editing error message: %s", edit_error)
            return

        if data == "about_survey_pause":
            await callback.answer()
            await state.clear()
            await callback.message.edit_text(
                "⏸ Мини-опрос поставлен на паузу.\n\n"
                "Можешь продолжить позже.",
                reply_markup=build_about_me_main_markup()
            )
            return


        await callback.answer()
    except Exception as e:
        logger.exception("Error in handle_about_callback: %s", e)
        try:
            await callback.answer("Ошибка. Попробуй позже.")
        except:
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

