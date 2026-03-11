from typing import Optional
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from bot.backend import BACKEND_CLIENT, get_or_fetch_token
from bot.config import (
    build_profile_sections_markup,
    build_profile_actions_markup,
    build_profile_skip_markup,
    build_profile_settings_markup,
    build_mini_survey_markup,
    build_survey_complete_markup,
    build_free_story_markup,
    build_free_story_add_entry_markup,
    build_section_history_markup,
    build_entry_detail_markup,
    build_entry_edit_markup,
    build_main_menu_markup,
    build_about_me_main_markup,
)
from bot.utils import send_long_message, edit_long_message
from .shared import (
    ProfileStates,
    MAIN_MENU_TEXT,
    logger,
    _clean_section_title,
    _entry_preview_text,
    _section_nav_callback,
    _section_back_callback,
)


async def _mini_survey_header(token: str) -> str:
    """Build header with progress for fixed mini-survey questions."""
    try:
        sections_data = await BACKEND_CLIENT.get_profile_sections(token)
        sections = sections_data.get("sections", []) if sections_data else []
        total_questions = 0
        answered_question_ids: set[int] = set()
        for section in sections:
            section_id = section.get("id")
            if not section_id:
                continue
            detail = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_info = detail.get("section", {}) if detail else {}
            questions = section_info.get("questions", []) or []
            total_questions += len(questions)
            try:
                answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
                for answer in (answers_data.get("answers", []) if answers_data else []):
                    qid = answer.get("question_id")
                    if qid:
                        answered_question_ids.add(qid)
            except Exception:
                pass
        if total_questions > 0:
            current = min(len(answered_question_ids) + 1, total_questions)
            return f"👣 Пройти мини-опрос\n\n📋 Вопрос {current} из {total_questions}"
    except Exception:
        pass
    return "👣 Пройти мини-опрос"

from .shared import _clean_section_title, _entry_preview_text, _section_nav_callback, _section_back_callback
from .about_me import find_first_unanswered_question

def _profile_info_menu_callback(source: str) -> str:
    """Back target from a specific info section/history to the 'Информация обо мне' list."""
    return "profile_settings_info" if source == "settings" else "profile_my_info"


def _profile_menu_callback(source: str) -> str:
    """Back target from the 'Информация обо мне' list to the parent profile menu."""
    return "profile_back_to_settings" if source == "settings" else "profile_back"


async def _render_profile_info_menu(callback: CallbackQuery, token: str, source: str = "settings", send_new: bool = False) -> None:
    sections_data = await BACKEND_CLIENT.get_profile_sections(token)
    sections = sections_data.get("sections", []) if sections_data else []

    markup_back = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️", callback_data=_profile_menu_callback(source))]
    ])

    if not sections:
        if send_new:
            await callback.message.answer("📋 Информация обо мне\n\nРазделы пока недоступны.", reply_markup=markup_back)
        else:
            await edit_long_message(callback, "📋 Информация обо мне\n\nРазделы пока недоступны.", reply_markup=markup_back)
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

    buttons.append([InlineKeyboardButton(text="➕ Добавить раздел", callback_data="profile_custom_section")])
    buttons.append([InlineKeyboardButton(text="◀️", callback_data=_profile_menu_callback(source))])

    text = "Информация обо мне"
    markup = InlineKeyboardMarkup(inline_keyboard=buttons)

    if send_new:
        await callback.message.answer(text, reply_markup=markup)
    else:
        await edit_long_message(callback, text, reply_markup=markup)



def _build_profile_info_section_markup(section_id: int, entries: list[dict], source: str = "settings", is_custom: bool = False) -> InlineKeyboardMarkup:
    history_cb = f"profile_history_settings_{section_id}" if source == "settings" else f"profile_history_{section_id}"
    add_cb = f"profile_add_entry_settings_{section_id}" if source == "settings" else f"profile_add_entry_{section_id}"
    back_cb = _profile_info_menu_callback(source)
    buttons = [
        [
            InlineKeyboardButton(text="🗃️ История", callback_data=history_cb),
            InlineKeyboardButton(text="➕ Добавить", callback_data=add_cb),
        ]
    ]
    if is_custom:
        buttons.append([InlineKeyboardButton(text="🗑 Удалить раздел", callback_data=f"profile_delete_section_{source}_{section_id}")])
    buttons.append([
        InlineKeyboardButton(text="◀️ К разделам", callback_data=back_cb),
        InlineKeyboardButton(text="🏠 Меню", callback_data="root_menu"),
    ])
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


