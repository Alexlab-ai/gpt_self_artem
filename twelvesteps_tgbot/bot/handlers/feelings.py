from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.config import (
    build_all_feelings_markup,
    build_feelings_category_markup,
    build_fears_markup,
    build_main_menu_markup,
    FEELINGS_CATEGORIES,
    FEARS_LIST,
)
from .shared import MAIN_MENU_TEXT

async def handle_feelings(message: Message, state: FSMContext) -> None:
    """Handle Feelings button - show feelings categories menu"""
    await message.answer("📘 Чувства", reply_markup=build_all_feelings_markup())

async def handle_feelings_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle feelings navigation callbacks"""
    data = callback.data

    if data == "feelings_back":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
        await callback.answer()
        return

    if data == "feelings_categories":
        await callback.message.edit_text("📘 Чувства", reply_markup=build_all_feelings_markup())
        await callback.answer()
        return

    if data.startswith("feelings_cat_"):
        category = data.replace("feelings_cat_", "")

        full_category = None
        for cat_name in FEELINGS_CATEGORIES.keys():
            if cat_name == category or category in cat_name:
                full_category = cat_name
                break

        if full_category:
            await callback.message.edit_text(
                f"{full_category}",
                reply_markup=build_feelings_category_markup(full_category)
            )
        await callback.answer()
        return

    if data == "feelings_fears":
        fears_text = "⚠️ СТРАХИ\n\n" + "\n".join([f"• {fear}" for fear in FEARS_LIST])
        fears_text += "\n\n💡 Нажми на страх, чтобы скопировать:"

        await callback.message.edit_text(fears_text, reply_markup=build_fears_markup())
        await callback.answer()
        return

    if data == "feelings_noop":
        await callback.answer()
        return

    await callback.answer()

async def handle_feeling_selection_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle feeling selection - show the feeling for copying"""
    data = callback.data

    if data.startswith("feeling_copy_") or data.startswith("feeling_select_"):
        feeling = data.replace("feeling_copy_", "").replace("feeling_select_", "")

        await callback.answer(f"💡 {feeling}", show_alert=True)
        return

    await callback.answer()
