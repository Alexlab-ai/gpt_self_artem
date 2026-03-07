from .shared import *

async def handle_thanks(message: Message, state: FSMContext) -> None:
    telegram_id = message.from_user.id

    try:
        backend_reply = await BACKEND_CLIENT.thanks(telegram_id=telegram_id, debug=False)

        reply_text = backend_reply.reply
        if backend_reply.log:
            log = backend_reply.log
            log.timestamp = int(datetime.datetime.utcnow().timestamp())
            USER_LOGS.setdefault(telegram_id, []).append(log)

        await send_long_message(message, reply_text, reply_markup=build_main_menu_markup())

    except Exception as exc:
        logger.exception("Failed to get response from /thanks endpoint: %s", exc)
        error_text = (
            "❌ Не удалось получить ответ от сервера.\n\n"
            "Произошла ошибка. Хочешь начать заново?"
        )
        await message.answer(error_text, reply_markup=build_error_markup())

async def handle_thanks_menu(message: Message, state: FSMContext) -> None:
    """Handle gratitude button - show gratitude menu"""
    thanks_text = (
        "🙏 Благодарности\n\n"
        "Благодарность помогает переключить мышление и снизить тревогу.\n\n"
        "Записывай за что ты благодарен — это может быть что угодно: "
        "тёплый день, вкусный завтрак, разговор с другом.\n\n"
        "Только ты видишь свои записи."
    )
    await message.answer(thanks_text, reply_markup=build_thanks_menu_markup())

async def handle_thanks_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle thanks/gratitude callbacks"""
    data = callback.data
    telegram_id = callback.from_user.id

    if data == "thanks_back":
        await callback.message.delete()
        await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
        await callback.answer()
        return

    if data == "thanks_menu":
        await callback.message.edit_text(
            "🙏 Благодарности\n\n"
            "Благодарность помогает переключить мышление и снизить тревогу.\n\n"
            "Записывай за что ты благодарен — это может быть что угодно.",
            reply_markup=build_thanks_menu_markup()
        )
        await callback.answer()
        return

    if data == "thanks_add":
        await state.set_state(ThanksStates.adding_entry)
        await state.update_data(gratitude_text="")
        await callback.message.edit_text(
            "🙏 Добавить благодарность\n\n"
            "Напиши за что ты сегодня благодарен.\n\n"
            "Можно написать 3-4 вещи через запятую или отдельными строками.\n\n"
            "После ввода текста нажми кнопку '💾 Сохранить'.",
            reply_markup=build_thanks_input_markup()
        )
        await callback.answer()
        return
    
    if data == "thanks_save":
        state_data = await state.get_data()
        gratitude_text = state_data.get("gratitude_text", "").strip()
        
        if not gratitude_text:
            await callback.answer("Сначала напиши текст благодарности", show_alert=True)
            return
        
        try:
            token = await get_or_fetch_token(telegram_id, callback.from_user.username, callback.from_user.first_name)
            if not token:
                await callback.answer("Ошибка авторизации", show_alert=True)
                return
            
            await BACKEND_CLIENT.create_gratitude(token, gratitude_text)
            
            try:
                backend_reply = await BACKEND_CLIENT.thanks(telegram_id=telegram_id, debug=False)
                reply_text = backend_reply.reply if backend_reply else "Благодарность сохранена! 🙏"
            except Exception:
                reply_text = "✅ Благодарность записана! 🙏\n\nПродолжай в том же духе!"
            
            await state.clear()
            await callback.message.edit_text(
                f"✅ Сохранено!\n\n{gratitude_text}\n\n{reply_text}\n\n"
                "Ты можешь посмотреть все свои благодарности в разделе '🗃️ История'.",
                reply_markup=build_thanks_menu_markup()
            )
            await callback.answer("✅ Благодарность сохранена!")
        except Exception as e:
            logger.exception("Error saving gratitude: %s", e)
            await callback.answer("❌ Ошибка при сохранении. Попробуй ещё раз.", show_alert=True)
        return
    
    if data == "thanks_cancel":
        await state.clear()
        await callback.message.edit_text(
            "🙏 Благодарности\n\n"
            "Благодарность помогает переключить мышление и снизить тревогу.\n\n"
            "Записывай за что ты благодарен — это может быть что угодно.",
            reply_markup=build_thanks_menu_markup()
        )
        await callback.answer("Отменено")
        return

    if data == "thanks_history":
        try:
            token = await get_or_fetch_token(telegram_id, callback.from_user.username, callback.from_user.first_name)
            if not token:
                await callback.answer("Ошибка авторизации")
                return

            gratitudes_data = await BACKEND_CLIENT.get_gratitudes(token, page=1, page_size=20)
            gratitudes = gratitudes_data.get("gratitudes", []) if gratitudes_data else []
            total = gratitudes_data.get("total", 0) if gratitudes_data else 0

            if not gratitudes:
                history_text = "🗃️ История благодарностей\n\nПока записей нет. Добавь свою первую благодарность!"
            else:
                history_text = f"🗃️ История благодарностей\n\nВсего записей: {total}\n\n"
                for i, g in enumerate(gratitudes[:10], 1):
                    created_at = g.get("created_at", "")
                    if created_at:
                        try:
                            from datetime import datetime
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            date_str = dt.strftime("%d.%m.%Y")
                        except:
                            date_str = ""
                    else:
                        date_str = ""

                    text = g.get("text", "")[:100]
                    if len(g.get("text", "")) > 100:
                        text += "..."

                    history_text += f"{i}. {text}\n"
                    if date_str:
                        history_text += f"   📅 {date_str}\n"
                    history_text += "\n"

                if total > 10:
                    history_text += f"\n... и ещё {total - 10} записей"

            await callback.message.edit_text(
                history_text,
                reply_markup=build_thanks_history_markup()
            )
        except Exception as e:
            logger.exception("Error loading gratitude history: %s", e)
            await callback.message.edit_text(
                "🗃️ История благодарностей\n\n"
                "❌ Ошибка при загрузке истории. Попробуй позже.",
                reply_markup=build_thanks_history_markup()
            )
        await callback.answer()
        return

    if data.startswith("thanks_page_"):
        page = int(data.replace("thanks_page_", ""))
        await callback.answer(f"Страница {page}")
        return

    await callback.answer()

async def handle_thanks_entry_input(message: Message, state: FSMContext) -> None:
    """Handle input for gratitude entry - store text and show save button"""
    text = message.text.strip()
    
    if not text:
        await message.answer("Пожалуйста, напиши текст благодарности.")
        return
    
    # Сохраняем текст в состояние
    await state.update_data(gratitude_text=text)
    
    await send_long_message(
        message,
        f"📝 Текст благодарности:\n\n{text}\n\n"
        "Нажми '💾 Сохранить' чтобы сохранить или '❌ Отмена' чтобы отменить.",
        reply_markup=build_thanks_input_markup()
    )

