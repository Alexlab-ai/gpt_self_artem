from .shared import *

async def _render_profile_info_menu(callback: CallbackQuery, token: str, source: str = "settings") -> None:
    sections_data = await BACKEND_CLIENT.get_profile_sections(token)
    sections = sections_data.get("sections", []) if sections_data else []

    if not sections:
        await edit_long_message(
            callback,
            "📋 Информация обо мне\n\nРазделы пока недоступны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️", callback_data=_section_back_callback(source))]
            ])
        )
        return

    buttons = []
    for section in sections:
        section_id = section.get("id")
        if not section_id or section_id == 14:
            continue

        name = section.get("name", "Раздел")
        icon = section.get("icon", "")
        title = _clean_section_title(name, icon)
        buttons.append([
            InlineKeyboardButton(
                text=title[:64],
                callback_data=_section_nav_callback(section_id, source)
            )
        ])

    buttons.append([InlineKeyboardButton(text="◀️", callback_data=_section_back_callback(source))])

    text = (
        "📋 Информация обо мне\n\n"
        "Выбери раздел.\n"
        "Внутри раздела сразу будут видны последние записи и действия."
    )
    await edit_long_message(
        callback,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )



def _build_profile_info_section_markup(section_id: int, entries: list[dict], source: str = "settings") -> InlineKeyboardMarkup:
    history_cb = f"profile_history_settings_{section_id}" if source == "settings" else f"profile_history_{section_id}"
    add_cb = f"profile_add_entry_settings_{section_id}" if source == "settings" else f"profile_add_entry_{section_id}"
    back_cb = _section_back_callback(source)
    buttons = [
        [
            InlineKeyboardButton(text="🗃️ История", callback_data=history_cb),
            InlineKeyboardButton(text="➕ Добавить", callback_data=add_cb),
        ]
    ]
    for idx, entry in enumerate(entries[:5], 1):
        entry_id = entry.get("id")
        if not entry_id:
            continue
        preview = _entry_preview_text(entry.get("content", ""), limit=48) or "Запись"
        if source == "settings":
            cb = f"profile_entry_settings_{entry_id}_{section_id}"
        else:
            cb = f"profile_entry_{entry_id}"
        buttons.append([InlineKeyboardButton(text=f"📝 {idx}. {preview}"[:64], callback_data=cb)])
    buttons.append([InlineKeyboardButton(text="◀️", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_profile_history_markup(section_id: int, entries: list[dict], source: str = "settings", page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    buttons = []
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(entries))
    for i in range(start_idx, end_idx):
        entry = entries[i]
        entry_id = entry.get("id")
        if not entry_id:
            continue
        preview = _entry_preview_text(entry.get("content", ""), limit=48) or "Запись"
        if source == "settings":
            cb = f"profile_entry_settings_{entry_id}_{section_id}"
        else:
            cb = f"profile_entry_{entry_id}"
        buttons.append([InlineKeyboardButton(text=f"📝 {i + 1}. {preview}"[:64], callback_data=cb)])
    nav = []
    if page > 0:
        cb = f"profile_history_settings_{section_id}_page_{page-1}" if source == "settings" else f"profile_history_{section_id}_page_{page-1}"
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=cb))
    if end_idx < len(entries):
        cb = f"profile_history_settings_{section_id}_page_{page+1}" if source == "settings" else f"profile_history_{section_id}_page_{page+1}"
        nav.append(InlineKeyboardButton(text="➡️", callback_data=cb))
    if nav:
        buttons.append(nav)
    add_cb = f"profile_add_entry_settings_{section_id}" if source == "settings" else f"profile_add_entry_{section_id}"
    back_cb = _section_nav_callback(section_id, source)
    buttons.append([InlineKeyboardButton(text="➕ Добавить", callback_data=add_cb), InlineKeyboardButton(text="◀️", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_profile_entry_detail_markup(entry_id: int, section_id: int, source: str = "settings") -> InlineKeyboardMarkup:
    back_cb = f"profile_history_settings_{section_id}" if source == "settings" else f"profile_history_{section_id}"
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="◀️", callback_data=back_cb)]])

