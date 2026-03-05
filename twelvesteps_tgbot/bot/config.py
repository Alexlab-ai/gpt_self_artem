"""Shared configuration and markup helpers for the Telegram frontend."""

from __future__ import annotations

import os
from typing import List, Optional, Dict, Any

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
import pathlib

env_path = pathlib.Path(__file__).parent.parent.parent / "telegram.env"
load_dotenv(env_path)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set")

BACKEND_API_BASE = (
    os.getenv("BACKEND_API_BASE_URL")
    or os.getenv("BACKEND_URL")
    or "http://127.0.0.1:8000"
)
BACKEND_CHAT_URL = os.getenv("BACKEND_CHAT_URL", f"{BACKEND_API_BASE.rstrip('/')}/chat")

PROGRAM_EXPERIENCE_OPTIONS: List[str] = ["Новичок", "Есть немного опыта", "Бывалый"]


def build_main_menu_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🪜 Работа по шагу"), KeyboardButton(text="📖 Самоанализ")],
            [KeyboardButton(text="📘 Чувства"), KeyboardButton(text="🙏 Благодарности")],
            [KeyboardButton(text="⚙️ Настройки"), KeyboardButton(text="📎 Инструкция")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def build_experience_markup() -> ReplyKeyboardMarkup:
    """Inline keyboard for selecting program experience."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=option)] for option in PROGRAM_EXPERIENCE_OPTIONS],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_exit_markup() -> ReplyKeyboardMarkup:
    """Minimal keyboard that offers an /exit option during onboarding."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/exit")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_skip_markup() -> ReplyKeyboardMarkup:
    """Simple markup that highlights /skip for optional questions."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="/skip")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def build_error_markup() -> ReplyKeyboardMarkup:
    """Keyboard shown when errors occur, offering restart option."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/start")],
            [KeyboardButton(text="/reset")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )



def build_profile_sections_markup(sections: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    buttons = []
    row = []

    for section in sections:
        section_id = section.get("id")
        if section_id == 14:
            continue

        name = section.get("name", "")
        button_text = name[:60] + "..." if len(name) > 60 else name

        row.append(InlineKeyboardButton(
            text=button_text,
            callback_data=f"profile_section_{section_id}"
        ))

        if len(row) >= 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(text="✍️ Свободный рассказ", callback_data="profile_free_text"),
        InlineKeyboardButton(text="➕ Добавить свой блок", callback_data="profile_custom_section")
    ])
    
    buttons.append([
        InlineKeyboardButton(text="📋 Информация обо мне", callback_data="profile_my_info")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_profile_actions_markup(section_id: int) -> InlineKeyboardMarkup:
    """Build action buttons for a profile section."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Свободный рассказ", callback_data=f"profile_free_text_{section_id}")],
        [
            InlineKeyboardButton(text="🗃️ История", callback_data=f"profile_history_{section_id}"),
            InlineKeyboardButton(text="➕ Добавить", callback_data=f"profile_add_entry_{section_id}")
        ],
        [InlineKeyboardButton(text="⏪ Назад", callback_data="profile_back")]
    ])


def build_section_history_markup(section_id: int, entries: List[Dict[str, Any]], page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Build markup for section history with pagination and edit buttons."""
    buttons = []

    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(entries))

    for i in range(start_idx, end_idx):
        entry = entries[i]
        entry_id = entry.get("id")
        preview = entry.get("content", "")[:40] + "..." if len(entry.get("content", "")) > 40 else entry.get("content", "")
        subblock = entry.get("subblock_name")

        button_text = f"📝 {i+1}. "
        if subblock:
            button_text += f"{subblock}: {preview}"
        else:
            button_text += preview

        if len(button_text) > 60:
            button_text = button_text[:57] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"profile_entry_{entry_id}"
            )
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Предыдущие", callback_data=f"profile_history_{section_id}_page_{page-1}"))
    if end_idx < len(entries):
        nav_buttons.append(InlineKeyboardButton(text="Следующие ▶️", callback_data=f"profile_history_{section_id}_page_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([
        InlineKeyboardButton(text="➕ Добавить запись", callback_data=f"profile_add_entry_{section_id}"),
        InlineKeyboardButton(text="⏪ Назад", callback_data=f"profile_section_{section_id}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_entry_detail_markup(entry_id: int, section_id: int) -> InlineKeyboardMarkup:
    """Build markup for entry detail view with edit/delete options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"profile_edit_{entry_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"profile_delete_{entry_id}")
        ],
        [InlineKeyboardButton(text="⏪ Назад к истории", callback_data=f"profile_history_{section_id}")]
    ])


def build_entry_edit_markup(entry_id: int, section_id: int) -> InlineKeyboardMarkup:
    """Build markup for entry editing."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Сохранить", callback_data=f"profile_save_edit_{entry_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"profile_entry_{entry_id}")]
    ])


def build_profile_skip_markup() -> InlineKeyboardMarkup:
    """Markup for skipping optional questions."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="profile_skip")]
    ])



def build_template_selection_markup() -> InlineKeyboardMarkup:
    """Markup for selecting answer template on first /steps entry."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧩 Авторский шаблон", callback_data="template_author")],
        [InlineKeyboardButton(text="✍️ Свой шаблон", callback_data="template_custom")]
    ])



