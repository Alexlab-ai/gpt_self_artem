from .shared import *
from .profile import _render_profile_info_menu, _render_profile_info_section
from .about_me import _start_mini_survey

async def handle_main_settings(message: Message, state: FSMContext) -> None:
    """Handle main settings button - show settings menu"""
    settings_text = (
        "⚙️ Настройки\n\n"
        "Выбери раздел настроек:"
    )
    await message.answer(settings_text, reply_markup=build_main_settings_markup())

async def handle_main_settings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle main settings callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    if data == "main_settings_back":
        await callback.message.delete()
        await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
        await callback.answer()
        return

    if data == "main_settings_reminders":
        await callback.message.edit_text(
            "🔔 Напоминания\n\n"
            "Настрой напоминания для регулярной практики.",
            reply_markup=build_reminders_settings_markup(reminders_enabled=False)
        )
        await callback.answer()
        return

    if data == "main_settings_language":
        await callback.message.edit_text(
            "🌐 Язык интерфейса\n\n"
            "Выбери язык:",
            reply_markup=build_language_settings_markup("ru")
        )
        await callback.answer()
        return

    if data == "main_settings_profile":
        await callback.message.edit_text(
            "🪪 Мой профиль\n\n"
            "Настройки профиля:",
            reply_markup=build_profile_settings_markup()
        )
        await callback.answer()
        return

    if data == "main_settings_steps":
        try:
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if not token:
                await callback.answer("Ошибка авторизации")
                return

            settings_text = (
                "⚙️ Настройки работы по шагу\n\n"
                "Выбери шаг и вопрос для работы:"
            )

            await callback.message.edit_text(
                settings_text,
                reply_markup=build_steps_settings_markup()
            )
        except Exception as e:
            logger.exception("Error loading steps settings: %s", e)
            await callback.answer("Ошибка загрузки настроек")
        await callback.answer()
        return

    await callback.answer()