async def _render_profile_info_section(callback: CallbackQuery, token: str, section_id: int, source: str = "settings") -> None:
    section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
    section = section_data.get("section", {}) if section_data else {}
    if not section:
        await edit_long_message(
            callback,
            "❌ Раздел не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️", callback_data=_section_back_callback(source))]
            ])
        )
        return

    title = _clean_section_title(section.get("name", "Раздел"), section.get("icon", ""))
    history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
    entries = history_data.get("entries", []) if history_data else []
    text = f"{title}\n\n"
    text += "Выбери действие или открой запись ниже." if entries else "Пока не заполнено. Добавь первую запись или открой историю."
    await edit_long_message(
        callback,
        text,
        reply_markup=_build_profile_info_section_markup(section_id, entries, source=source)
    )

async def handle_profile(message: Message, state: FSMContext) -> None:
    """Handle /profile command - show all profile sections"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Сначала нажми /start для авторизации.")
            return

        sections_data = await BACKEND_CLIENT.get_profile_sections(token)
        sections = sections_data.get("sections", [])

        if not sections:
            await message.answer("Разделы профиля пока не настроены.")
            return

        markup = build_profile_sections_markup(sections)
        await send_long_message(
            message,
            "📋 Выбери раздел, о котором хочешь рассказать:",
            reply_markup=markup
        )
        await state.set_state(ProfileStates.section_selection)

    except Exception as exc:
        logger.exception("Error handling /profile for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при загрузке разделов. Попробуй позже.")

async def handle_profile_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle callback queries for profile actions"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    logger.info(f"Profile callback received: {data} from user {telegram_id}")

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            logger.warning(f"No token for user {telegram_id}")
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data.startswith("profile_section_"):
            section_id = int(data.split("_")[-1])
            logger.info(f"User {telegram_id} selected section {section_id}")
            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            if not section_data:
                logger.error(f"Section {section_id} not found for user {telegram_id}")
                await callback.answer("Ошибка: раздел не найден")
                return
            section = section_data.get("section", {})
            if not section:
                logger.error(f"Section data is empty for section {section_id}, user {telegram_id}")
                await callback.answer("Ошибка: данные раздела не найдены")
                return
            questions = section.get("questions", [])
            logger.info(f"Section {section_id} ({section.get('name', 'Unknown')}) has {len(questions)} questions")

            if not questions:
                section_name = section.get('name', 'Раздел')
                markup = build_profile_actions_markup(section_id)
                logger.info(f"Section {section_id} ({section_name}) has no questions, showing buttons: {len(markup.inline_keyboard)} rows")
                try:
                    await edit_long_message(
                        callback,
                        f"📝 {section_name}\n\n"
                        "В этом разделе пока нет вопросов.\n\n"
                        "Ты можешь:\n"
                        "• Добавить запись вручную\n"
                        "• Посмотреть историю записей\n"
                        "• Написать свободный рассказ",
                        reply_markup=markup
                    )
                    logger.info(f"Successfully edited message for section {section_id} with buttons")
                except Exception as e:
                    logger.warning(f"Failed to edit message for section {section_id}: {e}, sending new message")
                    try:
                        await callback.message.answer(
                            f"📝 {section_name}\n\n"
                            "В этом разделе пока нет вопросов.\n\n"
                            "Ты можешь:\n"
                            "• Добавить запись вручную\n"
                            "• Посмотреть историю записей\n"
                            "• Написать свободный рассказ",
                            reply_markup=markup
                        )
                        logger.info(f"Successfully sent new message for section {section_id} with buttons")
                    except Exception as e2:
                        logger.error(f"Failed to send new message for section {section_id}: {e2}")
                        await callback.answer(f"Ошибка: {str(e2)[:50]}")
                        return
                await callback.answer()
                return

            answered_question_ids = set()
            try:
                answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
                if answers_data and "answers" in answers_data:
                    for answer in answers_data["answers"]:
                        q_id = answer.get("question_id")
                        if q_id:
                            answered_question_ids.add(q_id)

                all_question_ids = {q.get("id") for q in questions if q.get("id")}
                all_answered = len(all_question_ids) > 0 and all_question_ids.issubset(answered_question_ids)

                if all_answered:
                    section_name = section.get('name', 'Раздел')
                    markup = build_profile_actions_markup(section_id)
                    logger.info(f"Section {section_id} ({section_name}) all questions answered, showing buttons: {len(markup.inline_keyboard)} rows")
                    try:
                        await edit_long_message(
                            callback,
                            f"📝 {section_name}\n\n"
                            "✅ Все вопросы в этом разделе отвечены!\n\n"
                            "Ты можешь:\n"
                            "• Посмотреть историю записей\n"
                            "• Добавить новую запись вручную\n"
                            "• Написать свободный рассказ",
                            reply_markup=markup
                        )
                        logger.info(f"Successfully edited message for section {section_id} with buttons")
                    except Exception as e:
                        logger.warning(f"Failed to edit message for section {section_id}: {e}, sending new message")
                        try:
                            await callback.message.answer(
                                f"📝 {section_name}\n\n"
                                "✅ Все вопросы в этом разделе отвечены!\n\n"
                                "Ты можешь:\n"
                                "• Посмотреть историю записей\n"
                                "• Добавить новую запись вручную\n"
                                "• Написать свободный рассказ",
                                reply_markup=markup
                            )
                            logger.info(f"Successfully sent new message for section {section_id} with buttons")
                        except Exception as e2:
                            logger.error(f"Failed to send new message for section {section_id}: {e2}")
                            await callback.answer(f"Ошибка: {str(e2)[:50]}")
                            return
                    await state.set_state(ProfileStates.section_selection)
                    await callback.answer()
                    return
            except Exception as e:
                logger.warning(f"Failed to check answers for section {section_id}: {e}")

            unanswered_questions = [q for q in questions if q.get("id") not in answered_question_ids]

            if not unanswered_questions:
                section_name = section.get('name', 'Раздел')
                try:
                    await edit_long_message(
                        callback,
                        f"📝 {section_name}\n\n"
                        "✅ Все вопросы в этом разделе отвечены!\n\n"
                        "Ты можешь:\n"
                        "• Посмотреть историю записей\n"
                        "• Добавить новую запись вручную\n"
                        "• Написать свободный рассказ",
                        reply_markup=build_profile_actions_markup(section_id)
                    )
                except Exception as e:
                    logger.warning(f"Failed to edit message for section {section_id}: {e}, sending new message")
                    await callback.message.answer(
                        f"📝 {section_name}\n\n"
                        "✅ Все вопросы в этом разделе отвечены!\n\n"
                        "Ты можешь:\n"
                        "• Посмотреть историю записей\n"
                        "• Добавить новую запись вручную\n"
                        "• Написать свободный рассказ",
                        reply_markup=build_profile_actions_markup(section_id)
                    )
                await state.set_state(ProfileStates.section_selection)
                await callback.answer()
                return

            first_question = unanswered_questions[0]
            intro_text = f"📝 {section.get('name', 'Раздел')}\n\n"
            intro_text += "Давай начнём с первого неотвеченного вопроса:\n\n"
            question_text = f"{first_question.get('question_text', '')}"

            await state.update_data(
                section_id=section_id,
                current_question_id=first_question.get("id"),
                questions=questions,
                question_index=0
            )

            markup = build_profile_actions_markup(section_id)
            if first_question.get("is_optional"):
                skip_markup = build_profile_skip_markup()
                markup.inline_keyboard.append(skip_markup.inline_keyboard[0])

            try:
                await edit_long_message(
                    callback,
                    intro_text + question_text,
                    reply_markup=markup
                )
            except Exception as e:
                logger.warning(f"Failed to edit message for section {section_id} question: {e}, sending new message")
                await callback.message.answer(
                    intro_text + question_text,
                    reply_markup=markup
                )
            await state.set_state(ProfileStates.answering_question)
            await callback.answer()

        elif data == "profile_free_text" or data.startswith("profile_free_text_"):
            section_id = None
            if "_" in data:
                try:
                    section_id = int(data.split("_")[-1])
                except ValueError:
                    pass

            await state.update_data(section_id=section_id)
            await edit_long_message(
                callback,
                "✍️ Напиши свой рассказ. После сохранения система автоматически распределит информацию по разделам."
            )
            await state.set_state(ProfileStates.free_text_input)
            await callback.answer()

        elif data == "profile_custom_section":
            await edit_long_message(
                callback,
                "➕ Как назовём новый раздел? (можно добавить эмодзи)"
            )
            await state.set_state(ProfileStates.creating_custom_section)
            await callback.answer()

        elif data == "profile_back":
            await callback.message.edit_text(
                "🪪 Мой профиль\n\nВыбери раздел:",
                reply_markup=build_profile_settings_markup()
            )
            await callback.answer()
            return

        elif data == "profile_back_to_settings":
            await callback.message.edit_text(
                "🪪 Профиль\n\nВыбери раздел:",
                reply_markup=build_profile_settings_markup()
            )
            await callback.answer()
            return

        elif data == "profile_skip":
            state_data = await state.get_data()
            questions = state_data.get("questions", [])
            question_index = state_data.get("question_index", 0)

            if question_index + 1 < len(questions):
                next_index = question_index + 1
                next_question = questions[next_index]

                await state.update_data(question_index=next_index, current_question_id=next_question.get("id"))

                markup = build_profile_actions_markup(state_data.get("section_id"))
                if next_question.get("is_optional"):
                    skip_markup = build_profile_skip_markup()
                    markup.inline_keyboard.append(skip_markup.inline_keyboard[0])

                await edit_long_message(
                    callback,
                    next_question.get("question_text", ""),
                    reply_markup=markup
                )
                await callback.answer("Вопрос пропущен")
            else:
                await callback.answer("Это был последний вопрос")

        elif data.startswith("profile_history_"):
            parts = data.split("_")
            section_id = int(parts[2])
            page = 0

            if len(parts) > 3 and parts[3] == "page":
                page = int(parts[4])

            history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
            entries = history_data.get("entries", []) if history_data else []

            if not entries:
                section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
                section_name = section_data.get("section", {}).get("name", "Раздел")
                await edit_long_message(
                    callback,
                    f"🗃️ История раздела: {section_name}\n\n"
                    "История пока пуста. Добавь первую запись!",
                    reply_markup=build_section_history_markup(section_id, entries, page)
                )
            else:
                section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
                section_name = section_data.get("section", {}).get("name", "Раздел")
                history_text = f"🗃️ История раздела: {section_name}\n\nВсего записей: {len(entries)}\n\n"

                start_idx = page * 5
                end_idx = min(start_idx + 5, len(entries))

                for i in range(start_idx, end_idx):
                    entry = entries[i]
                    content = entry.get("content", "")
                    subblock = entry.get("subblock_name")
                    created_at = entry.get("created_at", "")

                    date_str = ""
                    if created_at:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            date_str = dt.strftime("%d.%m.%Y %H:%M")
                        except:
                            pass

                    history_text += f"📝 Запись {i+1}"
                    if subblock:
                        history_text += f" ({subblock})"
                    history_text += "\n"
                    if date_str:
                        history_text += f"📅 {date_str}\n"
                    history_text += "\n"

                markup = build_section_history_markup(section_id, entries, page)
                logger.info(f"Showing history for section {section_id} with {len(entries)} entries, page {page}, {len(markup.inline_keyboard)} button rows")
                try:
                    await edit_long_message(
                        callback,
                        history_text,
                        reply_markup=markup
                    )
                    logger.info(f"Successfully edited message for section {section_id} history with entry buttons")
                except Exception as e:
                    logger.warning(f"Failed to edit message for section {section_id} history: {e}, sending new message")
                    try:
                        await callback.message.answer(
                            history_text,
                            reply_markup=markup
                        )
                        logger.info(f"Successfully sent new message for section {section_id} history with entry buttons")
                    except Exception as e2:
                        logger.error(f"Failed to send new message for section {section_id} history: {e2}")
            await callback.answer()

        elif data.startswith("profile_entry_"):
            entry_id = int(data.split("_")[-1])

            history_data = await BACKEND_CLIENT.get_free_text_history(token)
            entries = history_data.get("entries", []) if history_data else []

            entry = None
            section_id = None
            for e in entries:
                if e.get("id") == entry_id:
                    entry = e
                    section_id = e.get("section_id")
                    break

            if not entry:
                await callback.answer("Запись не найдена")
                return

            content = entry.get("content", "")
            subblock = entry.get("subblock_name")
            entity_type = entry.get("entity_type")
            importance = entry.get("importance")
            is_core = entry.get("is_core_personality", False)
            tags = entry.get("tags")
            created_at = entry.get("created_at", "")

            date_str = ""
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime("%d.%m.%Y %H:%M")
                except:
                    pass

            entry_text = f"📝 Запись\n\n"
            if subblock:
                entry_text += f"📌 Подблок: {subblock}\n"
            if entity_type:
                entry_text += f"🏷 Тип: {entity_type}\n"
            if importance:
                entry_text += f"⭐ Важность: {importance}\n"
            if is_core:
                entry_text += f"💎 Ядро личности: Да\n"
            if tags:
                entry_text += f"🏷 Теги: {tags}\n"
            if date_str:
                entry_text += f"📅 {date_str}\n"
            entry_text += f"\n💬 Содержание:\n{content}"

            markup = build_entry_detail_markup(entry_id, section_id)
            logger.info(f"Showing entry detail {entry_id} with {len(markup.inline_keyboard)} button rows")
            try:
                await edit_long_message(
                    callback,
                    entry_text,
                    reply_markup=markup
                )
                logger.info(f"Successfully edited message for entry {entry_id} with edit/delete buttons")
            except Exception as e:
                logger.warning(f"Failed to edit message for entry {entry_id}: {e}, sending new message")
                try:
                    await callback.message.answer(
                        entry_text,
                        reply_markup=markup
                    )
                    logger.info(f"Successfully sent new message for entry {entry_id} with edit/delete buttons")
                except Exception as e2:
                    logger.error(f"Failed to send new message for entry {entry_id}: {e2}")
            await callback.answer()

        elif data.startswith("profile_edit_"):
            entry_id = int(data.split("_")[-1])

            history_data = await BACKEND_CLIENT.get_free_text_history(token)
            entries = history_data.get("entries", []) if history_data else []

            entry = None
            section_id = None
            for e in entries:
                if e.get("id") == entry_id:
                    entry = e
                    section_id = e.get("section_id")
                    break

            if not entry:
                await callback.answer("Запись не найдена")
                return

            await state.update_data(
                editing_entry_id=entry_id,
                editing_section_id=section_id,
                editing_content=entry.get("content", "")
            )
            await state.set_state(ProfileStates.editing_entry)

            await edit_long_message(
                callback,
                f"✏️ Редактирование записи\n\n"
                f"Текущее содержание:\n{entry.get('content', '')}\n\n"
                f"Напиши новое содержание:",
                reply_markup=build_entry_edit_markup(entry_id, section_id)
            )
            await callback.answer()

        elif data.startswith("profile_delete_"):
            entry_id = int(data.split("_")[-1])

            history_data = await BACKEND_CLIENT.get_free_text_history(token)
            entries = history_data.get("entries", []) if history_data else []

            section_id = None
            for e in entries:
                if e.get("id") == entry_id:
                    section_id = e.get("section_id")
                    break

            if not section_id:
                await callback.answer("Запись не найдена")
                return

            try:
                await BACKEND_CLIENT.delete_section_data_entry(token, entry_id)
                await callback.answer("✅ Запись удалена")

                history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
                entries = history_data.get("entries", []) if history_data else []

                if not entries:
                    section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
                    section_name = section_data.get("section", {}).get("name", "Раздел")
                    await edit_long_message(
                        callback,
                        f"🗃️ История раздела: {section_name}\n\n"
                        "История пуста.",
                        reply_markup=build_section_history_markup(section_id, entries, 0)
                    )
                else:
                    section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
                    section_name = section_data.get("section", {}).get("name", "Раздел")
                    await edit_long_message(
                        callback,
                        f"🗃️ История раздела: {section_name}\n\nВсего записей: {len(entries)}",
                        reply_markup=build_section_history_markup(section_id, entries, 0)
                    )
            except Exception as e:
                logger.exception(f"Error deleting entry {entry_id}: {e}")
                await callback.answer("❌ Ошибка при удалении")

        elif data == "profile_my_info":
            await _render_profile_info_menu(callback, token, source="profile")
            await callback.answer()
            return

        elif data.startswith("profile_info_settings_section_"):
            section_id = int(data.split("_")[-1])
            await _render_profile_info_section(callback, token, section_id, source="settings")
            await callback.answer()
            return

        elif data.startswith("profile_info_section_"):
            section_id = int(data.split("_")[-1])
            await _render_profile_info_section(callback, token, section_id, source="profile")
            await callback.answer()
            return

        elif data.startswith("profile_add_entry_"):
            section_id = int(data.split("_")[-1])

            await state.update_data(adding_section_id=section_id, adding_source="profile")
            await state.set_state(ProfileStates.adding_entry)

            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_name = section_data.get("section", {}).get("name", "Раздел")

            await edit_long_message(
                callback,
                f"➕ Добавить запись в раздел: {section_name}\n\n"
                "Напиши содержание записи:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️", callback_data=f"profile_info_section_{section_id}")]
                ])
            )
            await callback.answer()

        elif data.startswith("profile_save_edit_"):
            await callback.answer("Напиши новое содержание и нажми 'Сохранить'")

    except Exception as exc:
        logger.exception("Error handling profile callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_profile_answer(message: Message, state: FSMContext) -> None:
    """Handle answer to a profile question"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    answer_text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        survey_mode = state_data.get("survey_mode", False)

        if survey_mode:
            section_id = state_data.get("survey_section_id")
            question_id = state_data.get("survey_question_id")
            is_generated = state_data.get("survey_is_generated", False)

            if not section_id:
                await message.answer("Ошибка: не найден раздел.")
                await state.clear()
                return

            if not is_generated and not question_id:
                await message.answer("Ошибка: не найден вопрос.")
                await state.clear()
                return

            result = await BACKEND_CLIENT.submit_profile_answer(
                token, section_id, question_id, answer_text
            )

            next_question_data = result.get("next_question")

            if next_question_data:
                question_text = next_question_data.get("text", "")
                is_optional = next_question_data.get("is_optional", True)
                is_generated = next_question_data.get("is_generated", False)
                next_question_id = next_question_data.get("id")

                if not is_generated and next_question_id == question_id:
                    logger.warning(f"Next question is the same as current question {question_id}, skipping to next section")
                    next_question_data = await find_first_unanswered_question(token, start_from_section_id=section_id)
                    if not next_question_data:
                        await state.clear()
                        await message.answer(
                            "✅ Мини-опрос завершён!\n\n"
                            "Спасибо за ответы.",
                            reply_markup=build_about_me_main_markup()
                        )
                        return
                    next_section_id = next_question_data["section_id"]
                    next_question = next_question_data["question"]
                    section_info = next_question_data["section_info"]
                    question_text = next_question.get("question_text", "")
                    is_optional = next_question.get("is_optional", False)
                    next_question_id = next_question.get("id")
                    is_generated = False
                else:
                    if is_generated:
                        next_section_id = section_id
                        section_info = None
                    else:
                        next_section_id = section_id
                        section_detail = await BACKEND_CLIENT.get_section_detail(token, next_section_id)
                        section_info = section_detail.get("section", {}) if section_detail else {}

                if is_generated:
                    await state.update_data(
                        survey_section_id=next_section_id,
                        survey_question_id=None,
                        survey_is_generated=True,
                        survey_generated_text=question_text
                    )
                else:
                    await state.update_data(
                        survey_section_id=next_section_id,
                        survey_question_id=next_question_id,
                        survey_is_generated=False
                    )

                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                survey_markup = build_mini_survey_markup(next_question_id if next_question_id else -1, can_skip=is_optional)
                section_actions = [
                    [InlineKeyboardButton(text="🗃️ История раздела", callback_data=f"profile_history_{next_section_id}")],
                    [InlineKeyboardButton(text="➕ Добавить в раздел", callback_data=f"profile_add_entry_{next_section_id}")]
                ]
                combined_buttons = survey_markup.inline_keyboard + section_actions
                combined_markup = InlineKeyboardMarkup(inline_keyboard=combined_buttons)

                if section_info:
                    await send_long_message(
                        message,
                        f"✅ Ответ сохранён!\n\n"
                        f"👣 Пройти мини-опрос\n\n"
                        f"📋 {section_info.get('name', 'Следующий раздел')}\n\n"
                        f"❓ {question_text}",
                        reply_markup=combined_markup
                    )
                else:
                    await send_long_message(
                        message,
                        f"✅ Ответ сохранён!\n\n"
                        f"👣 Пройти мини-опрос\n\n"
                        f"❓ {question_text}",
                        reply_markup=combined_markup
                    )
            else:
                next_question_data = await find_first_unanswered_question(token, start_from_section_id=section_id)

                if next_question_data:
                    next_section_id = next_question_data["section_id"]
                    next_question = next_question_data["question"]
                    section_info = next_question_data["section_info"]
                    question_text = next_question.get("question_text", "")
                    is_optional = next_question.get("is_optional", False)

                    await state.update_data(
                        survey_section_id=next_section_id,
                        survey_question_id=next_question.get("id"),
                        survey_question_index=0,
                        survey_mode=True,
                        survey_is_generated=False
                    )

                    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    survey_markup = build_mini_survey_markup(next_question.get("id"), can_skip=is_optional)
                    section_actions = [
                        [InlineKeyboardButton(text="🗃️ История раздела", callback_data=f"profile_history_{section_id}")],
                        [InlineKeyboardButton(text="➕ Добавить в раздел", callback_data=f"profile_add_entry_{section_id}")]
                    ]
                    combined_buttons = survey_markup.inline_keyboard + section_actions
                    combined_markup = InlineKeyboardMarkup(inline_keyboard=combined_buttons)

                    await send_long_message(
                        message,
                        f"✅ Раздел завершён!\n\n"
                        f"👣 Пройти мини-опрос\n\n"
                        f"📋 {section_info.get('name', 'Следующий раздел')}\n\n"
                        f"❓ {question_text}",
                        reply_markup=combined_markup
                    )
                else:
                    await state.clear()
                    await message.answer(
                        "✅ Мини-опрос завершён!\n\n"
                        "Спасибо за ответы.",
                        reply_markup=build_about_me_main_markup()
                    )
        else:
            section_id = state_data.get("section_id")
            question_id = state_data.get("current_question_id")
            is_generated = state_data.get("is_generated_question", False)
            questions = state_data.get("questions", [])
            question_index = state_data.get("question_index", 0)

            if not section_id:
                await message.answer("Ошибка: не найден раздел. Начни заново с /profile")
                await state.clear()
                return

            if not is_generated and not question_id:
                await message.answer("Ошибка: не найден вопрос. Начни заново с /profile")
                await state.clear()
                return

            result = await BACKEND_CLIENT.submit_profile_answer(
                token, section_id, question_id, answer_text
            )

            next_question = result.get("next_question")

            if next_question:
                next_question_text = next_question.get("text", "")
                is_generated_next = next_question.get("is_generated", False)
                next_question_id = next_question.get("id")

                if is_generated_next:
                    await state.update_data(
                        current_question_id=None,
                        question_index=question_index + 1,
                        is_generated_question=True
                    )
                else:
                    await state.update_data(
                        current_question_id=next_question_id,
                        question_index=question_index + 1,
                        is_generated_question=False
                    )

                markup = build_profile_actions_markup(section_id)
                if next_question.get("is_optional"):
                    skip_markup = build_profile_skip_markup()
                    markup.inline_keyboard.append(skip_markup.inline_keyboard[0])

                await send_long_message(
                    message,
                    f"✅ Ответ сохранён!\n\nСледующий вопрос:\n\n{next_question_text}",
                    reply_markup=markup
                )
            else:
                await message.answer(
                    "✅ Все вопросы в этом разделе отвечены!",
                    reply_markup=build_profile_actions_markup(section_id)
                )
                await state.set_state(ProfileStates.section_selection)

    except Exception as exc:
        logger.exception("Error handling profile answer for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при сохранении ответа. Попробуй позже.")

