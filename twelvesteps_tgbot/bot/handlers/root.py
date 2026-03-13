import json
import datetime
from functools import partial

from aiogram import Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from bot.backend import (
    BACKEND_CLIENT,
    TOKEN_STORE,
    USER_CACHE,
    Log,
    call_legacy_chat,
    get_display_name,
    get_current_step_question,
    get_or_fetch_token,
)
from bot.config import (
    build_main_menu_markup,
    build_error_markup,

    build_root_menu_markup,
    build_tariffs_menu_markup,
    build_faq_menu_markup,
    build_main_settings_markup,
    build_profile_settings_markup,
)
from bot.utils import send_long_message
from bot.onboarding import OnboardingStates, send_welcome, register_onboarding_handlers

from .shared import (
    StepState,
    ProfileStates,
    SosStates,
    Step10States,
    ThanksStates,
    AboutMeStates,
    MAIN_MENU_TEXT,
    USER_LOGS,
    logger,
)
from .steps import handle_steps, handle_about_step, handle_steps_settings, handle_step_answer, handle_step_answer_mode, handle_template_selection, handle_template_filling_callback, handle_steps_navigation_callback, handle_step_selection_callback, handle_question_view_callback, handle_step_action_callback, handle_progress_callback, handle_template_field_input, handle_steps_settings_callback, handle_questions_group_callback, handle_progress_questions_group_callback, handle_question_select_callback, handle_step_questions_list_callback
from .step10 import handle_day, handle_step10_answer, handle_step10_callback
from .feelings import handle_feelings, handle_feelings_callback, handle_feeling_selection_callback
from .thanks import handle_thanks, handle_thanks_menu, handle_thanks_callback, handle_thanks_entry_input
from .faq import handle_faq, handle_faq_callback
from .settings import handle_main_settings, handle_main_settings_callback, handle_language_callback, handle_step_settings_callback, handle_profile_settings_callback
from .about_me import handle_about_callback, handle_about_entry_input
from .profile import handle_profile, handle_profile_callback, handle_profile_answer, handle_profile_free_text, handle_profile_custom_section, handle_profile_add_entry, handle_profile_edit_entry
from .sos import handle_sos, handle_sos_callback, handle_sos_chat_message, handle_sos_custom_input

async def show_main_menu(message_or_callback_message) -> None:
    await message_or_callback_message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())

async def handle_root_menu(message: Message, state: FSMContext) -> None:
    await message.answer("📋 Меню\n\nВыбери раздел:", reply_markup=build_root_menu_markup())

async def handle_tariffs(message: Message, state: FSMContext) -> None:
    text = (
        "💎 *Тарифы*\n"
        "━━━━━━━━━━━━━━━\n\n"
        "Текущий план: 🆓 *FREE*\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🆓 *FREE — 0 ₽ навсегда*\n"
        "Все 12 шагов, самоанализ, колесо чувств,\n"
        "благодарности, SOS, AI-чат до 5 сообщ/день\n\n"
        "⭐ *Premium — 290 ₽/мес*\n"
        "Всё из Free + безлимит AI-чат, примеры ответов,\n"
        "AI-подбор ситуаций, кастомные шаблоны,\n"
        "расширенный профиль, напоминания\n\n"
        "👑 *PRO — 590 ₽/мес*\n"
        "Всё из Premium + аналитика прогресса,\n"
        "ядро личности, приоритетная поддержка\n\n"
        "━━━━━━━━━━━━━━━\n\n"
        "🎁 *7 дней PRO бесплатно* для новых пользователей"
    )
    await message.answer(text, reply_markup=build_tariffs_menu_markup(), parse_mode="Markdown")