def build_sos_help_type_markup() -> InlineKeyboardMarkup:
    """Markup for selecting type of help in SOS."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💭 Не понял вопрос", callback_data="sos_help_question")],
        [InlineKeyboardButton(text="🔍 Хочу примеры", callback_data="sos_help_examples")],
        [InlineKeyboardButton(text="🪫 Просто тяжело", callback_data="sos_help_support")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="sos_back")],
    ])

def build_sos_save_draft_markup() -> InlineKeyboardMarkup:
    """Markup for saving SOS conversation as draft."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, сохранить", callback_data="sos_save_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="sos_save_no")]
    ])

def build_sos_exit_markup() -> InlineKeyboardMarkup:
    """Markup for exiting SOS chat."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="sos_back")]
    ])



def build_steps_navigation_markup() -> InlineKeyboardMarkup:
    """Markup for steps navigation menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔢 Выбрать другой шаг", callback_data="steps_select")],
        [InlineKeyboardButton(text="📋 Показать список вопросов", callback_data="steps_questions")],
        [InlineKeyboardButton(text="▶️ Продолжить", callback_data="steps_continue")]
    ])

def build_steps_list_markup(steps: list[dict]) -> InlineKeyboardMarkup:
    """Markup for selecting a step (1-12)."""
    import logging
    logger = logging.getLogger(__name__)

    buttons = []
    for i in range(0, len(steps), 3):
        row = []
        for j in range(3):
            if i + j < len(steps):
                step = steps[i + j]
                step_id = step.get('id')
                step_number = step.get('number')

                if step_id is None:
                    logger.warning(f"Step {i+j} has no 'id': {step}")
                    continue
                if step_number is None:
                    logger.warning(f"Step {i+j} has no 'number': {step}")
                    step_number = step_id

                row.append(InlineKeyboardButton(
                    text=f"Шаг {step_number}",
                    callback_data=f"step_select_{step_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="steps_back")])
    logger.info(f"Built steps list markup with {len(buttons)-1} rows of step buttons")
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_step_questions_markup(questions: list[dict], step_id: int) -> InlineKeyboardMarkup:
    """Markup for listing questions in a step."""
    buttons = []
    for i, q in enumerate(questions, 1):
        question_text = q.get("text", "")[:40] + "..." if len(q.get("text", "")) > 40 else q.get("text", "")
        buttons.append([InlineKeyboardButton(
            text=f"{i}. {question_text}",
            callback_data=f"question_view_{q['id']}"
        )])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="steps_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_settings_steps_list_markup(steps: list[dict]) -> InlineKeyboardMarkup:
    """Markup for selecting a step in settings (1-12)."""
    buttons = []
    for i in range(0, len(steps), 3):
        row = []
        for j in range(3):
            if i + j < len(steps):
                step = steps[i + j]
                step_id = step.get('id')
                step_number = step.get('number')

                if step_id is None or step_number is None:
                    continue

                row.append(InlineKeyboardButton(
                    text=f"{step_number}",
                    callback_data=f"step_settings_select_{step_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_steps")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_settings_questions_list_markup(questions: list[dict], step_id: int) -> InlineKeyboardMarkup:
    """Markup for selecting a question in settings - shows questions as squares (3 per row)."""
    buttons = []
    for i in range(0, len(questions), 3):
        row = []
        for j in range(3):
            if i + j < len(questions):
                q = questions[i + j]
                q_id = q.get('id')
                q_number = i + j + 1

                if q_id is None:
                    continue

                row.append(InlineKeyboardButton(
                    text=f"{q_number}",
                    callback_data=f"step_settings_question_{q_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_steps")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_settings_select_step_for_question_markup(steps: list[dict]) -> InlineKeyboardMarkup:
    """Markup for selecting a step first, then question."""
    buttons = []
    for i in range(0, len(steps), 3):
        row = []
        for j in range(3):
            if i + j < len(steps):
                step = steps[i + j]
                step_id = step.get('id')
                step_number = step.get('number')

                if step_id is None or step_number is None:
                    continue

                row.append(InlineKeyboardButton(
                    text=f"{step_number}",
                    callback_data=f"step_settings_question_step_{step_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_steps")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def format_step_progress_indicator(
    step_number: int,
    total_steps: int,
    step_title: Optional[str] = None,
    answered_questions: Optional[int] = None,
    total_questions: Optional[int] = None
) -> str:
    from typing import Optional

    indicator_parts = []

    step_text = f"Шаг {step_number}"
    if step_title:
        step_text += f" — {step_title}"
    indicator_parts.append(step_text)

    if answered_questions is not None and total_questions is not None and total_questions > 0:
        current_question = answered_questions + 1
        question_text = f"Вопрос {current_question} из {total_questions}"
        indicator_parts.append(question_text)

    return "\n".join(indicator_parts)


def build_step_actions_markup(has_template_progress: bool = False, show_description: bool = False) -> InlineKeyboardMarkup:
    """Markup for step actions during answering."""
    buttons = []

    buttons.append([
        InlineKeyboardButton(text="▶️ Продолжить", callback_data="step_continue"),
        InlineKeyboardButton(text="📋 Мой прогресс", callback_data="step_progress")
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🔽 Свернуть описание" if show_description else "🧾 Описание шага",
            callback_data="step_toggle_description"
        )
    ])

    buttons.append([
        InlineKeyboardButton(text="◀️ Назад", callback_data="steps_back"),
        InlineKeyboardButton(text="🧭 Помощь", callback_data="sos_help")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_step_answer_mode_markup() -> InlineKeyboardMarkup:
    """Markup for answer mode with draft controls."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 Сохранить черновик", callback_data="step_save_draft"),
            InlineKeyboardButton(text="📝 Просмотреть черновик", callback_data="step_view_draft")
        ],
        [
            InlineKeyboardButton(text="✏️ Редактировать последний ответ", callback_data="step_edit_last"),
            InlineKeyboardButton(text="🔄 Сбросить", callback_data="step_reset_draft")
        ],
        [
            InlineKeyboardButton(text="✔️ Завершить и перейти", callback_data="step_complete")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="step_back_from_answer")]
    ])


def build_template_filling_markup() -> InlineKeyboardMarkup:
    """Markup for template filling mode - pause and cancel options."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏸ Пауза (сохранить прогресс)", callback_data="tpl_pause")],
        [InlineKeyboardButton(text="❌ Отменить заполнение", callback_data="tpl_cancel")]
    ])


def build_template_situation_complete_markup() -> InlineKeyboardMarkup:
    """Markup shown when a situation is complete."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Продолжить к следующей ситуации", callback_data="tpl_next_situation")],
        [InlineKeyboardButton(text="⏸ Пауза", callback_data="tpl_pause")]
    ])


def build_template_conclusion_markup() -> InlineKeyboardMarkup:
    """Markup shown before conclusion (after 3 situations)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Написать финальный вывод", callback_data="tpl_write_conclusion")],
        [InlineKeyboardButton(text="⏸ Пауза", callback_data="tpl_pause")]
    ])