def _build_profile_survey_history_markup(section_id: int, answers: list[dict], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    buttons = []
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(answers))

    for i in range(start_idx, end_idx):
        answer = answers[i]
        question_id = answer.get("question_id")
        if question_id is None:
            continue
        preview = _entry_preview_text(answer.get("answer_text", ""), limit=48) or "Ответ"
        buttons.append([
            InlineKeyboardButton(
                text=f"📝 {i + 1}. {preview}"[:64],
                callback_data=f"profile_survey_entry_{question_id}_{section_id}"
            )
        ])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"profile_survey_history_{section_id}_page_{page-1}"))
    if end_idx < len(answers):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"profile_survey_history_{section_id}_page_{page+1}"))
    if nav:
        buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="◀️", callback_data="profile_settings_survey")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_profile_survey_entry_markup(question_id: int, section_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"profile_survey_edit_{question_id}_{section_id}")],
        [InlineKeyboardButton(text="◀️", callback_data=f"profile_survey_history_{section_id}")]
    ])

async def _render_profile_info_section(callback: CallbackQuery, token: str, section_id: int, source: str = "settings") -> None:
    section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
    section = section_data.get("section", {}) if section_data else {}
    if not section:
        await edit_long_message(
            callback,
            "❌ Раздел не найден.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="◀️", callback_data=_profile_info_menu_callback(source))]
            ])
        )
        return

    title = _clean_section_title(section.get("name", "Раздел"), section.get("icon", ""))
    is_custom = section.get("is_custom", False)
    logger.info(f"[render_section] section_id={section_id} name={section.get('name')!r} is_custom={is_custom} user_id={section.get('user_id')}")
    history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
    entries = history_data.get("entries", []) if history_data else []
    text = f"{title}\n\n"
    if entries:
        text += f"Записей: {len(entries)}. Открой историю или добавь новую."
    else:
        text += "Пока не заполнено. Добавь первую запись!"
    await edit_long_message(
        callback,
        text,
        reply_markup=_build_profile_info_section_markup(section_id, entries, source=source, is_custom=is_custom)
    )

