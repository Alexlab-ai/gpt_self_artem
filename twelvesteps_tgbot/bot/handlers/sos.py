import asyncio
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from bot.backend import BACKEND_CLIENT, get_or_fetch_token, get_current_step_question
from bot.config import (
    build_sos_help_type_markup,
    build_sos_exit_markup,
    build_step_actions_markup,
    build_main_menu_markup,
    format_step_progress_indicator,
)
from bot.utils import send_long_message, edit_long_message
from .shared import StepState, SosStates, MAIN_MENU_TEXT, logger

async def handle_sos(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id

    current_state = await state.get_state()
    if current_state == StepState.answering:
        await state.update_data(previous_state=StepState.answering)

    await state.set_state(SosStates.help_type_selection)
    await message.answer(
        "🆘 Хорошо, я с тобой. Давай разберёмся, с чем нужна помощь.\n\n"
        "Выбери или опиши словами:",
        reply_markup=build_sos_help_type_markup()
    )

async def safe_answer_callback(callback: CallbackQuery, text: str | None = None, show_alert: bool = False) -> bool:
    try:
        await callback.answer(text=text, show_alert=show_alert)
        return True
    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "query is too old" in error_message or "query id is invalid" in error_message:
            logger.warning("Callback query expired for user %s: %s", callback.from_user.id, callback.data)
            return False
        raise

async def handle_sos_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle SOS callback queries (help type selection, exit, etc.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await safe_answer_callback(callback, "Ошибка авторизации. Нажми /start.")
            return

        if data == "sos_back":
            state_data = await state.get_data()
            previous_state = state_data.get("previous_state")
            current_state = await state.get_state()

            if previous_state == StepState.answering or current_state == StepState.answering or str(previous_state) == str(StepState.answering):
                step_info = await BACKEND_CLIENT.get_current_step_info(token)
                if step_info:
                    step_data = await get_current_step_question(telegram_id, username, first_name)
                    if step_data:
                        response_text = step_data.get("message", "")
                        if response_text:
                            progress_indicator = format_step_progress_indicator(
                                step_number=step_info.get("step_number"),
                                total_steps=step_info.get("total_steps", 12),
                                step_title=step_info.get("step_title"),
                                answered_questions=step_info.get("answered_questions", 0),
                                total_questions=step_info.get("total_questions", 0)
                            )
                            full_text = f"{progress_indicator}\n\n{response_text}"
                            await edit_long_message(
                                callback,
                                full_text,
                                reply_markup=build_step_actions_markup()
                            )
                            await state.set_state(StepState.answering)
                            await safe_answer_callback(callback)
                            return

            await state.clear()
            await edit_long_message(
                callback,
                MAIN_MENU_TEXT,
                reply_markup=None
            )
            await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
            await safe_answer_callback(callback)
            return


        if data == "sos_help":
            current_state = await state.get_state()
            if current_state == StepState.answering:
                await state.update_data(previous_state=StepState.answering)

            await state.set_state(SosStates.help_type_selection)
            await edit_long_message(
                callback,
                "🆘 Хорошо, я с тобой. Давай разберёмся, с чем нужна помощь.\n\n"
                "Выбери или опиши словами:",
                reply_markup=build_sos_help_type_markup()
            )
            await safe_answer_callback(callback)
            return

        if data == "sos_help_custom":
            await state.set_state(SosStates.custom_input)
            await edit_long_message(
                callback,
                "✍️ Опиши, с чем нужна помощь, своими словами:",
                reply_markup=build_sos_exit_markup()
            )
            await safe_answer_callback(callback)
            return

        if data.startswith("sos_help_"):
            help_type = data.replace("sos_help_", "")
            help_type_map = {
                "question": "Не понял вопрос",
                "examples": "Хочу примеры",
                "direction": "Помоги понять куда смотреть",
                "memory": "Помоги понять куда смотреть",
                "support": "Просто тяжело"
            }
            help_type_name = help_type_map.get(help_type, help_type)

            if help_type == "examples":
                await safe_answer_callback(callback, "Загружаю примеры...")

                try:
                    step_info = await BACKEND_CLIENT.get_current_step_info(token)
                    step_number = step_info.get("step_number") if step_info else None
                    step_id = step_info.get("step_id") if step_info else None

                    question_id_data = await BACKEND_CLIENT.get_current_question_id(token)
                    question_id = question_id_data.get("question_id") if question_id_data else None

                    step_question = ""
                    if question_id and step_id:
                        questions_data = await BACKEND_CLIENT.get_step_questions(token, step_id)
                        questions = questions_data.get("questions", []) if questions_data else []
                        for q in questions:
                            if q.get("id") == question_id:
                                step_question = q.get("text", "")
                                break

                    if step_number and step_question:
                        await state.set_state(SosStates.chatting)
                        await state.update_data(help_type=help_type, conversation_history=[])

                        loading_text = (
                            "🆘 Помощь: Хочу примеры\n\n"
                            "⏳ Загружаю примеры...\n\n"
                            "Это может занять некоторое время (до 3 минут).\n"
                            "Пожалуйста, подожди, я формирую примеры специально для тебя."
                        )
                        await edit_long_message(
                            callback,
                            loading_text,
                            reply_markup=None
                        )

                        try:
                            sos_response = await asyncio.wait_for(
                                BACKEND_CLIENT.sos_chat(
                                    access_token=token,
                                    help_type=help_type,
                                    custom_text=step_question if step_question else None
                                ),
                                timeout=180.0
                            )

                            reply_text = sos_response.get("reply", "") if sos_response else ""

                            if not reply_text or reply_text.strip() == "":
                                reply_text = "Извини, не удалось получить примеры. Попробуй ещё раз или опиши проблему своими словами."
                        except asyncio.TimeoutError:
                            logger.error(f"SOS chat timeout after 180s for user {telegram_id}, help_type={help_type}")
                            reply_text = (
                                "🆘 Помощь: Хочу примеры\n\n"
                                "❌ Запрос занимает слишком много времени. Попробуй позже или опиши проблему своими словами."
                            )
                        except Exception as e:
                            logger.exception(f"Error getting examples for user {telegram_id}: {e}")
                            reply_text = (
                                "📋 Примеры ответов\n\n"
                                "❌ Не удалось получить примеры. Попробуй позже."
                            )
                    else:
                        reply_text = (
                            "📋 Примеры ответов\n\n"
                            "❌ Не удалось определить текущий шаг или вопрос. Вернись к работе по шагу."
                        )
                        await state.clear()
                except Exception as e:
                    logger.exception(f"Error getting step/question info for examples: {e}")
                    reply_text = (
                        "📋 Примеры ответов\n\n"
                        "❌ Не удалось получить информацию о текущем шаге. Вернись к работе по шагу."
                    )
                    await state.clear()

                await edit_long_message(
                    callback,
                    f"🆘 Помощь: {help_type_name}\n\n{reply_text}",
                    reply_markup=build_sos_exit_markup()
                )
                await safe_answer_callback(callback)
                return

            await state.set_state(SosStates.chatting)
            await state.update_data(help_type=help_type, conversation_history=[])

            await safe_answer_callback(callback, "Загружаю помощь...")

            try:
                sos_response = await asyncio.wait_for(
                    BACKEND_CLIENT.sos_chat(
                        access_token=token,
                        help_type=help_type
                    ),
                    timeout=15.0
                )

                reply_text = sos_response.get("reply", "") if sos_response else ""

                if not reply_text or reply_text.strip() == "":
                    reply_text = "Извини, не удалось получить ответ. Попробуй ещё раз или опиши проблему своими словами."
            except asyncio.TimeoutError:
                logger.warning(f"SOS chat timeout for user {telegram_id}, help_type={help_type}")
                reply_text = (
                    "⏱️ Запрос занимает больше времени, чем обычно.\n\n"
                    "Попробуй:\n"
                    "• Подождать немного и попробовать снова\n"
                    "• Опиши проблему своими словами в разделе «Своё описание»"
                )
            except Exception as e:
                logger.exception(f"Error getting SOS response for user {telegram_id}: {e}")
                reply_text = (
                    "❌ Произошла ошибка при получении помощи.\n\n"
                    "Попробуй:\n"
                    "• Подождать немного и попробовать снова\n"
                    "• Опиши проблему своими словами в разделе «Своё описание»"
                )

            if help_type == "question":
                original_reply = reply_text
                if reply_text and reply_text.strip():
                    lines = reply_text.split("\n")
                    cleaned_lines = []
                    skip_until_empty = False
                    for i, line in enumerate(lines):
                        if any(marker in line for marker in ["**Простыми словами:**", "**Про что это:**", "**Можно понять как:**", "Простыми словами:", "Про что это:", "Можно понять как:"]):
                            skip_until_empty = True
                            continue
                        if skip_until_empty and line.strip() == "":
                            skip_until_empty = False
                            continue
                        if not skip_until_empty:
                            cleaned_lines.append(line)
                    reply_text = "\n".join(cleaned_lines).strip()

                if not reply_text or reply_text.strip() == "":
                    if not original_reply or original_reply.strip() == "" or "Не удалось" in original_reply or "ошибка" in original_reply.lower():
                        reply_text = (
                            "Попробую объяснить вопрос проще.\n\n"
                            "💡 Вопрос может показаться сложным, но попробуй ответить своими словами, как понимаешь. "
                            "Можно начать с того, что первое приходит в голову. "
                            "Если что-то непонятно, напиши, что именно, и я помогу разобраться."
                        )
                    else:
                        reply_text = original_reply.strip()

            await edit_long_message(
                callback,
                f"🆘 Помощь: {help_type_name}\n\n{reply_text}",
                reply_markup=build_sos_exit_markup()
            )
            await safe_answer_callback(callback)
            return

        if data == "sos_save_yes":
            await state.clear()
            await edit_long_message(
                callback,
                "✅ Черновик сохранён.\n\nВернулся в главное меню.",
                reply_markup=None
            )
            await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
            await safe_answer_callback(callback, "Черновик сохранён")
            return

        if data == "sos_save_no":
            await state.clear()
            await edit_long_message(
                callback,
                "✅ Помощь завершена.\n\nВернулся в главное меню.",
                reply_markup=None
            )
            await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
            await safe_answer_callback(callback)
            return

        await safe_answer_callback(callback, "Неизвестная команда")

    except TelegramBadRequest as e:
        error_message = str(e).lower()
        if "query is too old" in error_message or "query id is invalid" in error_message:
            logger.warning("Callback query expired for user %s: %s", telegram_id, data)
        else:
            logger.exception("TelegramBadRequest handling SOS callback for %s: %s", telegram_id, e)
            await safe_answer_callback(callback, "Ошибка. Попробуй позже.")
    except Exception as exc:
        logger.exception("Error handling SOS callback for %s: %s", telegram_id, exc)
        await safe_answer_callback(callback, "Ошибка. Попробуй позже.")

async def handle_sos_chat_message(message: Message, state: FSMContext) -> None:
    """Handle messages during SOS chat"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            return

        state_data = await state.get_data()
        conversation_history = state_data.get("conversation_history", [])
        help_type = state_data.get("help_type")

        conversation_history.append({"role": "user", "content": text})

        try:
            sos_response = await asyncio.wait_for(
                BACKEND_CLIENT.sos_chat(
                    access_token=token,
                    help_type=help_type,
                    message=text,
                    conversation_history=conversation_history
                ),
                timeout=15.0
            )

            reply_text = sos_response.get("reply", "Готов помочь!") if sos_response else "Готов помочь!"
        except asyncio.TimeoutError:
            logger.warning(f"SOS chat timeout for user {telegram_id}, help_type={help_type}")
            reply_text = (
                "⏱️ Запрос занимает больше времени, чем обычно.\n\n"
                "Попробуй подождать немного или опиши проблему по-другому."
            )
        except Exception as e:
            logger.exception(f"Error getting SOS response for user {telegram_id}: {e}")
            reply_text = (
                "❌ Произошла ошибка при получении помощи.\n\n"
                "Попробуй подождать немного или опиши проблему по-другому."
            )

        if help_type == "support":
            try:
                await BACKEND_CLIENT.submit_general_free_text(token, text)
            except Exception as e:
                logger.warning(f"Failed to save SOS support message to profile: {e}")

        conversation_history.append({"role": "assistant", "content": reply_text})
        await state.update_data(conversation_history=conversation_history)

        await send_long_message(
            message,
            reply_text,
            reply_markup=build_sos_exit_markup()
        )

    except Exception as exc:
        logger.exception("Error handling SOS chat message for %s: %s", telegram_id, exc)
        await message.answer("Ошибка. Попробуй позже.")

async def handle_sos_custom_input(message: Message, state: FSMContext) -> None:
    """Handle custom help description input"""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    custom_text = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            return

        await state.set_state(SosStates.chatting)
        await state.update_data(help_type="custom", conversation_history=[])

        try:
            sos_response = await asyncio.wait_for(
                BACKEND_CLIENT.sos_chat(
                    access_token=token,
                    help_type="custom",
                    custom_text=custom_text
                ),
                timeout=15.0
            )

            reply_text = sos_response.get("reply", "Готов помочь!") if sos_response else "Готов помочь!"
        except asyncio.TimeoutError:
            logger.warning(f"SOS chat timeout for user {telegram_id}, help_type=custom")
            reply_text = (
                "⏱️ Запрос занимает больше времени, чем обычно.\n\n"
                "Попробуй подождать немного или опиши проблему по-другому."
            )
        except Exception as e:
            logger.exception(f"Error getting SOS response for user {telegram_id}: {e}")
            reply_text = (
                "❌ Произошла ошибка при получении помощи.\n\n"
                "Попробуй подождать немного или опиши проблему по-другому."
            )

        await send_long_message(
            message,
            f"🆘 Помощь: Своё описание\n\n{reply_text}",
            reply_markup=build_sos_exit_markup()
        )

    except Exception as exc:
        logger.exception("Error handling SOS custom input for %s: %s", telegram_id, exc)
        await message.answer("Ошибка. Попробуй позже.")