def build_steps_settings_markup() -> InlineKeyboardMarkup:
    """Markup for steps settings main menu - simplified: only step and question selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪜 Выбрать шаг вручную", callback_data="step_settings_select_step")],
        [InlineKeyboardButton(text="🗂 Выбрать вопрос вручную", callback_data="step_settings_select_question")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")]
    ])

def build_template_selection_settings_markup(templates: list[dict], current_template_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Markup for selecting template in settings."""
    buttons = []
    for template in templates:
        template_id = template.get("id")
        template_name = template.get("name", "")
        template_type = template.get("template_type", "")

        prefix = "✅ " if template_id == current_template_id else ""
        type_indicator = "🧩" if template_type == "AUTHOR" else "✍️"

        buttons.append([InlineKeyboardButton(
            text=f"{prefix}{type_indicator} {template_name}",
            callback_data=f"settings_select_template_{template_id}"
        )])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="settings_template_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def build_reminders_settings_markup(reminders_enabled: bool = False) -> InlineKeyboardMarkup:
    """Markup for reminders settings."""
    enabled_text = "✅ Включены" if reminders_enabled else "❌ Выключены"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⏰ Напоминания: {enabled_text}",
            callback_data="settings_toggle_reminders"
        )],
        [InlineKeyboardButton(text="🕐 Время напоминания", callback_data="settings_reminder_time")],
        [InlineKeyboardButton(text="📅 Дни недели", callback_data="settings_reminder_days")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_reminders_back")]
    ])