async def handle_root_callback(callback: CallbackQuery, state: FSMContext) -> None:
    data = callback.data
    if data == "root_menu":
        await callback.message.edit_text("📋 Меню\n\nВыбери раздел:", reply_markup=build_root_menu_markup())
        await callback.answer()
        return
    if data == "root_close":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await show_main_menu(callback.message)
        await callback.answer()
        return
    if data == "root_help":
        await callback.message.edit_text("📎 Инструкция\n\nВыбери раздел:", reply_markup=build_faq_menu_markup())
        await callback.answer()
        return
    if data == "root_settings":
        await callback.message.edit_text("⚙️ Настройки\n\nВыбери раздел настроек:", reply_markup=build_main_settings_markup())
        await callback.answer()
        return
    if data == "root_profile":
        await callback.message.edit_text("🪪 Профиль\n\nВыбери раздел:", reply_markup=build_profile_settings_markup())
        await callback.answer()
        return
    if data == "root_steps":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        await handle_steps(callback.message, state)
        return
    if data == "root_day":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        await handle_day(callback.message, state)
        return
    if data == "root_feelings":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        await handle_feelings(callback.message, state)
        return
    if data == "root_thanks":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.answer()
        await handle_thanks_menu(callback.message, state)
        return
    await callback.answer()

async def handle_tariff_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer("🔧 Оплата подключается — скоро будет доступна!", show_alert=True)