async def handle_language_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle language selection"""
    data = callback.data

    if data == "lang_ru":
        await callback.message.edit_text(
            "🌐 Язык интерфейса\n\n"
            "✅ Выбран русский язык.",
            reply_markup=build_language_settings_markup("ru")
        )
        await callback.answer("Выбран русский язык")
        return

    if data == "lang_en":
        await callback.message.edit_text(
            "🌐 Interface Language\n\n"
            "✅ English selected.\n\n"
            "(English interface coming soon)",
            reply_markup=build_language_settings_markup("en")
        )
        await callback.answer("English selected (coming soon)")
        return

    await callback.answer()

async def handle_step_settings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle step-specific settings callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    if data == "step_settings_select_step":
        try:
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if token:
                steps_data = await BACKEND_CLIENT.get_all_steps(token)
                steps = steps_data.get("steps", []) if steps_data else []

                await callback.message.edit_text(
                    "🪜 Выбрать шаг вручную\n\n"
                    "Выбери номер шага:",
                    reply_markup=build_settings_steps_list_markup(steps)
                )
        except Exception as e:
            logger.exception("Error loading steps: %s", e)
            await callback.answer("Ошибка загрузки шагов")
        await callback.answer()
        return

    if data.startswith("step_settings_select_") and data != "step_settings_select_question":
        try:
            step_id = int(data.split("_")[-1])
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if token:
                result = await BACKEND_CLIENT.switch_step(token, step_id)
                if result:
                    await callback.message.edit_text(
                        f"✅ Переключено на шаг {step_id}\n\n"
                        "Теперь ты работаешь с этим шагом.",
                        reply_markup=build_step_settings_markup()
                    )
                else:
                    await callback.answer("Ошибка переключения шага")
        except (ValueError, Exception) as e:
            logger.exception("Error switching step: %s", e)
            await callback.answer("Ошибка переключения шага")
        await callback.answer()
        return

    if data == "step_settings_select_question":
        try:
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if token:
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                if step_info and step_info.get("step_id"):
                    step_id = step_info.get("step_id")
                    step_number = step_info.get("step_number", step_id)

                    questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                    questions = questions_data.get("questions", []) if questions_data else []

                    if questions:
                        await callback.message.edit_text(
                            f"🗂 Выбрать вопрос вручную\n\n"
                            f"Шаг {step_number}\n"
                            "Выбери номер вопроса:",
                            reply_markup=build_settings_questions_list_markup(questions, step_id)
                        )
                    else:
                        await callback.answer("В этом шаге нет вопросов")
                else:
                    await callback.answer("Нет активного шага. Сначала выбери шаг.")
        except Exception as e:
            logger.exception("Error loading questions: %s", e)
            await callback.answer("Ошибка загрузки вопросов")
        await callback.answer()
        return


    if data.startswith("step_settings_question_"):
        try:
            question_id = int(data.split("_")[-1])
            token = await get_or_fetch_token(telegram_id, username, first_name)
            if token:
                result = await BACKEND_CLIENT.switch_to_question(token, question_id)
                if result:
                    await callback.message.edit_text(
                        f"✅ Переключено на вопрос {question_id}\n\n"
                        "Теперь ты работаешь с этим вопросом.",
                        reply_markup=build_step_settings_markup()
                    )
                else:
                    await callback.answer("Ошибка переключения вопроса")
        except Exception as e:
            logger.exception("Error switching question: %s", e)
            await callback.answer("Ошибка переключения вопроса")
        await callback.answer()
        return

    await callback.answer()

async def handle_profile_settings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle profile settings callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id

    try:
        if data == "profile_settings_back":
            await callback.message.edit_text(
                "⚙️ Настройки\n\n"
                "Выбери раздел настроек:",
                reply_markup=build_main_settings_markup()
            )
            await callback.answer()
            return

        if data in {"profile_settings_about", "profile_settings_survey"}:
            await callback.answer("Загружаю опрос...")
            try:
                await _start_mini_survey(callback, state)
            except Exception as e:
                logger.exception("Error loading mini survey: %s", e)
                await callback.message.edit_text(
                    f"❌ Ошибка загрузки опроса.\n\n{str(e)[:120]}",
                    reply_markup=build_profile_settings_markup()
                )
            return

        if data == "profile_settings_info":
            await callback.answer("Загружаю информацию...")
            username = callback.from_user.username
            first_name = callback.from_user.first_name
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if not token:
                    await callback.message.edit_text(
                        "❌ Ошибка авторизации. Нажми /start.",
                        reply_markup=build_profile_settings_markup()
                    )
                    return
                await _render_profile_info_menu(callback, token, source="settings")
            except Exception as e:
                logger.exception("Error loading profile info: %s", e)
                await callback.message.edit_text(
                    "❌ Ошибка загрузки информации. Попробуй позже.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="◀️", callback_data="profile_back_to_settings")]
                    ])
                )
            return

        if data.startswith("profile_settings_view_"):
            section_id = data.replace("profile_settings_view_", "")
            await callback.answer("Загружаю раздел...")
            username = callback.from_user.username
            first_name = callback.from_user.first_name
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if not token:
                    await callback.answer("Ошибка авторизации")
                    return
                await _render_profile_info_section(callback, token, int(section_id), source="settings")
            except Exception as e:
                logger.exception("Error viewing section: %s", e)
                await callback.answer("Ошибка загрузки раздела")
            return

        if data == "profile_settings_back":
            await callback.message.edit_text(
                "🪪 Мой профиль\n\n"
                "Настройки профиля:",
                reply_markup=build_profile_settings_markup()
            )
            await callback.answer()
            return

        if data.startswith("profile_settings_view_"):
            section_id = data.replace("profile_settings_view_", "")
            await callback.answer("Загружаю раздел...")
            username = callback.from_user.username
            first_name = callback.from_user.first_name
            
            try:
                token = await get_or_fetch_token(telegram_id, username, first_name)
                if not token:
                    await callback.answer("Ошибка авторизации")
                    return
                
                section_detail = await BACKEND_CLIENT.get_section_detail(token, int(section_id))
                if not section_detail:
                    await callback.answer("Раздел не найден")
                    return
                
                section_info = section_detail.get("section", {})
                section_name = section_info.get("name", "Раздел")
                section_icon = section_info.get("icon", "📁")
                questions = section_info.get("questions", [])
                entries = section_info.get("entries", [])
                
                answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, int(section_id))
                answers = answers_data.get("answers", []) if answers_data else []
                
                text_parts = [f"{section_icon} {section_name}\n"]
                
                if answers:
                    text_parts.append("\n📝 Ответы на вопросы:\n")
                    for answer in answers[:5]:
                        q_text = answer.get("question_text", "Вопрос")[:50]
                        a_text = answer.get("answer_text", "")[:100]
                        text_parts.append(f"• {q_text}...\n  ➜ {a_text}...\n")
                    if len(answers) > 5:
                        text_parts.append(f"... и ещё {len(answers) - 5} ответов\n")
                
                if entries:
                    text_parts.append("\n📄 Записи:\n")
                    for entry in entries[:3]:
                        content = entry.get("content", "")[:100]
                        text_parts.append(f"• {content}...\n")
                    if len(entries) > 3:
                        text_parts.append(f"... и ещё {len(entries) - 3} записей\n")
                
                if not answers and not entries:
                    text_parts.append("\nПока нет сохраненной информации в этом разделе.")
                
                buttons = [
                    [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"profile_section_{section_id}")],
                    [InlineKeyboardButton(text="◀️ Назад к списку", callback_data="profile_settings_info")]
                ]
                
                await callback.message.edit_text(
                    "".join(text_parts),
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
            except Exception as e:
                logger.exception("Error viewing section: %s", e)
                await callback.answer("Ошибка загрузки раздела")
            return

        await callback.answer()
    except Exception as e:
        logger.exception("Error in handle_profile_settings_callback: %s", e)
        try:
            await callback.answer("Ошибка. Попробуй позже.")
        except:
            pass