def build_main_settings_markup() -> InlineKeyboardMarkup:
    """Main settings menu according to interface spec."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Напоминания", callback_data="main_settings_reminders")],
        [InlineKeyboardButton(text="🌐 Язык интерфейса", callback_data="main_settings_language")],
        [InlineKeyboardButton(text="🪪 Мой профиль", callback_data="main_settings_profile")],
        [InlineKeyboardButton(text="🔧 Настройки по шагу", callback_data="main_settings_steps")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_back")]
    ])


def build_language_settings_markup(current_lang: str = "ru") -> InlineKeyboardMarkup:
    """Language selection menu."""
    ru_prefix = "✅ " if current_lang == "ru" else ""
    en_prefix = "✅ " if current_lang == "en" else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{ru_prefix}🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text=f"{en_prefix}🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_back")]
    ])


def build_step_settings_markup() -> InlineKeyboardMarkup:
    """Step-specific settings menu - simplified: only step and question selection."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪜 Выбрать шаг вручную", callback_data="step_settings_select_step")],
        [InlineKeyboardButton(text="🗂 Выбрать вопрос вручную", callback_data="step_settings_select_question")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="settings_back")]
    ])


def build_profile_settings_markup() -> InlineKeyboardMarkup:
    """Profile settings menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪪 Расскажи о себе", callback_data="profile_settings_about")],
        [InlineKeyboardButton(text="📋 Информация обо мне", callback_data="profile_settings_info")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="main_settings_back")]
    ])


def build_about_me_main_markup() -> InlineKeyboardMarkup:
    """Main menu for 'Tell about yourself' with 2 tabs."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Свободный рассказ", callback_data="about_free_story")],
        [InlineKeyboardButton(text="👣 Пройти мини-опрос", callback_data="about_mini_survey")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="profile_back")]
    ])


