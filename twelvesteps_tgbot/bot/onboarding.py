"""Onboarding FSM flow: Welcome -> Name -> Main Menu."""

from __future__ import annotations

import logging

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)

from bot.backend import update_user_profile
from bot.config import build_main_menu_markup

logger = logging.getLogger(__name__)


WELCOME_TEXT = (
    "Привет! 👋 Добро пожаловать в *GPT\\-SELF*\\!\n\n"
    "Вся программа 12 шагов — у тебя в кармане\\.\n\n"
    "Здесь есть всё, что нужно для работы по шагам:\n"
    "— 12 шагов с вопросами и описаниями\n"
    "— Ежедневный самоанализ по 10 шагу\n"
    "— Колесо чувств\n"
    "— Дневник благодарности\n"
    "— SOS\\-поддержка когда тяжело\n\n"
    "А ещё:\n"
    "— Я запоминаю важное и учитываю твои состояния\n"
    "— Помогаю разобраться в вопросах если застрял\n"
    "— Всё приватно — видишь только ты\n\n"
    "Это твоя личная система выздоровления\\.\n"
    "Давай начнём\\!"
)


class OnboardingStates(StatesGroup):
    welcome = State()
    display_name = State()


def _build_start_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Начать")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _build_skip_name_markup() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Пропустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def handle_welcome(message: Message, state: FSMContext) -> None:
    """Handle the welcome screen — wait for 'Начать' button press."""
    text = message.text.strip()
    if text == "🚀 Начать":
        await state.set_state(OnboardingStates.display_name)
        await message.answer(
            "Как к тебе обращаться? Напиши имя или ник.",
            reply_markup=_build_skip_name_markup(),
        )
    else:
        await message.answer(
            "Нажми кнопку «🚀 Начать», чтобы продолжить.",
            reply_markup=_build_start_markup(),
        )


async def handle_display_name(message: Message, state: FSMContext) -> None:
    """Handle name input or skip."""
    text = message.text.strip()

    if text == "Пропустить":
        display_name = message.from_user.first_name or message.from_user.username or "друг"
    elif not text or text.startswith("/"):
        await message.answer(
            "Напиши имя или ник, либо нажми «Пропустить».",
            reply_markup=_build_skip_name_markup(),
        )
        return
    else:
        display_name = text

    await update_user_profile(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        display_name=display_name,
    )

    await state.clear()
    await message.answer(
        f"Отлично, {display_name}! Добро пожаловать!",
        reply_markup=build_main_menu_markup(),
    )


def register_onboarding_handlers(dp: Dispatcher) -> None:
    """Attach onboarding FSM handlers to the dispatcher."""
    dp.message(OnboardingStates.welcome, F.text)(handle_welcome)
    dp.message(OnboardingStates.display_name, F.text)(handle_display_name)
