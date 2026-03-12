from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.backend import (
    BACKEND_CLIENT,
    get_or_fetch_token,
)
from bot.config import (
    build_step_actions_markup,
    build_main_menu_markup,
    build_template_filling_markup,
)
from bot.utils import send_long_message, edit_long_message
from .shared import StepState, logger


async def handle_template_selection(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle template selection callback"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        if data == "template_author":
            templates_data = await BACKEND_CLIENT.get_templates(token)
            templates = templates_data.get("templates", [])

            logger.info(f"Templates received: {len(templates)} templates")
            for t in templates:
                logger.info(f"Template: id={t.get('id')}, name={t.get('name')}, type={t.get('template_type')}")

            author_template = None
            for template in templates:
                template_type = template.get("template_type")
                if template_type == "AUTHOR" or (hasattr(template_type, 'value') and template_type.value == "AUTHOR"):
                    author_template = template
                    break

            if author_template:
                await BACKEND_CLIENT.set_active_template(token, author_template.get("id"))
                await callback.answer("✅ Авторский шаблон выбран")

                step_info = await BACKEND_CLIENT.get_current_step_info(token)

                if step_info:
                    step_number = step_info.get("step_number")
                    step_title = step_info.get("step_title") or step_info.get("step_description") or (f"Шаг {step_number}" if step_number else "Шаг")
                    total_steps = step_info.get("total_steps", 12)

                    if step_number is not None and total_steps is not None:
                        progress_bar = "█" * step_number + "░" * (total_steps - step_number)
                        progress_text = f"Шаг {step_number}/{total_steps}\n{progress_bar}"
                    else:
                        progress_text = "Начинаем работу по шагам..."

                    step_next = await BACKEND_CLIENT.get_next_step(token)

                    if step_next:
                        is_completed = step_next.get("is_completed", False)
                        question_text = step_next.get("message", "")

                        if is_completed or not question_text or question_text == "Program completed.":
                            await edit_long_message(
                                callback,
                                f"✅ Шаблон выбран!\n\n{progress_text}\n\n"
                                "⚠️ В базе данных пока нет шагов или вопросов.\n\n"
                                "Обратитесь к администратору для настройки шагов программы.",
                                reply_markup=None
                            )
                        else:
                            await edit_long_message(
                                callback,
                                f"✅ Шаблон выбран!\n\n{progress_text}\n\n📘 {step_title}\n\n{question_text}",
                                reply_markup=build_step_actions_markup()
                            )
                            await state.set_state(StepState.answering)
                    else:
                        await edit_long_message(
                            callback,
                            f"✅ Шаблон выбран!\n\n{progress_text}\n\n📘 {step_title}\n\nНачинаем работу по шагу...",
                            reply_markup=build_step_actions_markup()
                        )
                        await state.set_state(StepState.answering)
                else:
                    await edit_long_message(
                        callback,
                        "✅ Выбран авторский шаблон!\n\nТеперь можешь начать работу по шагу. Нажми /steps."
                    )
            else:
                await callback.answer("Авторский шаблон не найден")

        elif data == "template_custom":
            await edit_long_message(
                callback,
                "✍️ Для создания своего шаблона нужно:\n\n"
                "1. Определить структуру (поля) шаблона\n"
                "2. Создать шаблон через API или настройки\n\n"
                "Пока используй авторский шаблон, а свой создашь позже в настройках."
            )
            await callback.answer()

    except Exception as exc:
        logger.exception("Error handling template selection for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_template_filling_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle template filling FSM callbacks (pause, cancel, etc.)"""
    data = callback.data
    telegram_id = callback.from_user.id
    username = callback.from_user.username
    first_name = callback.from_user.first_name

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await callback.answer("Ошибка авторизации. Нажми /start.")
            return

        state_data = await state.get_data()
        step_id = state_data.get("template_step_id")
        question_id = state_data.get("template_question_id")

        if data == "tpl_pause":
            if step_id and question_id:
                result = await BACKEND_CLIENT.pause_template_progress(token, step_id, question_id)

                if result and result.get("success"):
                    resume_info = result.get("resume_info", "")
                    progress_summary = result.get("progress_summary", "")
                    await edit_long_message(
                        callback,
                        f"⏸ Прогресс сохранён!\n\n"
                        f"{resume_info}\n\n"
                        f"📊 {progress_summary}\n\n"
                        f"💡 Чтобы продолжить:\n"
                        f"1. Вернись к этому вопросу (🪜 Работа по шагу)\n"
                        f"2. Нажми «🧩 Заполнить по шаблону»\n"
                        f"3. Система автоматически продолжит с того места, где остановился",
                        reply_markup=build_step_actions_markup()
                    )
                    await state.set_state(StepState.answering)
                    await callback.answer("Прогресс сохранён")
                else:
                    await callback.answer("Ошибка сохранения прогресса")
            else:
                await callback.answer("Данные шаблона потеряны")
                await state.set_state(StepState.answering)

        elif data == "tpl_cancel":
            if step_id and question_id:
                await BACKEND_CLIENT.cancel_template_progress(token, step_id, question_id)

            await edit_long_message(
                callback,
                "❌ Заполнение шаблона отменено.\n\n"
                "Ты можешь ответить на вопрос своими словами или начать заполнение заново.",
                reply_markup=build_step_actions_markup()
            )
            await state.set_state(StepState.answering)
            await callback.answer("Заполнение отменено")

        elif data == "tpl_next_situation":
            await callback.answer("Продолжаем...")

        elif data == "tpl_write_conclusion":
            await callback.answer("Напиши финальный вывод")

        else:
            await callback.answer("Неизвестная команда")

    except Exception as exc:
        logger.exception("Error handling template filling callback for %s: %s", telegram_id, exc)
        await callback.answer("Ошибка. Попробуй позже.")

async def handle_template_field_input(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    field_value = message.text

    try:
        token = await get_or_fetch_token(telegram_id, username, first_name)
        if not token:
            await message.answer("Ошибка авторизации. Нажми /start.")
            await state.clear()
            return

        state_data = await state.get_data()
        step_id = state_data.get("template_step_id")
        question_id = state_data.get("template_question_id")

        if not step_id or not question_id:
            await message.answer("Ошибка: данные шаблона потеряны. Начни заново.")
            await state.clear()
            return

        result = await BACKEND_CLIENT.submit_template_field(
            token, step_id, question_id, field_value
        )

        if not result:
            await message.answer("Ошибка сервера. Попробуй ещё раз.")
            return

        if not result.get("success"):
            error_msg = result.get("error", "Ошибка валидации")
            validation_error = result.get("validation_error", False)

            if validation_error and result.get("current_feelings"):
                current_feelings = result.get("current_feelings", [])
                current_count = result.get("current_count", 0)
                if current_feelings:
                    feelings_text = ", ".join(current_feelings)
                    error_msg = f"{error_msg}\n\n📝 Уже указано ({current_count}): {feelings_text}"

            await message.answer(
                f"⚠️ {error_msg}\n\n💡 Совет: можешь написать все чувства через запятую в одном сообщении, или добавлять по одному.",
                reply_markup=build_template_filling_markup()
            )
            return

        if result.get("is_complete"):
            formatted_answer = result.get("formatted_answer", "")

            success = await BACKEND_CLIENT.submit_step_answer(token, formatted_answer, is_template_format=True)

            if success:
                step_next = await BACKEND_CLIENT.get_next_step(token)

                if step_next:
                    response_text = step_next.get("message", "")
                    is_completed = step_next.get("is_completed", False)

                    await send_long_message(
                        message,
                        response_text,
                        reply_markup=build_step_actions_markup()
                    )

                    if is_completed:
                        await message.answer(
                            "Этап завершен! 🎉",
                            reply_markup=build_main_menu_markup()
                        )
                        await state.clear()
                    else:
                        await state.set_state(StepState.answering)
                else:
                    await state.set_state(StepState.answering)
            else:
                await message.answer("Ошибка при сохранении. Попробуй ещё раз.")
            return

        field_info = result.get("field_info", {})
        current_situation = result.get("current_situation", 1)
        is_situation_complete = result.get("is_situation_complete", False)
        ready_for_conclusion = result.get("ready_for_conclusion", False)
        progress_summary = result.get("progress_summary", "")

        if ready_for_conclusion:
            await message.answer(
                f"✅ Ситуация {current_situation - 1} завершена!\n\n"
                f"🎯 Все 3 ситуации заполнены!\n\n"
                f"Теперь напиши **Финальный вывод**:\n\n"
                f"• Как ты теперь видишь ситуацию?\n"
                f"• Что на самом деле происходило?\n"
                f"• Как повторялись чувства/мысли/действия?\n"
                f"• Где была болезнь, где был ты?",
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )
        elif is_situation_complete:
            await message.answer(
                f"✅ Ситуация {current_situation - 1} завершена!\n\n"
                f"📝 Переходим к Ситуации {current_situation}\n\n"
                f"**{field_info.get('name', 'Поле')}**\n"
                f"{field_info.get('description', '')}\n\n"
                f"Введи значение:",
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )
        else:
            min_items = field_info.get("min_items")
            field_text = f"✅ Сохранено!\n\n"
            field_text += f"📝 Ситуация {current_situation}/3\n\n"
            field_text += f"**{field_info.get('name', 'Поле')}**\n"
            field_text += f"{field_info.get('description', '')}\n"
            if min_items:
                field_text += f"\n⚠️ Нужно указать минимум {min_items} (через запятую)\n"
            field_text += "\nВведи значение:"

            await message.answer(
                field_text,
                reply_markup=build_template_filling_markup(),
                parse_mode="Markdown"
            )

    except Exception as exc:
        logger.exception("Error handling template field input for %s: %s", telegram_id, exc)
        await message.answer("Произошла ошибка. Попробуй ещё раз.")
        await state.clear()