def build_free_story_markup() -> InlineKeyboardMarkup:
    """Markup for free story section."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить запись", callback_data="about_add_free")],
        [InlineKeyboardButton(text="🗃️ История", callback_data="about_history_free")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about_back")]
    ])


def build_free_story_add_entry_markup() -> InlineKeyboardMarkup:
    """Markup for adding free story entry (with back button)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about_free_story")]
    ])


def build_mini_survey_markup(question_id: Optional[int] = None, can_skip: bool = False) -> InlineKeyboardMarkup:
    """Markup for mini survey with action buttons."""
    buttons = []
    if can_skip:
        buttons.append([InlineKeyboardButton(text="🔁 Пропустить", callback_data="about_survey_skip")])
    buttons.append([
        InlineKeyboardButton(text="⏸ Пауза", callback_data="about_survey_pause")
    ])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="about_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_about_section_actions_markup(section_id: str) -> InlineKeyboardMarkup:
    """Actions inside an about me section."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить запись", callback_data=f"about_add_{section_id}"),
            InlineKeyboardButton(text="🗃️ История", callback_data=f"about_history_{section_id}")
        ],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="about_back")]
    ])



def build_progress_step_markup(step_id: int, step_number: int, step_title: str) -> InlineKeyboardMarkup:
    """Markup for viewing a specific step's progress."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Посмотреть ответы", callback_data="progress_view_answers")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="progress_main")]
    ])




