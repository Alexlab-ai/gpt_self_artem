# twelvesteps/services/profile.py
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from ..db.models import ProfileAnswer, ProfileSection, User
from ..repositories.profile_repository import ProfileRepository
from ..core.llm_service import generate_gpt_response  # предполагаем, что есть
from ..services.tracker_service import TrackerService

tracker_service = TrackerService()

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProfileRepository(db)

    async def get_next_question(self, user_id: int, section_id: Optional[int] = None) -> Optional[dict]:
        # Фаза 1: Только фиксированные вопросы (по 4 на раздел)
        total_answered = await self.repo.get_total_answered(user_id)
        if total_answered >= 52:
            # Фаза 1 завершена → предлагаем Фазу 2
            return None  # или специальное сообщение "Базовый профиль завершён"

        if section_id is None:
            section_id = await self.repo.get_next_section(user_id)

        fixed_questions = await self.repo.get_fixed_questions(section_id)  # список из 4 вопросов
        answered_in_section = await self.repo.get_answered_in_section(user_id, section_id)

        if answered_in_section < len(fixed_questions):
            next_q = fixed_questions[answered_in_section]
            # Персонализация вопроса (опционально)
            user = await self.repo.get_user(user_id)
            personalized = await self._personalize_question(next_q, user)
            return {"question": personalized, "section_id": section_id, "question_id": next_q.id}
        
        return None  # Переход к следующему разделу

    async def _personalize_question(self, question, user):
        # Пример: добавить контекст из онбординга/шагов
        context = f"Учитывая опыт АН: {user.program_experience}, дата трезвости: {user.sobriety_date}"
        prompt = f"Адаптируй вопрос для пользователя: {question.text}\nКонтекст: {context}"
        return await generate_gpt_response(prompt, model="gpt-4o-mini")

    async def save_answer(self, user_id: int, section_id: int, question_id: int, answer: str):
        await self.repo.save_answer(user_id, section_id, question_id, answer)
        
        # Обновление трекера чувств
        emotions = await self._extract_emotions(answer)  # твоя функция извлечения
        if emotions:
            await tracker_service.update_feeling(user_id, emotions, source="profile")

        # Обновление персонализации
        await self.repo.update_personalized_prompt(user_id)

    async def check_completion_and_offer_deepening(self, user_id: int):
        total = await self.repo.get_total_answered(user_id)
        if total >= 52:
            # Отправить сообщение в бот: "Базовый профиль завершён. Хочешь углубить? (да/нет)"
            pass  # логика в боте

    # Фаза 2: углубление (по запросу пользователя)
    async def start_deepening(self, user_id: int, count: int = 3):
        profile_data = await self.repo.get_full_profile(user_id)
        prompt = f"Сгенерируй {count} уточняющих вопросов на основе профиля:\n{profile_data}"
        questions = await generate_gpt_response(prompt, model="gpt-4o")
        return questions.split("\n")  # или парсинг JSON
