from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.ProfileRepository import ProfileRepository
from db.models import (
    ProfileSection,
    ProfileSectionData,
    ProfileQuestion,
    ProfileAnswer,
)
from llm.openai_provider import OpenAI


class ProfileService:
    def __init__(self, session: AsyncSession):
        self.repo = ProfileRepository(session)
        self.session = session

    async def get_all_sections(self, user_id: Optional[int] = None) -> List[ProfileSection]:
        """Get all sections available to user"""
        return await self.repo.get_all_sections(user_id)

    async def get_section_detail(
        self, section_id: int, user_id: Optional[int] = None
    ) -> Optional[ProfileSection]:
        """Get section with questions and check if user has data"""
        try:
            section = await self.repo.get_section_by_id(section_id)
            if not section:
                return None

            if user_id:
                try:
                    data = await self.repo.get_section_data(user_id, section_id)
                    section.has_data = data is not None
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error checking section data for user {user_id}, section {section_id}: {e}")
                    section.has_data = False

            return section
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in get_section_detail for section_id={section_id}, user_id={user_id}: {e}")
            raise

    async def save_answer(
        self, user_id: int, question_id: int, answer_text: str
    ) -> Tuple[ProfileAnswer, Optional[ProfileQuestion]]:
        answer = await self.repo.save_answer(user_id, question_id, answer_text)

        await self.session.flush()

        from sqlalchemy import select
        query = select(ProfileQuestion).where(ProfileQuestion.id == question_id)
        result = await self.session.execute(query)
        question = result.scalar_one_or_none()

        if question:
            await self.session.refresh(answer)
            next_question = await self.get_next_question_for_section(
                user_id, question.section_id, answer_text
            )
            return answer, next_question

        return answer, None

    async def save_free_text(
        self,
        user_id: int,
        section_id: Optional[int],
        text: str,
        subblock_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        importance: Optional[float] = 1.0,
        is_core_personality: bool = False,
        tags: Optional[str] = None
    ) -> ProfileSectionData:
        """Save free text as a new entry (history). If section_id is None, it's a general free text"""
        if section_id is None:
            raise ValueError("section_id is required for free text")

        return await self.repo.save_free_text(
            user_id=user_id,
            section_id=section_id,
            content=text,
            subblock_name=subblock_name,
            entity_type=entity_type,
            importance=importance,
            is_core_personality=is_core_personality,
            tags=tags
        )

    async def get_section_data_history(
        self, user_id: int, section_id: int, limit: Optional[int] = None
    ) -> List[ProfileSectionData]:
        """Get history of entries for a section"""
        return await self.repo.get_section_data_history(user_id, section_id, limit)

    async def get_section_data_by_subblock(
        self, user_id: int, section_id: int, subblock_name: str
    ) -> List[ProfileSectionData]:
        """Get all entries for a specific subblock"""
        return await self.repo.get_section_data_by_subblock(user_id, section_id, subblock_name)

    async def create_custom_section(
        self, user_id: int, name: str, icon: Optional[str] = None
    ) -> ProfileSection:
        """Create a custom section for user"""
        return await self.repo.create_custom_section(user_id, name, icon)

    async def update_section(
        self, section_id: int, name: Optional[str] = None,
        icon: Optional[str] = None, order_index: Optional[int] = None
    ) -> Optional[ProfileSection]:
        """Update a custom section"""
        return await self.repo.update_section(section_id, name, icon, order_index)

    async def delete_section(self, section_id: int, user_id: int) -> bool:
        """Delete a custom section (only custom sections owned by user)"""
        return await self.repo.delete_section(section_id, user_id)

    async def get_section_summary(
        self, user_id: int, section_id: int
    ) -> dict:
        """Get summary for a section"""
        return await self.repo.get_section_summary(user_id, section_id)

    def split_long_message(self, text: str, max_length: int = 4096) -> List[str]:
        """Split long message into chunks."""
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        paragraphs = text.split('\n\n')

        for para in paragraphs:
            if len(para) > max_length:
                sentences = para.split('. ')
                for i, sentence in enumerate(sentences):
                    if i < len(sentences) - 1:
                        sentence += '. '

                    if len(current_chunk) + len(sentence) > max_length:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = sentence
                        else:
                            words = sentence.split()
                            for word in words:
                                if len(current_chunk) + len(word) + 1 > max_length:
                                    if current_chunk:
                                        chunks.append(current_chunk.strip())
                                        current_chunk = word
                                    else:
                                        chunks.append(word[:max_length])
                                        current_chunk = word[max_length:]
                                else:
                                    current_chunk += (' ' if current_chunk else '') + word
                    else:
                        current_chunk += sentence
            else:
                if len(current_chunk) + len(para) + 2 > max_length:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = para
                    else:
                        chunks.append(para)
                else:
                    current_chunk += ('\n\n' if current_chunk else '') + para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def get_next_question_for_section(
        self, user_id: int, section_id: int, last_answer: Optional[str] = None
    ) -> Optional[ProfileQuestion]:
        """Get the next unanswered question for a section."""
        section = await self.repo.get_section_by_id(section_id)
        if not section:
            return None

        questions = section.questions
        if not questions:
            return None

        user_answers = await self.repo.get_user_answers_for_section(user_id, section_id)
        answered_question_ids = {ans.question_id for ans in user_answers}

        unanswered = [q for q in questions if q.id not in answered_question_ids]

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[ProfileService.get_next_question_for_section] Section {section_id}: "
                   f"Total questions: {len(questions)}, "
                   f"Answered: {len(answered_question_ids)}, "
                   f"Unanswered: {len(unanswered)}, "
                   f"Has last_answer: {last_answer is not None}")

        if not unanswered and last_answer:
            # MVP / prod-safe mode:
            # while the user is passing the fixed base questionnaire,
            # we do NOT generate GPT follow-up questions inside a section.
            # This keeps the survey predictable: 52 base questions only.
            #
            # The dynamic deepening mode should be implemented later as a
            # separate phase AFTER all base questions are completed.
            return None

        if not unanswered:
            return None

        if not last_answer:
            return unanswered[0] if unanswered else None

        if unanswered:
            return unanswered[0]

        return None

    async def _suggest_next_question(
        self,
        section: ProfileSection,
        unanswered_questions: List[ProfileQuestion],
        last_answer: str
    ) -> ProfileQuestion:
        llm = OpenAI()

        questions_text = "\n".join([
            f"{i+1}. [ID: {q.id}] {q.question_text}"
            for i, q in enumerate(unanswered_questions)
        ])

        system_prompt = "Ты помогаешь выбрать следующий вопрос для профиля. Верни только номер вопроса (1, 2, 3 и т.д.) без дополнительного текста."

        user_prompt = f"Последний ответ пользователя: {last_answer}\n\nСписок вопросов:\n{questions_text}\n\nКакой вопрос задать следующим? Верни только номер."

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            from openai import AsyncOpenAI
            import os
            from dotenv import load_dotenv
            load_dotenv()

            async with AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) as client:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=10,
                    temperature=0.3,
                )

            suggestion = response.choices[0].message.content.strip()
            try:
                question_num = int(''.join(filter(str.isdigit, suggestion)))
                if 1 <= question_num <= len(unanswered_questions):
                    return unanswered_questions[question_num - 1]
            except ValueError:
                pass

            return unanswered_questions[0]

        except Exception as e:
            print(f"[ProfileService._suggest_next_question] Error: {e}")
            return unanswered_questions[0]

    async def _generate_follow_up_question(
        self,
        user_id: int,
        section: ProfileSection,
        last_answer: str
    ) -> Optional[ProfileQuestion]:
        """Generate a follow-up question based on the last answer."""
        from repositories.PromptRepository import PromptRepository
        from db.models import ProfileQuestion

        prompt_template = await PromptRepository.load_profile_next_question_prompt()
        if not prompt_template:
            return None

        user_answers = await self.repo.get_user_answers_for_section(user_id, section.id)

        answers_text = ""
        for answer in user_answers:
            from sqlalchemy import select
            query = select(ProfileQuestion).where(ProfileQuestion.id == answer.question_id)
            result = await self.session.execute(query)
            question = result.scalar_one_or_none()
            if question:
                answers_text += f"Вопрос: {question.question_text}\n"
                answers_text += f"Ответ: {answer.answer_text}\n\n"

        from repositories.UserRepository import UserRepository
        user_repo = UserRepository(self.session)
        personalized_prompt = await user_repo.get_personalized_prompt(user_id) or "Нет персонализации."


        prompt = prompt_template.replace("[НАЗВАНИЕ_БЛОКА]", section.name)
        full_prompt = f"""{prompt}

Предыдущие ответы пользователя:
{answers_text}

Последний ответ: {last_answer}

Персонализация: {personalized_prompt}

Сформулируй уточняющий вопрос (или верни пустую строку, если не нужен)."""

        try:
            from openai import AsyncOpenAI
            import os
            from dotenv import load_dotenv
            load_dotenv()

            async with AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")) as client:
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "Ты помогаешь формулировать уточняющие вопросы для психологического профиля."},
                        {"role": "user", "content": full_prompt}
                    ],
                    max_tokens=150,
                    temperature=0.7,
                )

            generated_question = response.choices[0].message.content.strip()

            if not generated_question or len(generated_question) < 10:
                return None

            temp_question = ProfileQuestion(
                id=-1,
                section_id=section.id,
                question_text=generated_question,
                order_index=999,
                is_optional=True
            )
            return temp_question

        except Exception as e:
            print(f"[ProfileService._generate_follow_up_question] Error: {e}")
            return None

    async def get_fsm_state(
        self, user_id: int, section_id: int
    ) -> dict:
        """Get FSM state for a section."""
        section = await self.repo.get_section_by_id(section_id)
        if not section:
            return {
                "current_question_id": None,
                "answered_count": 0,
                "total_questions": 0,
                "is_complete": False,
            }

        questions = section.questions
        user_answers = await self.repo.get_user_answers_for_section(user_id, section_id)
        answered_question_ids = {ans.question_id for ans in user_answers}

        unanswered = [q for q in questions if q.id not in answered_question_ids]
        current_question = unanswered[0] if unanswered else None

        return {
            "current_question_id": current_question.id if current_question else None,
            "answered_count": len(answered_question_ids),
            "total_questions": len(questions),
            "is_complete": len(unanswered) == 0,
        }

