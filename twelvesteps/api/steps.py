from datetime import datetime
from typing import Optional, Union

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Step, Question, StepAnswer, UserStep,
    Tail, TailType, StepProgressStatus, User, AnswerTemplate
)
import json

class StepFlowService:
    MIN_ANSWER_LENGTH = 50

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_step_info(self, user_id: int) -> Optional[dict]:
        """Get current step information including step number"""
        from sqlalchemy.orm import selectinload

        stmt_user_step = select(UserStep).where(
            UserStep.user_id == user_id,
            UserStep.status == StepProgressStatus.IN_PROGRESS
        )

        result = await self.session.execute(stmt_user_step)
        current_user_step = result.scalars().first()

        if not current_user_step:
            current_user_step = await self._initialize_next_step(user_id)
            if not current_user_step:
                return None

        stmt_step = select(Step).where(Step.id == current_user_step.step_id)
        result_step = await self.session.execute(stmt_step)
        step = result_step.scalars().first()

        if not step:
            return None

        stmt_total = select(Step).order_by(Step.index.desc()).limit(1)
        result_total = await self.session.execute(stmt_total)
        last_step = result_total.scalars().first()
        total_steps = last_step.index if last_step else 12

        stmt_answered = select(func.count()).select_from(StepAnswer).where(
            StepAnswer.user_id == user_id,
            StepAnswer.step_id == current_user_step.step_id
        )
        result_answered = await self.session.execute(stmt_answered)
        answered_count = result_answered.scalar() or 0

        stmt_questions = select(func.count()).select_from(Question).where(
            Question.step_id == current_user_step.step_id
        )
        result_questions = await self.session.execute(stmt_questions)
        total_questions = result_questions.scalar() or 0

        return {
            "step_id": step.id,
            "step_number": step.index,
            "step_title": step.title,
            "step_description": step.description,
            "total_steps": total_steps,
            "answered_questions": answered_count,
            "total_questions": total_questions,
            "status": current_user_step.status.value
        }

    async def get_all_steps(self) -> list[dict]:
        """Get list of all steps"""
        stmt = select(Step).order_by(Step.index)
        result = await self.session.execute(stmt)
        steps = result.scalars().all()

        return [{"id": s.id, "number": s.index} for s in steps]

    async def get_step_questions(self, step_id: int) -> list[dict]:
        """Get list of questions for a step"""
        stmt = select(Question).where(Question.step_id == step_id).order_by(Question.id)
        result = await self.session.execute(stmt)
        questions = result.scalars().all()

        return [
            {"id": int(q.id), "text": str(q.text) if q.text else ""}
            for q in questions
            if q.id is not None
        ]

    async def save_draft(self, user_id: int, draft_text: str) -> bool:
        """Save draft answer in Tail.payload without closing Tail"""
        import logging
        logger = logging.getLogger(__name__)

        stmt = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        )
        result = await self.session.execute(stmt)
        active_tail = result.scalars().first()

        logger.info(f"save_draft for user {user_id}: active_tail={active_tail is not None}")

        if not active_tail:
            logger.warning(f"No active tail found for user {user_id} to save draft")
            return False

        if active_tail.payload is None:
            active_tail.payload = {}

        new_payload = dict(active_tail.payload) if active_tail.payload else {}
        new_payload["draft"] = draft_text
        new_payload["draft_saved_at"] = datetime.now().isoformat()
        active_tail.payload = new_payload

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(active_tail, "payload")

        logger.info(f"Saving draft to tail {active_tail.id}, payload keys: {list(active_tail.payload.keys())}")

        await self.session.flush()

        await self.session.commit()
        logger.info(f"Committed draft save for tail {active_tail.id}")

        await self.session.refresh(active_tail)
        saved_draft = active_tail.payload.get("draft") if active_tail.payload else None
        logger.info(f"Draft saved verification for user {user_id}, tail {active_tail.id}: saved_draft length={len(saved_draft) if saved_draft else 0}, payload keys: {list(active_tail.payload.keys()) if active_tail.payload else 'None'}")

        return True

    async def get_previous_answer(self, user_id: int, question_id: int) -> Optional[str]:
        """Get previous answer for a question if exists"""
        stmt = select(StepAnswer).where(
            StepAnswer.user_id == user_id,
            StepAnswer.question_id == question_id
        ).order_by(desc(StepAnswer.version)).limit(1)

        result = await self.session.execute(stmt)
        previous_answer = result.scalars().first()

        if previous_answer:
            return previous_answer.answer_text
        return None

    async def get_active_tail_draft(self, user_id: int) -> Optional[str]:
        """Get draft from active Tail if exists"""
        import logging
        logger = logging.getLogger(__name__)

        stmt = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        )
        result = await self.session.execute(stmt)
        active_tail = result.scalars().first()

        logger.info(f"get_active_tail_draft for user {user_id}: active_tail={active_tail is not None}, tail_id={active_tail.id if active_tail else None}")

        if active_tail:
            await self.session.refresh(active_tail)
            logger.info(f"Active tail found: id={active_tail.id}, payload type={type(active_tail.payload)}, payload={active_tail.payload}")

            if active_tail.payload and "draft" in active_tail.payload:
                draft_value = active_tail.payload["draft"]
                logger.info(f"Draft found in payload: length={len(draft_value) if draft_value else 0}")
                return draft_value
            else:
                payload_keys = list(active_tail.payload.keys()) if active_tail.payload else None
                logger.warning(f"No draft in payload for user {user_id}, tail_id={active_tail.id}, payload keys: {payload_keys}")
        else:
            logger.warning(f"No active tail found for user {user_id}")

        return None

    async def get_example_answers(self, question_id: int, user_id: int, limit: int = 5) -> list[dict]:
        """Get example answers for a question from other users (anonymized)"""
        from sqlalchemy import func

        stmt = (
            select(StepAnswer)
            .where(
                StepAnswer.question_id == question_id,
                StepAnswer.user_id != user_id
            )
            .order_by(func.random())
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        answers = result.scalars().all()

        examples = []
        for answer in answers:
            answer_text = answer.answer_text
            if len(answer_text) > 200:
                answer_text = answer_text[:200] + "..."
            examples.append({
                "text": answer_text,
                "preview": answer_text[:100] + "..." if len(answer_text) > 100 else answer_text
            })

        return examples

    async def get_active_question_id(self, user_id: int) -> Optional[int]:
        """Get question_id from active Tail if exists"""
        stmt = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        )
        result = await self.session.execute(stmt)
        active_tail = result.scalars().first()

        if active_tail and active_tail.step_question_id:
            return active_tail.step_question_id
        return None

    async def get_last_answered_question_id(self, user_id: int) -> Optional[int]:
        """Get question_id from the last answered question (last closed Tail)"""
        stmt = (
            select(Tail)
            .where(
                Tail.user_id == user_id,
                Tail.tail_type == TailType.STEP_QUESTION,
                Tail.is_closed == True
            )
            .order_by(desc(Tail.closed_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        last_tail = result.scalars().first()

        if last_tail and last_tail.step_question_id:
            return last_tail.step_question_id
        return None

    async def switch_to_question(self, user_id: int, question_id: int) -> Optional[str]:
        """Switch to a specific question, also switching step if needed"""
        stmt_question = select(Question).where(Question.id == question_id)
        result_q = await self.session.execute(stmt_question)
        question = result_q.scalars().first()

        if not question:
            return None

        target_step_id = question.step_id

        stmt_user_step = select(UserStep).where(
            UserStep.user_id == user_id,
            UserStep.status == StepProgressStatus.IN_PROGRESS
        )
        result = await self.session.execute(stmt_user_step)
        current_user_step = result.scalars().first()

        if not current_user_step or current_user_step.step_id != target_step_id:
            if current_user_step:
                current_user_step.status = StepProgressStatus.NOT_STARTED

            stmt_target_step = select(UserStep).where(
                UserStep.user_id == user_id,
                UserStep.step_id == target_step_id
            )
            result_target = await self.session.execute(stmt_target_step)
            target_user_step = result_target.scalars().first()

            if target_user_step:
                target_user_step.status = StepProgressStatus.IN_PROGRESS
            else:
                target_user_step = UserStep(
                    user_id=user_id,
                    step_id=target_step_id,
                    status=StepProgressStatus.IN_PROGRESS,
                    started_at=datetime.now()
                )
                self.session.add(target_user_step)

        stmt_tail = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        )
        result_tail = await self.session.execute(stmt_tail)
        current_tail = result_tail.scalars().first()

        if current_tail:
            current_tail.is_closed = True
            current_tail.closed_at = datetime.now()

        new_tail = Tail(
            user_id=user_id,
            tail_type=TailType.STEP_QUESTION,
            step_id=target_step_id,
            step_question_id=question_id,
            is_closed=False,
            payload={}
        )
        self.session.add(new_tail)
        await self.session.commit()

        return question.text

    async def get_next_question_for_user(self, user_id: int) -> Union[str, None]:
        stmt_tail = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        ).options(selectinload(Tail.question))

        result_tail = await self.session.execute(stmt_tail)
        active_tail = result_tail.scalars().first()

        if active_tail:
            if active_tail.question:
                return active_tail.question.text
            else:
                if active_tail.step_question_id:
                    stmt_q = select(Question).where(Question.id == active_tail.step_question_id)
                    result_q = await self.session.execute(stmt_q)
                    question = result_q.scalars().first()
                    if question:
                        return question.text
                return None

        stmt_user_step = select(UserStep).where(
            UserStep.user_id == user_id,
            UserStep.status == StepProgressStatus.IN_PROGRESS
        )
        result_step = await self.session.execute(stmt_user_step)
        current_user_step = result_step.scalars().first()

        if not current_user_step:
            current_user_step = await self._initialize_next_step(user_id)
            if not current_user_step:
                return None

        next_question = await self._find_next_unanswered_question(
            user_id, current_user_step.step_id
        )

        if not next_question:
            await self._complete_step(current_user_step)
            return await self.get_next_question_for_user(user_id)

        new_tail = Tail(
            user_id=user_id,
            tail_type=TailType.STEP_QUESTION,
            step_id=current_user_step.step_id,
            step_question_id=next_question.id,
            is_closed=False,
            payload={}
        )
        self.session.add(new_tail)
        await self.session.commit()

        return next_question.text

    def validate_answer_length(self, answer_text: str, is_template_format: bool = False) -> tuple[bool, str]:
        if is_template_format:
            try:
                template_data = json.loads(answer_text)
                total_length = 0
                for key, value in template_data.items():
                    if isinstance(value, str):
                        total_length += len(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, str):
                                total_length += len(item)
                            elif isinstance(item, dict):
                                for v in item.values():
                                    if isinstance(v, str):
                                        total_length += len(v)

                if total_length < self.MIN_ANSWER_LENGTH:
                    return False, f"⚠️ Ответ слишком короткий ({total_length} символов). Минимум: {self.MIN_ANSWER_LENGTH} символов. Пожалуйста, раскрой ответ подробнее."
            except json.JSONDecodeError:
                if len(answer_text.strip()) < self.MIN_ANSWER_LENGTH:
                    return False, f"⚠️ Ответ слишком короткий ({len(answer_text.strip())} символов). Минимум: {self.MIN_ANSWER_LENGTH} символов. Пожалуйста, раскрой ответ подробнее."
        else:
            if len(answer_text.strip()) < self.MIN_ANSWER_LENGTH:
                return False, f"⚠️ Ответ слишком короткий ({len(answer_text.strip())} символов). Минимум: {self.MIN_ANSWER_LENGTH} символов.\n\nРаскрой ответ подробнее - это поможет глубже проработать вопрос."

        return True, ""

    async def save_user_answer(self, user_id: int, answer_text: str, is_template_format: bool = False, skip_validation: bool = False) -> tuple[bool, str]:
        stmt = select(Tail).where(
            Tail.user_id == user_id,
            Tail.tail_type == TailType.STEP_QUESTION,
            Tail.is_closed == False
        )
        result = await self.session.execute(stmt)
        active_tail = result.scalars().first()

        if not active_tail:
            return False, "Нет активного вопроса. Нажми /steps, чтобы начать."

        if not skip_validation:
            is_valid, error_msg = self.validate_answer_length(answer_text, is_template_format)
            if not is_valid:
                return False, error_msg

        stmt_user = select(User).where(User.id == user_id)
        result_user = await self.session.execute(stmt_user)
        user = result_user.scalars().first()

        final_answer_text = answer_text

        if is_template_format:
            try:
                template_data = json.loads(answer_text)
                final_answer_text = json.dumps(template_data, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                final_answer_text = answer_text
        elif user and user.active_template_id:
            final_answer_text = answer_text

        new_answer = StepAnswer(
            user_id=user_id,
            step_id=active_tail.step_id,
            question_id=active_tail.step_question_id,
            answer_text=final_answer_text,
            version=1
        )
        self.session.add(new_answer)

        active_tail.is_closed = True
        active_tail.closed_at = datetime.now()

        from services.personalization_service import update_personalized_prompt_from_all_answers
        await update_personalized_prompt_from_all_answers(self.session, user_id)

        return True, ""

    async def get_current_step_questions(self, user_id: int) -> list[dict]:
        """Get list of questions for current step"""
        stmt_user_step = select(UserStep).where(
            UserStep.user_id == user_id,
            UserStep.status == StepProgressStatus.IN_PROGRESS
        )
        result = await self.session.execute(stmt_user_step)
        current_user_step = result.scalars().first()

        if not current_user_step:
            return []

        return await self.get_step_questions(current_user_step.step_id)


    async def _initialize_next_step(self, user_id: int) -> Optional[UserStep]:
        stmt_last = select(Step).join(UserStep).where(
            UserStep.user_id == user_id,
            UserStep.status == StepProgressStatus.COMPLETED
        ).order_by(desc(Step.index)).limit(1)

        result_last = await self.session.execute(stmt_last)
        last_step = result_last.scalars().first()

        next_index = 1 if not last_step else last_step.index + 1

        stmt_next_step_def = select(Step).where(Step.index == next_index)
        result_def = await self.session.execute(stmt_next_step_def)
        next_step_def = result_def.scalars().first()

        if not next_step_def:
            return None

        new_user_step = UserStep(
            user_id=user_id,
            step_id=next_step_def.id,
            status=StepProgressStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        self.session.add(new_user_step)
        await self.session.commit()
        return new_user_step

    async def _find_next_unanswered_question(self, user_id: int, step_id: int) -> Optional[Question]:
        stmt_questions = select(Question).where(
            Question.step_id == step_id
        ).order_by(Question.id)

        stmt_answers = select(StepAnswer.question_id).where(
            StepAnswer.user_id == user_id,
            StepAnswer.step_id == step_id
        )

        res_q = await self.session.execute(stmt_questions)
        questions = res_q.scalars().all()

        res_a = await self.session.execute(stmt_answers)
        answered_ids = set(res_a.scalars().all())

        for q in questions:
            if q.id not in answered_ids:
                return q

        return None

    async def _complete_step(self, user_step: UserStep):
        """Marks a user step as completed."""
        user_step.status = StepProgressStatus.COMPLETED
        user_step.completed_at = datetime.now()
        await self.session.commit()