async def handle_exit(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()

    await state.clear()

    if current_state == StepState.answering:
        text = "Выход из режима шагов. Твой прогресс сохранен."
    elif current_state:
        text = "Процесс прерван."
    else:
        text = "Режим сброшен."

    await message.answer(text, reply_markup=build_main_menu_markup())

async def handle_reset(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    key = str(telegram_id)
    username = message.from_user.username
    first_name = message.from_user.first_name

    await state.clear()

    from bot.backend import TOKEN_STORE, USER_CACHE
    if key in TOKEN_STORE:
        del TOKEN_STORE[key]
    if key in USER_CACHE:
        del USER_CACHE[key]

    try:
        user, is_new, access_token = await BACKEND_CLIENT.auth_telegram(
            telegram_id=key,
            username=username,
            first_name=first_name,
        )

        TOKEN_STORE[key] = access_token
        USER_CACHE[key] = user

        if is_new:
            await state.set_state(OnboardingStates.welcome)
            await send_welcome(message)
        else:
            try:
                status = await BACKEND_CLIENT.get_status(access_token)
                await send_welcome_back(message, user, status)
            except Exception:
                await message.answer(
                    "🔄 Состояние сброшено. С возвращением!",
                    reply_markup=build_main_menu_markup()
                )
    except Exception as exc:
        logger.exception("Failed to reset for user %s: %s", key, exc)
        await message.answer(
            "❌ Не удалось перезапустить. Попробуй нажать /start",
            reply_markup=build_error_markup()
        )

async def qa_open(message: Message) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        step_data = await get_current_step_question(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )
    except Exception as exc:
        await message.answer(f"❌ API Error: {exc}")
        return

    if not step_data:
        await message.answer("📭 Backend returned no data (or Auth failed).")
        return

    text = step_data.get("message", "[No Text]")
    is_done = step_data.get("is_completed", False)

    info = (
        f"Хвосты:\nШаг: {text}"
    )
    await message.answer(info)

async def qa_ctx(message: Message) -> None:
    uid = message.from_user.id
    logs = USER_LOGS.get(uid, [])
    await message.answer(logs[-1].prompt_changes if logs else "Empty")

async def qa_trace(message: Message) -> None:
    uid = message.from_user.id
    logs = USER_LOGS.get(uid, [])
    await message.answer(str(logs[-1].blocks_used) if logs else "Empty")

async def qa_last(message: Message) -> None:
    uid = message.from_user.id
    logs = USER_LOGS.get(uid, [])
    await message.answer(str(logs[-1].classification_result) if logs else "Empty")

def get_logs_for_period(uid: int, hours: int):
    logs = USER_LOGS.get(uid, [])
    now_ts = int(datetime.datetime.utcnow().timestamp())
    return [l for l in logs if getattr(l, "timestamp", 0) >= (now_ts - hours * 3600)]

async def qa_export(message: Message):
    uid = message.from_user.id
    args = message.text.split()
    if len(args) < 2: return await message.answer("Usage: /qa_export 5h")
    logs = get_logs_for_period(uid, int(args[1][:-1]))
    if not logs: return await message.answer("No logs.")
    data = [{"ts": l.timestamp, "blocks": l.blocks_used} for l in logs]
    await message.answer(f"```json\n{json.dumps(data, indent=2)[:4000]}\n```")

async def qa_report(message: Message):
    uid = message.from_user.id
    args = message.text.split()
    if len(args) < 2: return await message.answer("Usage: /qa_report 5h")
    logs = get_logs_for_period(uid, int(args[1][:-1]))
    if not logs: return await message.answer("No logs.")
    await message.answer(f"Found {len(logs)} interactions.")

async def handle_message(message: Message, debug: bool) -> None:
    telegram_id = message.from_user.id

    try:
        backend_reply = await call_legacy_chat(
            telegram_id=telegram_id,
            text=message.text,
            debug=debug
        )

        reply_text = "..."
        if isinstance(backend_reply, str):
             try:
                data = json.loads(backend_reply)
                reply_text = data.get("reply", "Error parsing reply")
             except (json.JSONDecodeError, TypeError):
                reply_text = backend_reply
        else:
             reply_text = backend_reply.reply
             if backend_reply.log:
                uid = message.from_user.id
                log = backend_reply.log
                log.timestamp = int(datetime.datetime.utcnow().timestamp())
                USER_LOGS.setdefault(uid, []).append(log)

        await send_long_message(message, reply_text, reply_markup=build_main_menu_markup())

    except Exception as exc:
        error_msg = str(exc)
        if "bot was blocked by the user" in error_msg or "Forbidden: bot was blocked" in error_msg:
            logger.info(f"User {telegram_id} blocked the bot - skipping message")
            return

        logger.exception("Failed to get response from backend chat: %s", exc)
        error_text = (
            "❌ Не удалось получить ответ от сервера.\n\n"
            "Произошла ошибка. Хочешь начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())

async def handle_start(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    key = str(telegram_id)
    username = message.from_user.username
    first_name = message.from_user.first_name

    try:
        user, is_new, access_token = await BACKEND_CLIENT.auth_telegram(
            telegram_id=key,
            username=username,
            first_name=first_name,
        )
    except Exception as exc:
        logger.exception("Failed to auth telegram user %s: %s", key, exc)
        error_text = (
            "❌ Ошибка подключения к серверу.\n\n"
            "Хочешь попробовать начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())
        return

    TOKEN_STORE[key] = access_token
    USER_CACHE[key] = user

    if is_new:
        await state.clear()
        await state.set_state(OnboardingStates.welcome)
        await send_welcome(message)
        return

    try:
        status = await BACKEND_CLIENT.get_status(access_token)
    except Exception:
        await message.answer("С возвращением!", reply_markup=build_main_menu_markup())
        return

    await send_welcome_back(message, user, status)

async def send_welcome_back(message: Message, user: dict, status: dict) -> None:
    display_name = get_display_name(user)
    open_question = status.get("open_step_question")

    text = f"С возвращением, {display_name}!"
    if open_question:
        text += "\n\nУ тебя есть незавершённый шаг. Нажми /steps, чтобы продолжить."
    else:
        text += "\n\nЯ готов общаться. Напиши мне что-нибудь или нажми /steps."

    await message.answer(text, reply_markup=build_main_menu_markup())


def register_handlers(dp: Dispatcher) -> None:
    dp.message(CommandStart())(handle_start)
    dp.message(Command(commands=["exit"]))(handle_exit)
    dp.message(Command(commands=["reset", "restart"]))(handle_reset)
    dp.message(Command(commands=["steps"]))(handle_steps)
    dp.message(Command(commands=["about_step"]))(handle_about_step)
    dp.message(Command(commands=["sos"]))(handle_sos)
    dp.message(Command(commands=["profile"]))(handle_profile)
    dp.message(Command(commands=["steps_settings", "settings"]))(handle_steps_settings)
    dp.message(Command(commands=["thanks"]))(handle_thanks)
    dp.message(Command(commands=["day", "inventory"]))(handle_day)

    dp.message(F.text == "🪜 Работа по шагу")(handle_steps)
    dp.message(F.text == "📖 Самоанализ")(handle_day)
    dp.message(F.text == "📘 Чувства")(handle_feelings)
    dp.message(F.text == "🙏 Благодарности")(handle_thanks_menu)
    dp.message(F.text == "⚙️ Настройки")(handle_main_settings)
    dp.message(F.text == "📎 Инструкция")(handle_faq)
    dp.message(F.text == "📋 Меню")(handle_root_menu)
    dp.message(F.text == "💎 Тарифы")(handle_tariffs)
    dp.message(F.text == "❓ Помощь")(handle_faq)

    register_onboarding_handlers(dp)

    dp.message(StateFilter(StepState.answering))(handle_step_answer)
    dp.message(StateFilter(StepState.answer_mode))(handle_step_answer_mode)
    dp.message(StateFilter(StepState.filling_template))(handle_template_field_input)
    dp.message(Command(commands=["qa_open"]))(qa_open)

    dp.callback_query(F.data.startswith("main_settings_"))(handle_main_settings_callback)
    dp.callback_query(F.data.startswith("lang_"))(handle_language_callback)
    dp.callback_query(F.data.startswith("step_settings_"))(handle_step_settings_callback)
    dp.callback_query(F.data.startswith("profile_settings_"))(handle_profile_settings_callback)
    dp.callback_query(F.data.startswith("about_"))(handle_about_callback)

    dp.callback_query(F.data.startswith("profile_"))(handle_profile_callback)
    dp.message(StateFilter(ProfileStates.answering_question))(handle_profile_answer)
    dp.message(StateFilter(ProfileStates.free_text_input))(handle_profile_free_text)
    dp.message(StateFilter(ProfileStates.creating_custom_section))(handle_profile_custom_section)
    dp.message(StateFilter(ProfileStates.adding_entry))(handle_profile_add_entry)
    dp.message(StateFilter(ProfileStates.editing_entry))(handle_profile_edit_entry)

    dp.callback_query(F.data.startswith("template_"))(handle_template_selection)
    dp.callback_query(F.data.startswith("tpl_"))(handle_template_filling_callback)

    dp.callback_query(F.data.startswith("sos_"))(handle_sos_callback)
    dp.message(StateFilter(SosStates.chatting))(handle_sos_chat_message)
    dp.message(StateFilter(SosStates.custom_input))(handle_sos_custom_input)

    dp.message(StateFilter(Step10States.answering_question))(handle_step10_answer)
    dp.callback_query(F.data.startswith("step10_"))(handle_step10_callback)

    dp.callback_query(F.data.startswith("steps_"))(handle_steps_navigation_callback)
    dp.callback_query(F.data.startswith("step_select_"))(handle_step_selection_callback)
    dp.callback_query(F.data.startswith("step_questions_list_"))(handle_step_questions_list_callback)
    dp.callback_query(F.data.startswith("question_view_"))(handle_question_view_callback)
    dp.callback_query(F.data.startswith("question_select_"))(handle_question_select_callback)
    dp.callback_query(F.data.startswith("questions_group_"))(handle_questions_group_callback)
    dp.callback_query(F.data.startswith("step_") & ~F.data.startswith("step_select_") & ~F.data.startswith("step_questions_list_"))(handle_step_action_callback)

    dp.callback_query(F.data.startswith("settings_"))(handle_steps_settings_callback)
    dp.message(StateFilter(AboutMeStates.adding_entry))(handle_about_entry_input)

    dp.callback_query(F.data.startswith("progress_qgroup_"))(handle_progress_questions_group_callback)
    dp.callback_query(F.data.startswith("progress_"))(handle_progress_callback)

    dp.callback_query(F.data.startswith("thanks_"))(handle_thanks_callback)
    dp.message(StateFilter(ThanksStates.adding_entry))(handle_thanks_entry_input)

    dp.callback_query(F.data.startswith("feelings_"))(handle_feelings_callback)
    dp.callback_query(F.data.startswith("feeling_"))(handle_feeling_selection_callback)

    dp.callback_query(F.data.startswith("faq_"))(handle_faq_callback)
    dp.callback_query(F.data.startswith("tariff_"))(handle_tariff_callback)
    dp.callback_query(F.data.startswith("root_"))(handle_root_callback)

    dp.message(Command(commands=["qa_last"]))(qa_last)
    dp.message(Command(commands=["qa_ctx"]))(qa_ctx)
    dp.message(Command(commands=["qa_trace"]))(qa_trace)
    dp.message(Command(commands=["qa_report"]))(qa_report)
    dp.message(Command(commands=["qa_export"]))(qa_export)

    dp.message()(partial(handle_message, debug=False))