async def handle_profile_free_text(message: Message, state: FSMContext) -> None:
    """Handle free text input for profile"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        section_id = state_data.get("section_id")

        if section_id:
            await BACKEND_CLIENT.submit_free_text(token, section_id, text)
            await message.answer(
                f"✅ Свободный рассказ сохранён в раздел!",
                reply_markup=build_main_menu_markup()
            )
        else:
            try:
                result = await BACKEND_CLIENT.submit_general_free_text(token, text)
                saved_sections = result.get("saved_sections", [])
                if saved_sections:
                    sections_list = ", ".join([s.get("section_name", "") for s in saved_sections])
                    await message.answer(
                        f"✅ Текст обработан и распределён по разделам: {sections_list}",
                        reply_markup=build_main_menu_markup()
                    )
                else:
                    await message.answer(
                        "✅ Текст сохранён. Система обработает его и распределит по разделам.",
                        reply_markup=build_main_menu_markup()
                    )
            except Exception as e:
                logger.exception("Error processing general free text: %s", e)
                await message.answer(
                    "✅ Текст сохранён. Система обработает его и распределит по разделам.",
                    reply_markup=build_main_menu_markup()
                )

        await state.clear()

    except Exception as exc:
        logger.exception("Error handling profile free text for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при сохранении текста. Попробуй позже.")

async def handle_profile_add_entry(message: Message, state: FSMContext) -> None:
    """Handle manual entry addition to a section"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        section_id = state_data.get("adding_section_id")

        if not section_id:
            await message.answer("Ошибка: не найден раздел.")
            await state.clear()
            return

        result = await BACKEND_CLIENT.create_section_data_entry(
            access_token=token,
            section_id=section_id,
            content=text
        )

        if result.get("status") == "success":
            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_name = _clean_section_title(section_data.get("section", {}).get("name", "Раздел"), section_data.get("section", {}).get("icon", ""))
            source = state_data.get("adding_source", "profile")
            if source == "settings":
                history_cb = f"profile_history_settings_{section_id}"
                back_cb = f"profile_info_settings_section_{section_id}"
            else:
                history_cb = f"profile_history_{section_id}"
                back_cb = f"profile_info_section_{section_id}"

            await message.answer(
                f"✅ Запись добавлена\n\n{section_name}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗃️ История", callback_data=history_cb)],
                    [InlineKeyboardButton(text="◀️", callback_data=back_cb)]
                ])
            )
        else:
            await message.answer("❌ Ошибка при добавлении записи.")

        await state.clear()

    except Exception as exc:
        logger.exception("Error handling profile add entry: %s", exc)
        await message.answer("Ошибка. Попробуй позже.")
        await state.clear()