def build_progress_main_markup(steps: list[dict]) -> InlineKeyboardMarkup:
    """Main progress menu - shows steps as numbers only (like feelings)."""
    buttons = []
    for i in range(0, len(steps), 3):
        row = []
        for j in range(3):
            if i + j < len(steps):
                step = steps[i + j]
                step_id = step.get('id')
                step_number = step.get('number', step_id)

                if step_id is None or step_number is None:
                    continue

                row.append(InlineKeyboardButton(
                    text=f"{step_number}",
                    callback_data=f"progress_step_{step_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="📄 Посмотреть ответы", callback_data="progress_view_answers")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="steps_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_progress_view_answers_steps_markup(steps: list[dict]) -> InlineKeyboardMarkup:
    """Markup for selecting a step to view answers (numbers only, like feelings)."""
    buttons = []
    for i in range(0, len(steps), 3):
        row = []
        for j in range(3):
            if i + j < len(steps):
                step = steps[i + j]
                step_id = step.get('id')
                step_number = step.get('number')

                if step_id is None or step_number is None:
                    continue

                row.append(InlineKeyboardButton(
                    text=f"{step_number}",
                    callback_data=f"progress_answers_step_{step_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="progress_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_progress_view_answers_questions_markup(questions: list[dict], step_id: int, back_callback: str = "progress_view_answers") -> InlineKeyboardMarkup:
    """Markup for selecting a question to view answer (numbers only, like feelings)."""
    buttons = []
    for i in range(0, len(questions), 3):
        row = []
        for j in range(3):
            if i + j < len(questions):
                q = questions[i + j]
                q_id = q.get('id')
                q_number = q.get('number', i + j + 1)

                if q_id is None:
                    continue

                status = q.get("status", "")
                if status == "COMPLETED":
                    emoji = "✅"
                elif status == "IN_PROGRESS" or q.get("answer_preview"):
                    emoji = "⏳"
                else:
                    emoji = "⬜"

                row.append(InlineKeyboardButton(
                    text=f"{emoji} {q_number}",
                    callback_data=f"progress_answers_question_{q_id}"
                ))
        if row:
            buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



def build_thanks_menu_markup() -> InlineKeyboardMarkup:
    """Main gratitude/thanks menu."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить запись", callback_data="thanks_add")],
        [InlineKeyboardButton(text="🗃️ История", callback_data="thanks_history")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="thanks_back")]
    ])


def build_thanks_history_markup(page: int = 1, has_more: bool = False) -> InlineKeyboardMarkup:
    """Pagination for thanks history."""
    buttons = []
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"thanks_page_{page - 1}"))
    if has_more:
        nav_row.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"thanks_page_{page + 1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="thanks_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_thanks_input_markup() -> InlineKeyboardMarkup:
    """Markup shown while user is typing gratitude entry."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💾 Сохранить", callback_data="thanks_save"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="thanks_cancel")
        ]
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)



FEELINGS_CATEGORIES = {
    "😠 ГНЕВ": [
        "бешенство", "ярость", "ненависть", "истерия", "злость", "раздражение",
        "презрение", "негодование", "обида", "ревность", "уязвлённость", "досада",
        "зависть", "неприязнь", "возмущение", "отвращение"
    ],
    "😰 СТРАХ": [
        "ужас", "отчаяние", "испуг", "оцепенение", "подозрение", "тревога",
        "ошарашенность", "беспокойство", "боязнь", "унижение", "замешательство",
        "растерянность", "вина", "стыд", "сомнение", "застенчивость", "опасение",
        "смущение", "сломленность", "надменность", "ошеломлённость"
    ],
    "😢 ГРУСТЬ": [
        "горечь", "тоска", "скорбь", "лень", "жалость", "отрешённость",
        "отчаяние", "беспомощность", "душевная боль", "безнадёжность",
        "отчуждённость", "разочарование", "потрясение", "сожаление", "скука",
        "безысходность", "печаль", "загнанность"
    ],
    "😊 РАДОСТЬ": [
        "счастье", "восторг", "ликование", "приподнятость", "оживление",
        "умиротворение", "увлечение", "интерес", "забота", "ожидание",
        "возбуждение", "предвкушение", "надежда", "любопытство", "освобождение",
        "принятие", "нетерпение", "вера", "изумление"
    ],
    "💗 ЛЮБОВЬ": [
        "нежность", "теплота", "сочувствие", "блаженство", "доверие",
        "безопасность", "благостность", "спокойствие", "симпатия", "гордость",
        "восхищение", "уважение", "самоценность", "влюблённость", "любовь к себе",
        "очарованность", "смирение", "искренность", "дружелюбие", "доброта", "взаимовыручка"
    ],
    "🧠 СОСТОЯНИЯ": [
        "нервозность", "пренебрежение", "недовольство", "вредность", "огорчение",
        "нетерпимость", "вседозволенность", "раскаяние", "безысходность",
        "превосходство", "высокомерие", "неполноценность", "неудобство", "неловкость",
        "апатия", "безразличие", "неуверенность", "тупик", "усталость", "принуждение",
        "одиночество", "отверженность", "подавленность", "холодность", "безучастность",
        "равнодушие", "удовлетворение", "уверенность", "довольство", "окрылённость",
        "торжественность", "жизнерадостность", "облегчение", "ободрённость", "удивление",
        "сопереживание", "сопричастность", "уравновешенность", "смирение",
        "естественность", "жизнелюбие", "вдохновение", "воодушевление"
    ]
}

FEARS_LIST = [
    "страх оценки", "страх ошибки", "страх нового", "страх одиночества",
    "страх ответственности", "страх темноты", "страх высоты",
    "страх разочарования в себе", "страх будущего", "страх за свою жизнь"
]


def build_feelings_categories_markup() -> InlineKeyboardMarkup:
    """Markup for selecting feelings category."""
    buttons = []
    for category in FEELINGS_CATEGORIES.keys():
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"feelings_cat_{category[:10]}")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="feelings_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_feelings_list_markup(category: str) -> InlineKeyboardMarkup:
    """Markup for selecting specific feelings from a category."""
    feelings = []
    for cat_name, cat_feelings in FEELINGS_CATEGORIES.items():
        if cat_name.startswith(category) or category in cat_name:
            feelings = cat_feelings
            break

    buttons = []
    row = []
    for feeling in feelings:
        row.append(InlineKeyboardButton(text=feeling, callback_data=f"feeling_select_{feeling[:15]}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ Назад к категориям", callback_data="feelings_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_all_feelings_markup() -> InlineKeyboardMarkup:
    """Markup with categories to choose from (table is too big for buttons)."""
    buttons = []

    for category in FEELINGS_CATEGORIES.keys():
        buttons.append([InlineKeyboardButton(text=category, callback_data=f"feelings_cat_{category}")])

    buttons.append([InlineKeyboardButton(text="⚠️ СТРАХИ (список)", callback_data="feelings_fears")])
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="feelings_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_feelings_category_markup(category: str) -> InlineKeyboardMarkup:
    """Show feelings from a specific category."""
    feelings = FEELINGS_CATEGORIES.get(category, [])

    buttons = []
    row = []
    for feeling in feelings:
        btn_text = feeling[:18] if len(feeling) > 18 else feeling
        row.append(InlineKeyboardButton(text=btn_text, callback_data=f"feeling_copy_{feeling[:20]}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    buttons.append([InlineKeyboardButton(text="◀️ К категориям", callback_data="feelings_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_fears_markup() -> InlineKeyboardMarkup:
    """Show list of common fears."""
    buttons = []
    for fear in FEARS_LIST:
        buttons.append([InlineKeyboardButton(text=fear, callback_data=f"feeling_copy_{fear[:20]}")])

    buttons.append([InlineKeyboardButton(text="◀️ К категориям", callback_data="feelings_categories")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def format_feelings_table_text() -> str:
    """Format the feelings table as text for display."""
    text = "📘 ТАБЛИЦА ЧУВСТВ\n\n"

    for category, feelings in FEELINGS_CATEGORIES.items():
        text += f"{category}\n"
        feelings_line = ", ".join(feelings)
        text += f"{feelings_line}\n\n"

    text += "⚠️ СТРАХИ:\n"
    text += ", ".join(FEARS_LIST)

    return text



FAQ_SECTIONS = {
    "🪜 Работа по шагу": (
        "🪜 Работа по шагу\n\n"
        "• Что такое шаги?\n"
        "Это 12 ключевых тем, через которые проходит каждый зависимый. Шаги помогают понять своё мышление, чувства, действия и изменить их. Это не теория — это личная практика.\n\n"
        "• Как выбрать шаг и вопрос?\n"
        "Если ты уже работаешь по шагу — продолжай. Если нет — выбери начальный шаг (обычно с 1-го). Внутри шага есть вопросы, которые раскрывают тему. Система запомнит, где ты остановился.\n\n"
        "• Что делать, если не могу ответить?\n"
        "Нажми «🧭 Помощь». Там есть варианты: «Не понял вопрос», «Нужны примеры», «Просто тяжело». GPT подскажет, поможет вспомнить и не даст застрять.\n\n"
        "• Как сохраняется прогресс?\n"
        "Все твои ответы сохраняются автоматически. Ты можешь поставить вопрос на паузу и вернуться. Прогресс виден в разделе «Мой прогресс»."
    ),
    "📖 Самоанализ (10 шаг)": (
        "📖 Самоанализ (10 шаг)\n\n"
        "• Как работает?\n"
        "Каждый день ты отвечаешь на вопросы. Это помогает отслеживать мысли, чувства, ошибки, помогает развиваться.\n\n"
        "• Сколько вопросов?\n"
        "В самоанализе 10 вопросов. Они повторяются ежедневно. Можно делать не все, а столько, сколько успеешь.\n\n"
        "• Делать ли каждый день?\n"
        "Желательно. Это как зарядка для осознанности. Но если не получилось — не страшно. Главное — возвращаться."
    ),
    "📘 Чувства": (
        "📘 Чувства\n\n"
        "• Что такое таблица чувств?\n"
        "Это список эмоций, которые можно выбрать, если сложно назвать, что ты чувствуешь. Они помогают лучше понять себя.\n\n"
        "• Как использовать?\n"
        "Когда заполняешь шаблон, можно открыть таблицу и выбрать подходящие чувства. Особенно это важно в блоке \"Чувства до / после\".\n\n"
        "• Как выбрать нужное чувство?\n"
        "Не обязательно выбирать «правильно». Просто найди то, что ближе всего к тому, как ты ощущаешь. Это не тест."
    ),
    "✍️ О себе": (
        "✍️ О себе\n\n"
        "• Зачем писать?\n"
        "Чем больше ты рассказываешь о себе, тем точнее GPT тебя понимает. Это как знакомство — без давления, но с пользой.\n\n"
        "• Что, если не хочу?\n"
        "Ты можешь пропустить. Но лучше дать хоть немного информации — это поможет в работе по шагам и в поддержке.\n\n"
        "• Что такое \"Свободный рассказ\"?\n"
        "Это раздел, где можно просто написать всё, что хочешь — без вопросов и рамок. GPT сам распределит по темам."
    ),
    "📋 Шаблон ответа": (
        "📋 Шаблон ответа\n\n"
        "• Как выбрать или изменить?\n"
        "Система автоматически использует авторский шаблон. Его можно изменить в настройках шага.\n\n"
        "• Мой vs авторский шаблон?\n"
        "Авторский — проверенная структура (ситуация, мысли, чувства, действия…). Свой — ты настраиваешь сам."
    ),
    "🧭 Помощь": (
        "🧭 Помощь\n\n"
        "• Когда использовать?\n"
        "Когда застрял. Когда не знаешь, что ответить. Когда слишком тяжело. Или просто не понимаешь вопрос.\n\n"
        "• Что значит \"Не понял вопрос\"?\n"
        "GPT переформулирует вопрос и объяснит его.\n\n"
        "• Как работает \"Нужны примеры\"\n"
        "GPT даст тебе 12-18 бытовых ситуаций, где может проявляться тема шага. Это поможет вспомнить свою ситуацию. Если не нашел подходящий пример, нажми еще раз — получишь новые варианты.\n\n"
        "• Что делать, если тяжело?\n"
        "Нажми «Просто тяжело». GPT поддержит тебя. Иногда важно просто не быть одному."
    ),
    "🙏 Благодарности": (
        "🙏 Благодарности\n\n"
        "• Зачем писать?\n"
        "Чтобы учиться видеть хорошее. Благодарность переключает мышление и снижает тревогу.\n\n"
        "• Как часто?\n"
        "Хоть каждый день. Можно 4-5 фраз, за что именно ты сегодня благодарен — это может быть благодарность миру за теплый день и маме за вкусный обед.\n\n"
        "• Кто видит?\n"
        "Только ты. Это твой личный дневник. Никуда не отправляется."
    ),
    "📈 Прогресс": (
        "📈 Прогресс\n\n"
        "• Как посмотреть, что уже сделано?\n"
        "Зайди в «Мой прогресс». Там будут шаги, вопросы, твои ответы и статус каждого.\n\n"
        "• Что такое \"Мой прогресс\"?\n"
        "Это твоя карта движения. Показывает, где ты, что уже пройдено, что осталось."
    ),
}


def build_faq_menu_markup() -> InlineKeyboardMarkup:
    """Markup for FAQ sections menu."""
    buttons = []

    for section_name in FAQ_SECTIONS.keys():
        buttons.append([InlineKeyboardButton(text=section_name, callback_data=f"faq_section_{section_name}")])

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="faq_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_faq_section_markup() -> InlineKeyboardMarkup:
    """Markup for returning to FAQ menu from a section."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ К разделам", callback_data="faq_menu")]
    ])
