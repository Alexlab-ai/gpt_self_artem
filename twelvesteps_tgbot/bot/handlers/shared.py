"""Telegram handlers for /start, /exit, /steps and the legacy chat bridge."""

from __future__ import annotations

from functools import partial
from typing import Optional
import json
import logging
import datetime
import asyncio

from aiogram import Dispatcher, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from bot.backend import (
    BACKEND_CLIENT,
    TOKEN_STORE,
    USER_CACHE,
    Log,
    call_legacy_chat,
    get_display_name,
    process_step_message,
    get_current_step_question,
    get_or_fetch_token
)
from bot.config import (
    build_exit_markup,
    build_main_menu_markup,
    build_root_menu_markup,
    build_tariffs_menu_markup,
    build_error_markup,
    format_step_progress_indicator,
    build_profile_sections_markup,
    build_profile_actions_markup,
    build_profile_skip_markup,
    build_template_selection_markup,
    build_template_filling_markup,
    build_sos_help_type_markup,
    build_sos_save_draft_markup,
    build_sos_exit_markup,
    build_steps_navigation_markup,
    build_steps_list_markup,
    build_step_questions_markup,
    build_step_actions_markup,
    build_step_answer_mode_markup,
    build_steps_settings_markup,
    build_template_selection_settings_markup,
    build_reminders_settings_markup,
    build_main_settings_markup,
    build_language_settings_markup,
    build_step_settings_markup,
    build_profile_settings_markup,
    build_about_me_main_markup,
    build_free_story_markup,
    build_free_story_add_entry_markup,
    build_section_history_markup,
    build_entry_detail_markup,
    build_entry_edit_markup,
    build_mini_survey_markup,
    build_settings_steps_list_markup,
    build_settings_questions_list_markup,
    build_settings_select_step_for_question_markup,
    build_progress_step_markup,
    build_progress_main_markup,
    build_progress_view_answers_steps_markup,
    build_progress_view_answers_questions_markup,
    build_thanks_menu_markup,
    build_thanks_history_markup,
    build_thanks_input_markup,
    build_feelings_categories_markup,
    build_feelings_list_markup,
    build_all_feelings_markup,
    build_feelings_category_markup,
    build_fears_markup,
    FEELINGS_CATEGORIES,
    FEARS_LIST,
    build_faq_menu_markup,
    build_faq_section_markup,
    FAQ_SECTIONS
)
from bot.utils import split_long_message, send_long_message, edit_long_message
from bot.onboarding import OnboardingStates, register_onboarding_handlers


logger = logging.getLogger(__name__)

USER_LOGS: dict[int, list[Log]] = {}

MAIN_MENU_TEXT = "⁠"

class StepState(StatesGroup):
    answering = State()
    answer_mode = State()
    filling_template = State()
    template_field = State()

class ProfileStates(StatesGroup):
    section_selection = State()
    answering_question = State()
    free_text_input = State()
    creating_custom_section = State()
    adding_entry = State()
    editing_entry = State()

class SosStates(StatesGroup):
    help_type_selection = State()
    chatting = State()
    custom_input = State()
    saving_draft = State()

class Step10States(StatesGroup):
    answering_question = State()

class ThanksStates(StatesGroup):
    adding_entry = State()

class AboutMeStates(StatesGroup):
    adding_entry = State()


def _clean_section_title(name: str, icon: str = "") -> str:
    """Build display title: 'emoji name'. Never cuts cyrillic letters."""
    import re
    raw_name = (name or "").strip()
    # Strip leading emoji/symbols — allow Cyrillic \u0400-\u04FF, latin \w, digits
    cleaned_name = re.sub(r'^[^\u0400-\u04FFa-zA-Z0-9]+', '', raw_name).strip()
    if not cleaned_name:
        cleaned_name = raw_name  # fallback
    # Normalize icon: strip variation selectors
    cleaned_icon = re.sub(r'[\uFE0F\u20E3]', '', (icon or '').strip())
    if not cleaned_icon:
        return cleaned_name or "Раздел"
    # Avoid double-emoji: if name already starts with that icon, just clean the name
    if raw_name.startswith(cleaned_icon):
        return f"{cleaned_icon} {cleaned_name}".strip()
    return f"{cleaned_icon} {cleaned_name}".strip()

def _entry_preview_text(content: str, limit: int = 42) -> str:
    content = (content or "").replace("\n", " ").strip()
    if len(content) <= limit:
        return content
    return content[: limit - 1].rstrip() + "…"

def _section_nav_callback(section_id: int, source: str) -> str:
    return f"profile_info_settings_section_{section_id}" if source == "settings" else f"profile_info_section_{section_id}"

def _section_back_callback(source: str) -> str:
    return "profile_back_to_settings" if source == "settings" else "profile_my_info"