async def handle_profile_edit_entry(message: Message, state: FSMContext) -> None:
    """Handle entry editing"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        entry_id = state_data.get("editing_entry_id")
        section_id = state_data.get("editing_section_id")

        if not entry_id or not section_id:
            await message.answer("Ошибка: не найдена запись.")
            await state.clear()
            return

        result = await BACKEND_CLIENT.update_section_data_entry(
            access_token=token,
            data_id=entry_id,
            content=text
        )

        if result.get("status") == "success":
            await message.answer(
                "✅ Запись обновлена!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Посмотреть запись", callback_data=f"profile_entry_{entry_id}")],
                    [InlineKeyboardButton(text="🗃️ История", callback_data=f"profile_history_{section_id}")]
                ])
            )
        else:
            await message.answer("❌ Ошибка при обновлении записи.")

        await state.clear()

    except Exception as exc:
        logger.exception("Error handling profile edit entry: %s", exc)
        await message.answer("Ошибка. Попробуй позже.")
        await state.clear()

async def handle_profile_custom_section(message: Message, state: FSMContext) -> None:
    """Handle custom section creation"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    section_name = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        icon = None
        if section_name and len(section_name) > 0:
            first_char = section_name[0]
            if ord(first_char) > 127:
                icon = first_char
                section_name = section_name[1:].strip()

        result = await BACKEND_CLIENT.create_custom_section(token, section_name, icon)
        section_id = result.get("section_id")

        await message.answer(
            f"✅ Раздел '{section_name}' создан! Теперь можешь добавить в него вопросы через /profile",
            reply_markup=build_main_menu_markup()
        )
        await state.clear()

    except Exception as exc:
        logger.exception("Error creating custom section for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при создании раздела. Попробуй позже.")