async def handle_profile(message: Message, state: FSMContext) -> None:
    """Handle /profile command - show profile settings menu"""
    await state.clear()
    from bot.config import build_profile_settings_markup
    await message.answer(
        "Профиль",
        reply_markup=build_profile_settings_markup()
    )

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
                "➕ Как назовём новый раздел?\n\n"
                "Можешь добавить свой эмодзи в начало: 🎯 Цели\n"
                "Или просто напиши название — выберем эмодзи вместе.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️ Назад", callback_data="profile_settings_info")]
                ])
            )
            await state.set_state(ProfileStates.creating_custom_section)
            await callback.answer()

        elif data == "profile_back":
            await state.clear()
            await callback.message.edit_text(
                "Профиль",
                reply_markup=build_profile_settings_markup()
            )
            await callback.answer()
            return

        elif data == "profile_back_to_settings":
            await state.clear()
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(
                "Профиль",
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

        elif data.startswith("profile_survey_history_"):
            payload = data.removeprefix("profile_survey_history_")
            page = 0
            if "_page_" in payload:
                section_str, page_str = payload.split("_page_", 1)
                section_id = int(section_str)
                page = int(page_str)
            else:
                section_id = int(payload)

            history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
            entries = history_data.get("entries", []) if history_data else []
            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_name = _clean_section_title(
                section_data.get("section", {}).get("name", "Раздел"),
                section_data.get("section", {}).get("icon", "")
            )

            await edit_long_message(
                callback,
                f"🗃️ История раздела\n\n{section_name}\n\n" + ("Выбери запись ниже." if entries else "История пока пуста."),
                reply_markup=_build_profile_survey_history_markup(section_id, entries, page=page)
            )
            await callback.answer()
            return

        elif data.startswith("profile_history_settings_"):
            payload = data.removeprefix("profile_history_settings_")
            page = 0
            if "_page_" in payload:
                section_str, page_str = payload.split("_page_", 1)
                section_id = int(section_str)
                page = int(page_str)
            else:
                section_id = int(payload)

            history_data = await BACKEND_CLIENT.get_section_history(token, section_id)
            entries = history_data.get("entries", []) if history_data else []
            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_name = _clean_section_title(
                section_data.get("section", {}).get("name", "Раздел"),
                section_data.get("section", {}).get("icon", "")
            )

            await edit_long_message(
                callback,
                f"🗃️ История раздела\n\n{section_name}\n\n" + ("Выбери запись ниже." if entries else "История пока пуста."),
                reply_markup=_build_profile_history_markup(section_id, entries, source="settings", page=page)
            )
            await callback.answer()
            return

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
                        except (ValueError, AttributeError):
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

        elif data.startswith("profile_survey_entry_"):
            payload = data.removeprefix("profile_survey_entry_")
            entry_str, section_str = payload.split("_", 1)
            entry_id = int(entry_str)
            section_id = int(section_str)

            answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
            answers = answers_data.get("answers", []) if answers_data else []
            answer = next((item for item in answers if item.get("question_id") == entry_id), None)

            if not answer:
                await callback.answer("Ответ не найден")
                return

            content = answer.get("answer_text", "")
            subblock = None
            created_at = answer.get("created_at", "")
            date_str = ""
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass

            entry_text = "📝 Запись\n\n"
            if subblock:
                entry_text += f"📌 Подблок: {subblock}\n"
            if date_str:
                entry_text += f"📅 {date_str}\n"
            entry_text += f"\n💬 Содержание:\n{content}"

            await edit_long_message(
                callback,
                entry_text,
                reply_markup=_build_profile_survey_entry_markup(entry_id, section_id)
            )
            await callback.answer()
            return

        elif data.startswith("profile_survey_edit_"):
            payload = data.removeprefix("profile_survey_edit_")
            entry_str, section_str = payload.split("_", 1)
            entry_id = int(entry_str)
            section_id = int(section_str)

            answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
            answers = answers_data.get("answers", []) if answers_data else []
            answer = next((item for item in answers if item.get("question_id") == entry_id), None)

            if not answer:
                await callback.answer("Ответ не найден")
                return

            await state.update_data(
                editing_entry_id=entry_id,
                editing_section_id=section_id,
                editing_content=answer.get("answer_text", ""),
                editing_source="survey_answer",
                editing_question_id=entry_id
            )
            await state.set_state(ProfileStates.editing_entry)

            await edit_long_message(
                callback,
                f"✏️ Редактирование записи\n\nТекущее содержание:\n{entry.get('content', '')}\n\nНапиши новое содержание:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️", callback_data=f"profile_survey_entry_{entry_id}_{section_id}")]
                ])
            )
            await callback.answer()
            return

        elif data.startswith("profile_entry_settings_"):
            payload = data.removeprefix("profile_entry_settings_")
            entry_str, section_str = payload.split("_", 1)
            entry_id = int(entry_str)
            section_id = int(section_str)

            answers_data = await BACKEND_CLIENT.get_user_answers_for_section(token, section_id)
            answers = answers_data.get("answers", []) if answers_data else []
            answer = next((item for item in answers if item.get("question_id") == entry_id), None)

            if not answer:
                await callback.answer("Ответ не найден")
                return

            content = answer.get("answer_text", "")
            subblock = None
            created_at = answer.get("created_at", "")

            date_str = ""
            if created_at:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = dt.strftime("%d.%m.%Y %H:%M")
                except Exception:
                    pass

            entry_text = "📝 Запись\n\n"
            if subblock:
                entry_text += f"📌 Подблок: {subblock}\n"
            if date_str:
                entry_text += f"📅 {date_str}\n"
            entry_text += f"\n💬 Содержание:\n{content}"

            await edit_long_message(
                callback,
                entry_text,
                reply_markup=_build_profile_entry_detail_markup(entry_id, section_id, source="settings")
            )
            await callback.answer()
            return

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
                except (ValueError, AttributeError):
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
                editing_content=entry.get("content", ""),
                editing_source="profile"
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

        elif data.startswith("profile_emoji_"):
            emoji_choice = data.removeprefix("profile_emoji_")
            state_data = await state.get_data()
            section_name = state_data.get("pending_section_name", "Новый раздел")
            icon = None if emoji_choice == "none" else emoji_choice

            try:
                await BACKEND_CLIENT.create_custom_section(token, section_name, icon)
                await state.clear()

                sections_data = await BACKEND_CLIENT.get_profile_sections(token)
                sections = sections_data.get("sections", []) if sections_data else []
                buttons = []
                for section in sections:
                    sid = section.get("id")
                    if not sid or sid == 14:
                        continue
                    title = _clean_section_title(section.get("name", "Раздел"), section.get("icon", ""))
                    buttons.append([InlineKeyboardButton(text=title[:64], callback_data=_section_nav_callback(sid, "settings"))])
                buttons.append([InlineKeyboardButton(text="➕ Добавить раздел", callback_data="profile_custom_section")])
                buttons.append([InlineKeyboardButton(text="◀️", callback_data="profile_back_to_settings")])

                await edit_long_message(
                    callback,
                    "✅ Раздел создан!\n\nИнформация обо мне",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
                )
            except Exception as e:
                logger.exception("Error creating section after emoji choice: %s", e)
                await callback.answer("❌ Ошибка при создании раздела")
            await callback.answer()

        elif data.startswith("profile_delete_section_"):
            payload = data.removeprefix("profile_delete_section_")
            parts = payload.split("_", 1)
            if len(parts) == 2 and parts[0] in {"settings", "profile"}:
                source = parts[0]
                section_id = int(parts[1])
            else:
                source = "settings"
                section_id = int(payload)
            await edit_long_message(
                callback,
                "🗑 Удалить раздел?\n\nЭто действие нельзя отменить. Все записи в разделе будут удалены.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"profile_confirm_delete_section_{source}_{section_id}")],
                    [InlineKeyboardButton(text="◀️ Отмена", callback_data=_section_nav_callback(section_id, source))]
                ])
            )
            await callback.answer()

        elif data.startswith("profile_confirm_delete_section_"):
            await callback.answer()
            payload = data.removeprefix("profile_confirm_delete_section_")
            parts = payload.split("_", 1)
            if len(parts) == 2 and parts[0] in {"settings", "profile"}:
                source = parts[0]
                section_id = int(parts[1])
            else:
                source = "settings"
                section_id = int(payload)
            logger.info(f"User {callback.from_user.id} confirming delete of section {section_id} from source={source}")
            try:
                result = await BACKEND_CLIENT.delete_section(token, section_id)
                logger.info(f"Delete section {section_id} result: {result}")
                await _render_profile_info_menu(callback, token, source=source, send_new=False)
            except Exception as e:
                logger.exception(f"Error deleting section {section_id}: {e}")
                err_text = str(e)
                menu_cb = "profile_settings_info" if source == "settings" else "profile_my_info"
                if "403" in err_text:
                    await edit_long_message(
                        callback,
                        "❌ Этот раздел нельзя удалить.\n\n"
                        "Разделы созданные до обновления бота привязаны к старым данным. "
                        "Создай новый раздел — он удалится без проблем.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="◀️ К разделам", callback_data=menu_cb)]
                        ])
                    )
                else:
                    await edit_long_message(
                        callback,
                        f"❌ Ошибка при удалении раздела.\n\nПопробуй позже.",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="◀️ К разделам", callback_data=menu_cb)]
                        ])
                    )

        

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
            await state.clear()
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

        elif data.startswith("profile_add_entry_settings_"):
            section_id = int(data.removeprefix("profile_add_entry_settings_"))

            await state.update_data(adding_section_id=section_id, adding_source="settings")
            await state.set_state(ProfileStates.adding_entry)

            section_data = await BACKEND_CLIENT.get_section_detail(token, section_id)
            section_name = _clean_section_title(
                section_data.get("section", {}).get("name", "Раздел"),
                section_data.get("section", {}).get("icon", "")
            )

            await edit_long_message(
                callback,
                f"➕ Добавить запись\n\n{section_name}\n\nНапиши содержание записи:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="◀️", callback_data=f"profile_info_settings_section_{section_id}")]
                ])
            )
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
                            "🎉 Базовый профиль завершён!\n\n"
                            "Ты ответил на все вопросы.\n"
                            "Теперь GPT знает тебя значительно лучше.\n\n"
                            "Что дальше?",
                            reply_markup=build_survey_complete_markup()
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

                combined_markup = build_mini_survey_markup(
                    next_question_id if next_question_id else -1,
                    can_skip=is_optional,
                    history_callback=f"profile_survey_history_{next_section_id}"
                )

                if section_info:
                    header = await _mini_survey_header(token)
                    await send_long_message(
                        message,
                        f"✅ Ответ сохранён!\n\n"
                        f"{header}\n\n"
                        f"📋 {section_info.get('name', 'Следующий раздел')}\n\n"
                        f"❓ {question_text}",
                        reply_markup=combined_markup
                    )
                else:
                    header = await _mini_survey_header(token)
                    await send_long_message(
                        message,
                        f"✅ Ответ сохранён!\n\n"
                        f"{header}\n\n"
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

                    combined_markup = build_mini_survey_markup(
                        next_question.get("id"),
                        can_skip=is_optional,
                        history_callback=f"profile_survey_history_{next_section_id}"
                    )

                    header = await _mini_survey_header(token)
                    await send_long_message(
                        message,
                        f"✅ Раздел завершён!\n\n"
                        f"{header}\n\n"
                        f"📋 {section_info.get('name', 'Следующий раздел')}\n\n"
                        f"❓ {question_text}",
                        reply_markup=combined_markup
                    )
                else:
                    await state.clear()
                    await message.answer(
                        "🎉 Базовый профиль завершён!\n\n"
                        "Ты ответил на все вопросы.\n"
                        "Теперь GPT знает тебя значительно лучше.\n\n"
                        "Что дальше?",
                        reply_markup=build_survey_complete_markup()
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
            source = state_data.get("editing_source", "profile")
            if source == "survey_answer":
                question_id = state_data.get("editing_question_id", entry_id)
                result = await BACKEND_CLIENT.submit_profile_answer(token, section_id, question_id, text)
                if result.get("status") == "success":
                    await message.answer(
                        "✅ Ответ обновлён!",
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                            [InlineKeyboardButton(text="📝 Посмотреть ответ", callback_data=f"profile_survey_entry_{question_id}_{section_id}")],
                            [InlineKeyboardButton(text="🗃️ История", callback_data=f"profile_survey_history_{section_id}")]
                        ])
                    )
                else:
                    await message.answer("❌ Ошибка при обновлении ответа.")
                await state.clear()
                return
            elif source == "survey":
                view_cb = f"profile_survey_entry_{entry_id}_{section_id}"
                history_cb = f"profile_survey_history_{section_id}"
            else:
                view_cb = f"profile_entry_{entry_id}"
                history_cb = f"profile_history_{section_id}"

            await message.answer(
                "✅ Запись обновлена!",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📝 Посмотреть запись", callback_data=view_cb)],
                    [InlineKeyboardButton(text="🗃️ История", callback_data=history_cb)]
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
    section_name = (message.text or "").strip()

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        # Извлекаем эмодзи если пользователь поставил его в начало
        icon = None
        import re as _re
        # Надёжный паттерн для эмодзи в начале строки
        _emoji_pattern = _re.compile(
            r'^([\U0001F300-\U0001F9FF'
            r'\U00002600-\U000027BF'
            r'\U0001FA00-\U0001FA9F'
            r'\u2702-\u27B0'
            r'\u24C2-\U0001F251'
            r']+)'
        )
        emoji_match = _emoji_pattern.match(section_name)
        if emoji_match:
            icon = emoji_match.group(1)
            section_name = section_name[len(icon):].strip()

        # Если эмодзи нет — предлагаем выбрать из готовых вариантов по смыслу
        if not icon:
            # Сохраняем имя раздела в state и предлагаем эмодзи
            await state.update_data(pending_section_name=section_name)
            emoji_options = [
                ("⭐️", "profile_emoji_⭐️"), ("🎯", "profile_emoji_🎯"),
                ("💡", "profile_emoji_💡"), ("❤️", "profile_emoji_❤️"),
                ("🌿", "profile_emoji_🌿"), ("🏆", "profile_emoji_🏆"),
                ("🎨", "profile_emoji_🎨"), ("✈️", "profile_emoji_✈️"),
                ("💼", "profile_emoji_💼"), ("📖", "profile_emoji_📖"),
                ("🏠", "profile_emoji_🏠"), ("🎵", "profile_emoji_🎵"),
            ]
            buttons = []
            row = []
            for emoji, cb in emoji_options:
                row.append(InlineKeyboardButton(text=emoji, callback_data=cb))
                if len(row) == 4:
                    buttons.append(row)
                    row = []
            if row:
                buttons.append(row)
            buttons.append([InlineKeyboardButton(text="➡️ Без эмодзи", callback_data="profile_emoji_none")])
            buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="profile_settings_info")])
            await message.answer(
                f"Раздел «{section_name}»\n\nВыбери эмодзи для раздела:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            return

        # Эмодзи уже есть — создаём раздел сразу
        result = await BACKEND_CLIENT.create_custom_section(token, section_name, icon)
        await state.clear()

        sections_data = await BACKEND_CLIENT.get_profile_sections(token)
        sections = sections_data.get("sections", []) if sections_data else []
        buttons = []
        for section in sections:
            sid = section.get("id")
            if not sid or sid == 14:
                continue
            title = _clean_section_title(section.get("name", "Раздел"), section.get("icon", ""))
            buttons.append([InlineKeyboardButton(text=title[:64], callback_data=_section_nav_callback(sid, "settings"))])
        buttons.append([InlineKeyboardButton(text="➕ Добавить раздел", callback_data="profile_custom_section")])
        buttons.append([InlineKeyboardButton(text="◀️", callback_data="profile_back_to_settings")])

        await message.answer(
            f"✅ Раздел создан!\n\nИнформация обо мне",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
        )

    except Exception as exc:
        logger.exception("Error creating custom section for %s: %s", telegram_id, exc)
        await message.answer("Ошибка при создании раздела. Попробуй позже.")
