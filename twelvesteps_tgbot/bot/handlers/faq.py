from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.config import build_faq_menu_markup, build_faq_section_markup, build_main_menu_markup, FAQ_SECTIONS
from bot.utils import edit_long_message
from .shared import MAIN_MENU_TEXT

async def handle_faq(message: Message, state: FSMContext) -> None:
    """Handle FAQ command - show instructions menu"""
    faq_text = "📎 ИНСТРУКЦИИ — КАК ЭТО РАБОТАЕТ\n\nВыбери раздел для просмотра:"
    await message.answer(faq_text, reply_markup=build_faq_menu_markup())

async def handle_faq_callback(callback: CallbackQuery, state: FSMContext) -> None:
    """Handle FAQ/Instructions callbacks"""
    data = callback.data

    if data == "faq_back":
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(MAIN_MENU_TEXT, reply_markup=build_main_menu_markup())
        await callback.answer()
        return

    if data == "faq_menu":
        faq_text = "📎 ИНСТРУКЦИИ — КАК ЭТО РАБОТАЕТ\n\nВыбери раздел для просмотра:"
        await callback.message.edit_text(faq_text, reply_markup=build_faq_menu_markup())
        await callback.answer()
        return

    if data.startswith("faq_section_"):
        section_name = data.replace("faq_section_", "")
        section_text = FAQ_SECTIONS.get(section_name)

        if section_text:
            await edit_long_message(
                callback,
                section_text,
                reply_markup=build_faq_section_markup()
            )
        else:
            await callback.answer("Раздел не найден")
        await callback.answer()
        return

    await callback.answer()
