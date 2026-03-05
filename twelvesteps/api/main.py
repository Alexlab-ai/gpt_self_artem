from typing import Optional
from datetime import date
from fastapi import Depends, FastAPI, HTTPException, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from dotenv import load_dotenv
import traceback

from api.dependencies import CurrentUserContext, get_current_user, get_db, get_db_session
from api.schemas import (
    AnswerRequest,
    ChatRequest,
    ChatResponse,
    ProfileUpdateRequest,
    StatusResponse,
    StepResponse,
    StepInfoResponse,
    StepListResponse,
    StepQuestionsResponse,
    StepQuestionItem,
    DraftRequest,
    DraftResponse,
    PreviousAnswerResponse,
    SwitchQuestionRequest,
    StepsSettingsResponse,
    StepsSettingsUpdateRequest,
    TelegramAuthRequest,
    TelegramAuthResponse,
    UserSchema,
    SosRequest,
    SosResponse,
    SosChatRequest,
    SosChatResponse,
    ProfileSectionListResponse,
    ProfileSectionDetailResponse,
    ProfileSectionDetailSchema,
    ProfileAnswerRequest,
    FreeTextRequest,
    CustomSectionRequest,
    SectionUpdateRequest,
    SectionSummaryResponse,
    ProfileSectionDataCreateRequest,
    ProfileSectionDataUpdateRequest,
    AnswerTemplateSchema,
    AnswerTemplateListResponse,
    AnswerTemplateCreateRequest,
    AnswerTemplateUpdateRequest,
    ActiveTemplateRequest,
    TemplateProgressStartRequest,
    TemplateProgressResponse,
    TemplateFieldSubmitRequest,
    TemplateFieldSubmitResponse,
    TemplatePauseRequest,
    TemplatePauseResponse,
    TemplateFieldsInfoResponse,
    TemplateFieldInfo,
    Step10StartRequest,
    Step10StartResponse,
    Step10SubmitAnswerRequest,
    Step10SubmitAnswerResponse,
    Step10PauseRequest,
    Step10PauseResponse,
    Step10ProgressResponse,
    Step10QuestionData,
    SessionStateResponse,
    SessionStateUpdateRequest,
    FrameTrackingResponse,
    FrameTrackingUpdateRequest,
    QAStatusResponse,
    QAStatusUpdateRequest,
    TrackerSummaryResponse,
    TrackerSummaryCreateRequest,
    UserMetaResponse,
    UserMetaUpdateRequest,
    GratitudeCreateRequest,
    GratitudeListResponse,
    GratitudeItem,
)
from api.steps import StepFlowService
from core.chat_service import handle_chat, handle_sos, handle_thanks, handle_day
from services.status import StatusService
from services.users import UserService
from services.profile import ProfileService
from services.template_service import TemplateService
from services.sos_service import SosService
from services.steps_settings_service import StepsSettingsService
from repositories.SessionStateRepository import SessionStateRepository
from repositories.FrameTrackingRepository import FrameTrackingRepository
from repositories.QAStatusRepository import QAStatusRepository
from repositories.UserMetaRepository import UserMetaRepository
from repositories.TrackerSummaryRepository import TrackerSummaryRepository
from repositories.GratitudeRepository import GratitudeRepository
from datetime import date as date_class
import pathlib

env_path = pathlib.Path(__file__).parent.parent.parent / "backend.env"
load_dotenv(env_path)

app = FastAPI(title="12STEPS Chat API")

@app.get("/health")
async def health_check():
    """Health check endpoint for Render and monitoring"""
    return {"status": "ok", "service": "twelvesteps-backend"}

@app.get("/")
async def root():
    """Root endpoint for basic health check"""
    return {"status": "ok", "service": "twelvesteps-backend", "message": "API is running"}

@app.on_event("startup")
async def startup_event():
    """Initialize profile sections on application startup"""
    try:
        from db.init_profile_sections import init_profile_sections
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, init_profile_sections)
        print("✅ Profile sections initialized (if needed)")
    except Exception as e:
        print(f"⚠️ Warning: Could not initialize profile sections on startup: {e}")
        import traceback
        traceback.print_exc()

def build_user_schema(user) -> UserSchema:
    """Build UserSchema from User model."""
    return UserSchema(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        display_name=user.display_name,
        role=user.user_role.value if user.user_role else None,
        program_experience=user.program_experience,
        sobriety_date=user.sobriety_date,
        personal_prompt=user.personal_prompt,
        relapse_dates=user.relapse_dates,
        sponsor_ids=user.sponsor_ids,
        custom_fields=user.custom_fields,
        last_active=user.last_active,
        created_at=user.created_at,
        updated_at=user.updated_at
    )

@app.post("/auth/telegram", response_model=TelegramAuthResponse)
async def auth_telegram_endpoint(
    payload: TelegramAuthRequest,
    session: AsyncSession = Depends(get_db)
) -> TelegramAuthResponse:
    try:
        service = UserService(session)
        user, is_new = await service.authenticate_telegram(
            telegram_id=payload.telegram_id,
            username=payload.username,
            first_name=payload.first_name
        )

        return TelegramAuthResponse(
            user=build_user_schema(user),
            is_new=is_new,
            access_token=user.api_key
        )
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        reply = await handle_chat(payload.telegram_id, payload.message, payload.debug)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))
    return reply

@app.post("/thanks", response_model=ChatResponse)
async def thanks_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        reply = await handle_thanks(payload.telegram_id, payload.debug)
        return reply
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/day", response_model=ChatResponse)
async def day_endpoint(payload: ChatRequest) -> ChatResponse:
    try:
        reply = await handle_day(payload.telegram_id, payload.debug)
        return reply
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/sos", response_model=SosResponse)
async def sos_endpoint(payload: SosRequest) -> SosResponse:
    try:
        reply_text = await handle_sos(payload.telegram_id)
        return SosResponse(reply=reply_text)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/sos/chat", response_model=SosChatResponse)
async def sos_chat_endpoint(
    payload: SosChatRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> SosChatResponse:
    try:
        service = SosService(current_context.session)
        result = await service.chat(
            user_id=current_context.user.id,
            help_type=payload.help_type,
            custom_text=payload.custom_text,
            message=payload.message,
            conversation_history=payload.conversation_history
        )
        return SosChatResponse(
            reply=result["reply"],
            is_finished=result["is_finished"],
            conversation_history=result["conversation_history"]
        )
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/auth/telegram", response_model=TelegramAuthResponse)
async def authenticate_via_telegram(
    payload: TelegramAuthRequest,
    session: AsyncSession = Depends(get_db_session),
) -> TelegramAuthResponse:
    service = UserService(session)
    user, is_new = await service.authenticate_telegram(
        telegram_id=payload.telegram_id,
        username=payload.username,
        first_name=payload.first_name,
    )
    return TelegramAuthResponse(
        user=build_user_schema(user), is_new=is_new, access_token=user.api_key or ""
    )


@app.patch("/me", response_model=UserSchema)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: CurrentUserContext = Depends(get_current_user),
) -> UserSchema:
    service = UserService(current_user.session)
    updates = payload.model_dump(exclude_unset=True)
    user = await service.update_profile(current_user.user, updates)

    if any(key in updates for key in ['display_name', 'program_experience', 'sobriety_date']):
        from services.personalization_service import update_personalized_prompt_from_all_answers
        await update_personalized_prompt_from_all_answers(current_user.session, user.id)

    await current_user.session.flush()

    await current_user.session.refresh(user)

    await current_user.session.commit()

    return build_user_schema(user)


@app.get("/status", response_model=StatusResponse)
async def get_status(current_user: CurrentUserContext = Depends(get_current_user)) -> StatusResponse:
    service = StatusService(current_user.session)
    status_payload = await service.get_status_for_user(current_user.user)
    return StatusResponse(**status_payload)


@app.get("/steps/next", response_model=StepResponse)
async def get_next_step_question(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    service = StepFlowService(current_context.session)

    question_text = await service.get_next_question_for_user(current_context.user.id)

    if not question_text:
        return StepResponse(message="Program completed.", is_completed=True)

    return StepResponse(
        message=question_text,
        is_completed=False
    )

@app.get("/steps/current", response_model=StepInfoResponse)
async def get_current_step(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get current step information with progress indicators"""
    service = StepFlowService(current_context.session)
    step_info = await service.get_current_step_info(current_context.user.id)

    if not step_info:
        return StepInfoResponse()

    return StepInfoResponse(
        step_id=step_info.get("step_id"),
        step_number=step_info.get("step_number"),
        step_title=step_info.get("step_title"),
        step_description=step_info.get("step_description"),
        total_steps=step_info.get("total_steps"),
        answered_questions=step_info.get("answered_questions"),
        total_questions=step_info.get("total_questions"),
        status=step_info.get("status")
    )

@app.get("/steps/{step_id}/detail")
async def get_step_detail(
    step_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get detailed information about a specific step"""
    service = StepFlowService(current_context.session)
    step_detail = await service.get_step_detail(step_id)

    if not step_detail:
        raise HTTPException(status_code=404, detail="Step not found")

    return step_detail

@app.get("/steps/list", response_model=StepListResponse)
async def get_all_steps(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get list of all steps"""
    service = StepFlowService(current_context.session)
    steps = await service.get_all_steps()
    return StepListResponse(steps=steps)

@app.get("/steps/current/questions")
async def get_current_step_questions(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get list of questions for current step"""
    import logging
    from sqlalchemy import select
    from db.models import Step, UserStep, StepProgressStatus

    logger = logging.getLogger(__name__)

    try:
        service = StepFlowService(current_context.session)

        stmt_user_step = select(UserStep).where(
            UserStep.user_id == current_context.user.id,
            UserStep.status == StepProgressStatus.IN_PROGRESS
        )
        result = await current_context.session.execute(stmt_user_step)
        current_user_step = result.scalars().first()

        if not current_user_step:
            raise HTTPException(status_code=404, detail="No step in progress")

        stmt_step = select(Step).where(Step.id == current_user_step.step_id)
        result_step = await current_context.session.execute(stmt_step)
        step = result_step.scalars().first()

        if not step:
            raise HTTPException(status_code=404, detail="Step not found")

        logger.info(f"Getting questions for step_id={step.id}, step.index={step.index}")

        questions = await service.get_current_step_questions(current_context.user.id)
        logger.info(f"Retrieved {len(questions)} questions: {questions}")

        question_items = []
        for q in questions:
            try:
                if not isinstance(q, dict):
                    logger.error(f"Question is not a dict: {q}, type: {type(q)}")
                    continue
                if "id" not in q or "text" not in q:
                    logger.error(f"Question missing id or text: {q}")
                    continue
                question_items.append(StepQuestionItem(id=int(q["id"]), text=str(q["text"])))
            except (KeyError, TypeError, ValueError) as e:
                logger.error(f"Error converting question to StepQuestionItem: {q}, error: {e}")
                continue

        if step.index is None:
            logger.warning(f"Step {step.id} has None index, defaulting to 0")
            step_number = 0
        else:
            try:
                step_number = int(step.index)
            except (ValueError, TypeError) as e:
                logger.error(f"Error converting step.index to int: {step.index}, error: {e}")
                step_number = 0

        if step.id is None:
            logger.error(f"Step has None id")
            raise HTTPException(status_code=500, detail="Step has no id")
        try:
            step_id_int = int(step.id)
        except (ValueError, TypeError) as e:
            logger.error(f"Error converting step.id to int: {step.id}, error: {e}")
            raise HTTPException(status_code=500, detail="Invalid step id")

        logger.info(f"Returning response: step_id={step_id_int}, step_number={step_number}, questions_count={len(question_items)}")

        questions_list = [{"id": q.id, "text": q.text} for q in question_items]

        logger.info(f"Questions list: {questions_list}")

        response_dict = {
            "step_id": step_id_int,
            "step_number": step_number,
            "questions": questions_list
        }

        logger.info(f"Returning dict: {response_dict}")
        return response_dict

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_step_questions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/steps/{step_id}/questions", response_model=StepQuestionsResponse)
async def get_step_questions(
    step_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get list of questions for a specific step by step_id"""
    from sqlalchemy import select
    from db.models import Step

    service = StepFlowService(current_context.session)

    stmt = select(Step).where(Step.id == step_id)
    result = await current_context.session.execute(stmt)
    step = result.scalars().first()

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    questions = await service.get_step_questions(step_id)

    question_items = []
    for q in questions:
        try:
            question_items.append(StepQuestionItem(id=q["id"], text=q["text"]))
        except (KeyError, TypeError) as e:
            import logging
            logging.error(f"Error converting question to StepQuestionItem: {q}, error: {e}")
            continue

    step_number = step.index if step.index is not None else 0

    return StepQuestionsResponse(
        step_id=step_id,
        step_number=step_number,
        questions=question_items
    )

@app.post("/steps/answer")
async def submit_answer(
    answer_data: AnswerRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    service = StepFlowService(current_context.session)

    success, error_message = await service.save_user_answer(
        current_context.user.id,
        answer_data.text,
        is_template_format=answer_data.is_template_format,
        skip_validation=getattr(answer_data, 'skip_validation', False)
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail=error_message or "No active question found to answer. Please call /steps/next first."
        )

    return {"status": "success", "message": "Answer saved."}

@app.post("/steps/draft", response_model=DraftResponse)
async def save_draft(
    draft_data: DraftRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Save draft answer in Tail.payload without closing Tail"""
    import logging
    logger = logging.getLogger(__name__)

    service = StepFlowService(current_context.session)
    logger.info(f"Saving draft for user {current_context.user.id}, text length: {len(draft_data.draft_text)}")
    success = await service.save_draft(current_context.user.id, draft_data.draft_text)
    logger.info(f"Draft save result for user {current_context.user.id}: success={success}")

    if not success:
        logger.warning(f"Failed to save draft for user {current_context.user.id}: no active Tail")
        raise HTTPException(
            status_code=400,
            detail="No active question found to save draft."
        )

    return DraftResponse(success=True, draft=draft_data.draft_text)

@app.get("/steps/draft", response_model=DraftResponse)
async def get_draft(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get draft from active Tail if exists"""
    import logging
    logger = logging.getLogger(__name__)

    service = StepFlowService(current_context.session)
    draft = await service.get_active_tail_draft(current_context.user.id)

    logger.info(f"Getting draft for user {current_context.user.id}: draft={draft[:50] if draft else None}...")

    return DraftResponse(success=draft is not None, draft=draft)

@app.get("/steps/current/question-id")
async def get_current_question_id(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get question_id from active Tail if exists"""
    service = StepFlowService(current_context.session)
    question_id = await service.get_active_question_id(current_context.user.id)

    if question_id is None:
        raise HTTPException(status_code=404, detail="No active question found")

    return {"question_id": question_id}

@app.get("/steps/last-answered/question-id")
async def get_last_answered_question_id(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get question_id from the last answered question (last closed Tail)"""
    service = StepFlowService(current_context.session)
    question_id = await service.get_last_answered_question_id(current_context.user.id)

    if question_id is None:
        raise HTTPException(status_code=404, detail="No answered question found")

    return {"question_id": question_id}

@app.get("/steps/question/{question_id}/previous", response_model=PreviousAnswerResponse)
async def get_previous_answer(
    question_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get previous answer for a question if exists"""
    service = StepFlowService(current_context.session)
    answer_text = await service.get_previous_answer(current_context.user.id, question_id)

    return PreviousAnswerResponse(question_id=question_id, answer_text=answer_text)

@app.get("/steps/question/{question_id}/examples")
async def get_example_answers(
    question_id: int,
    current_context: CurrentUserContext = Depends(get_current_user),
    limit: int = 5
):
    """Get example answers for a question from other users (anonymized)"""
    service = StepFlowService(current_context.session)
    examples = await service.get_example_answers(question_id, current_context.user.id, limit)

    return {"examples": examples, "count": len(examples)}

@app.post("/steps/switch-question", response_model=StepResponse)
async def switch_to_question(
    switch_data: SwitchQuestionRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Switch to a specific question in current step"""
    service = StepFlowService(current_context.session)
    question_text = await service.switch_to_question(
        current_context.user.id,
        switch_data.question_id
    )

    if not question_text:
        raise HTTPException(
            status_code=400,
            detail="Cannot switch to this question. It may not belong to current step."
        )

    return StepResponse(message=question_text, is_completed=False)

@app.post("/steps/switch")
async def switch_step(
    switch_data: dict,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Switch to a specific step"""
    step_id = switch_data.get("step_id")
    if not step_id:
        raise HTTPException(status_code=400, detail="step_id is required")

    service = StepFlowService(current_context.session)
    from sqlalchemy import select
    from db.models import UserStep, StepProgressStatus
    stmt = select(UserStep).where(
        UserStep.user_id == current_context.user.id,
        UserStep.status == StepProgressStatus.IN_PROGRESS
    )
    result = await current_context.session.execute(stmt)
    current_user_step = result.scalars().first()
    if current_user_step:
        current_user_step.status = StepProgressStatus.NOT_STARTED

    from db.models import Step
    stmt_step = select(Step).where(Step.id == step_id)
    result_step = await current_context.session.execute(stmt_step)
    step = result_step.scalars().first()

    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    stmt_user_step = select(UserStep).where(
        UserStep.user_id == current_context.user.id,
        UserStep.step_id == step_id
    )
    result_user_step = await current_context.session.execute(stmt_user_step)
    user_step = result_user_step.scalars().first()

    if user_step:
        user_step.status = StepProgressStatus.IN_PROGRESS
    else:
        from datetime import datetime
        user_step = UserStep(
            user_id=current_context.user.id,
            step_id=step_id,
            status=StepProgressStatus.IN_PROGRESS,
            started_at=datetime.now()
        )
        current_context.session.add(user_step)

    await current_context.session.commit()

    question_text = await service.get_next_question_for_user(current_context.user.id)
    if not question_text:
        return StepResponse(message="No questions in this step.", is_completed=True)

    return StepResponse(message=question_text, is_completed=False)

@app.get("/steps/question/{question_id}")
async def get_question_detail(
    question_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get question details"""
    from sqlalchemy import select
    from db.models import Question, Step
    service = StepFlowService(current_context.session)

    stmt = select(Question).where(Question.id == question_id)
    result = await current_context.session.execute(stmt)
    question = result.scalars().first()

    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    stmt_step = select(Step).where(Step.id == question.step_id)
    result_step = await current_context.session.execute(stmt_step)
    step = result_step.scalars().first()

    stmt_count = select(Question).where(Question.step_id == question.step_id)
    result_count = await current_context.session.execute(stmt_count)
    all_questions = result_count.scalars().all()
    total_questions = len(all_questions)

    question_number = 1
    for i, q in enumerate(all_questions, 1):
        if q.id == question_id:
            question_number = i
            break

    return {
        "question_id": question_id,
        "question_text": question.text,
        "question_number": question_number,
        "total_questions": total_questions,
        "step_id": step.id if step else None,
        "step_number": step.index if step else None
    }


@app.get("/steps/settings", response_model=StepsSettingsResponse)
async def get_steps_settings(
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get current steps settings for user"""
    service = StepsSettingsService(current_context.session)
    settings = await service.get_settings(current_context.user.id)
    return StepsSettingsResponse(**settings)

@app.put("/steps/settings", response_model=StepsSettingsResponse)
async def update_steps_settings(
    settings_data: StepsSettingsUpdateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Update steps settings for user"""
    service = StepsSettingsService(current_context.session)

    try:
        settings = await service.update_settings(
            user_id=current_context.user.id,
            active_template_id=settings_data.active_template_id,
            reminders_enabled=settings_data.reminders_enabled,
            reminder_time=settings_data.reminder_time,
            reminder_days=settings_data.reminder_days
        )
        return StepsSettingsResponse(**settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))



@app.get("/profile/sections", response_model=ProfileSectionListResponse)
async def get_profile_sections(
    current_user: CurrentUserContext = Depends(get_current_user)
) -> ProfileSectionListResponse:
    """Get all profile sections (standard + user's custom)"""
    try:
        service = ProfileService(current_user.session)
        sections = await service.get_all_sections(current_user.user.id)

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Returning {len(sections)} sections for user {current_user.user.id}")
        for section in sections:
            questions_count = len(section.questions) if hasattr(section, 'questions') and section.questions else 0
            logger.info(f"Section {section.id}: {section.name}, questions count: {questions_count}")

        return ProfileSectionListResponse(sections=sections)
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_profile_sections: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/profile/sections/{section_id}", response_model=ProfileSectionDetailResponse)
async def get_section_detail(
    section_id: int,
    current_user: CurrentUserContext = Depends(get_current_user)
) -> ProfileSectionDetailResponse:
    """Get section details with questions"""
    try:
        service = ProfileService(current_user.session)
        section = await service.get_section_detail(section_id, current_user.user.id)

        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        detail_schema = ProfileSectionDetailSchema(
            id=section.id,
            name=section.name,
            icon=section.icon,
            is_custom=section.is_custom,
            user_id=section.user_id,
            order_index=section.order_index,
            created_at=section.created_at,
            updated_at=section.updated_at,
            questions=[q for q in section.questions],
            has_data=getattr(section, 'has_data', False),
        )

        return ProfileSectionDetailResponse(section=detail_schema)
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error in get_section_detail for section_id={section_id}, user_id={current_user.user.id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.get("/profile/sections/{section_id}/answers")
async def get_user_answers_for_section(
    section_id: int,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get user's answers for questions in a section"""
    service = ProfileService(current_user.session)
    answers = await service.repo.get_user_answers_for_section(current_user.user.id, section_id)

    return {
        "answers": [
            {
                "question_id": answer.question_id,
                "answer_text": answer.answer_text,
                "version": answer.version,
                "created_at": answer.created_at.isoformat() if answer.created_at else None
            }
            for answer in answers
        ]
    }


@app.post("/profile/sections/{section_id}/answer")
async def submit_profile_answer(
    section_id: int,
    answer_data: ProfileAnswerRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Save answer to a profile question and update personalized prompt"""
    service = ProfileService(current_user.session)

    if answer_data.question_id is not None:
        section = await service.get_section_detail(section_id, current_user.user.id)
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")

        question_ids = [q.id for q in section.questions]
        if answer_data.question_id not in question_ids:
            raise HTTPException(
                status_code=400,
                detail="Question does not belong to this section"
            )

        answer, next_question = await service.save_answer(
            current_user.user.id,
            answer_data.question_id,
            answer_data.answer_text
        )

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[submit_profile_answer] User {current_user.user.id}, question_id={answer_data.question_id}, "
                   f"next_question={'found' if next_question else 'None'}, "
                   f"next_question_id={next_question.id if next_question else None}, "
                   f"next_question_text={next_question.question_text[:50] if next_question else None}...")
    else:
        section_data_existing = await service.repo.get_section_data(
            current_user.user.id, section_id
        )
        if section_data_existing and section_data_existing.content:
            new_content = f"{section_data_existing.content}\n\n[Сгенерированный вопрос]\n{answer_data.answer_text}"
        else:
            new_content = f"[Сгенерированный вопрос]\n{answer_data.answer_text}"

        section_data = await service.save_free_text(
            current_user.user.id,
            section_id,
            new_content
        )
        next_question = None
        answer = None

    from services.personalization_service import update_personalized_prompt_from_all_answers
    await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)

    await current_user.session.commit()

    response = {
        "status": "success",
        "message": "Answer saved",
        "answer_id": answer.id if answer else None,
    }

    if next_question:
        if next_question.id == -1:
            response["next_question"] = {
                "id": None,
                "text": next_question.question_text,
                "is_optional": True,
                "is_generated": True
            }
        else:
            response["next_question"] = {
                "id": next_question.id,
                "text": next_question.question_text,
                "is_optional": next_question.is_optional,
                "is_generated": False
            }
    else:
        response["message"] = "Answer saved. All questions in this section are completed."

    return response


@app.post("/profile/sections/{section_id}/free-text")
async def submit_free_text(
    section_id: int,
    free_text_data: FreeTextRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Save free text to a profile section and update personalized prompt"""
    service = ProfileService(current_user.session)

    section = await service.get_section_detail(section_id, current_user.user.id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    data = await service.save_free_text(
        current_user.user.id,
        section_id,
        free_text_data.text
    )

    from services.personalization_service import update_personalized_prompt_from_all_answers
    await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)

    await current_user.session.commit()

    return {
        "status": "success",
        "message": "Free text saved",
        "data_id": data.id,
    }


@app.post("/profile/free-text")
async def submit_general_free_text(
    free_text_data: FreeTextRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    if free_text_data.section_id is not None:
        raise HTTPException(
            status_code=400,
            detail="This endpoint is for general free text only. Use /profile/sections/{section_id}/free-text for specific section."
        )

    from core.chat_service import process_profile_free_text
    import logging
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Processing free text for user {current_user.user.id}: {free_text_data.text[:100]}...")
        result = await process_profile_free_text(
            user_id=current_user.user.id,
            free_text=free_text_data.text,
            debug=True
        )

        saved_sections = result.get("saved_sections", [])
        logger.info(f"Free text processed: {len(saved_sections)} sections saved: {[s.get('section_name') for s in saved_sections]}")

        from services.personalization_service import update_personalized_prompt_from_all_answers
        await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)
        await current_user.session.commit()

        logger.info(f"Free text processing completed for user {current_user.user.id}")

        return {
            "status": result.get("status", "success"),
            "message": result.get("message", "Free text processed and distributed"),
            "saved_sections": saved_sections,
            "extracted_info": result.get("extracted_info", "")
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing free text: {str(e)}")


@app.get("/profile/free-text/history")
async def get_free_text_history(
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get all free text entries (history) for the user across all sections"""
    from sqlalchemy import select
    from db.models import ProfileSectionData, ProfileSection

    query = (
        select(
            ProfileSectionData.id,
            ProfileSectionData.section_id,
            ProfileSectionData.content,
            ProfileSectionData.subblock_name,
            ProfileSectionData.entity_type,
            ProfileSectionData.importance,
            ProfileSectionData.is_core_personality,
            ProfileSectionData.tags,
            ProfileSectionData.created_at,
            ProfileSectionData.updated_at,
            ProfileSection.name.label("section_name")
        )
        .join(ProfileSection, ProfileSectionData.section_id == ProfileSection.id)
        .where(ProfileSectionData.user_id == current_user.user.id)
        .where(ProfileSectionData.content.isnot(None))
        .where(ProfileSectionData.content != "")
        .order_by(ProfileSectionData.created_at.desc())
    )

    result = await current_user.session.execute(query)
    entries = result.all()

    history_items = []
    for entry in entries:
        content = entry.content or ""
        preview = content[:100] + "..." if len(content) > 100 else content

        history_items.append({
            "id": entry.id,
            "section_id": entry.section_id,
            "section_name": entry.section_name,
            "content": content,
            "preview": preview,
            "subblock_name": entry.subblock_name,
            "entity_type": entry.entity_type,
            "importance": entry.importance,
            "is_core_personality": entry.is_core_personality,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
        })

    return {
        "status": "success",
        "total": len(history_items),
        "entries": history_items
    }


@app.get("/profile/sections/{section_id}/history")
async def get_section_history(
    section_id: int,
    limit: Optional[int] = None,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Get history of entries for a specific section"""
    service = ProfileService(current_user.session)
    entries = await service.get_section_data_history(
        current_user.user.id,
        section_id,
        limit
    )

    return {
        "status": "success",
        "section_id": section_id,
        "total": len(entries),
        "entries": [
            {
                "id": e.id,
                "content": e.content,
                "subblock_name": e.subblock_name,
                "entity_type": e.entity_type,
                "importance": e.importance,
                "is_core_personality": e.is_core_personality,
                "tags": e.tags,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "updated_at": e.updated_at.isoformat() if e.updated_at else None
            }
            for e in entries
        ]
    }


@app.post("/profile/sections/{section_id}/data")
async def create_section_data_entry(
    section_id: int,
    data: ProfileSectionDataCreateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Create a new entry in a section (manual addition)"""
    service = ProfileService(current_user.session)

    entry = await service.save_free_text(
        user_id=current_user.user.id,
        section_id=section_id,
        text=data.content,
        subblock_name=data.subblock_name,
        entity_type=data.entity_type,
        importance=data.importance,
        is_core_personality=data.is_core_personality,
        tags=data.tags
    )

    from services.personalization_service import update_personalized_prompt_from_all_answers
    await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)

    await current_user.session.commit()

    return {
        "status": "success",
        "message": "Entry created",
        "entry": {
            "id": entry.id,
            "section_id": entry.section_id,
            "content": entry.content,
            "subblock_name": entry.subblock_name,
            "entity_type": entry.entity_type,
            "importance": entry.importance,
            "is_core_personality": entry.is_core_personality,
            "tags": entry.tags,
            "created_at": entry.created_at.isoformat() if entry.created_at else None
        }
    }


@app.put("/profile/section-data/{data_id}")
async def update_section_data_entry(
    data_id: int,
    data: ProfileSectionDataUpdateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Update an existing entry"""
    from sqlalchemy import select
    from db.models import ProfileSectionData

    query = select(ProfileSectionData).where(
        ProfileSectionData.id == data_id,
        ProfileSectionData.user_id == current_user.user.id
    )
    result = await current_user.session.execute(query)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    if data.content is not None:
        entry.content = data.content
    if data.subblock_name is not None:
        entry.subblock_name = data.subblock_name
    if data.entity_type is not None:
        entry.entity_type = data.entity_type
    if data.importance is not None:
        entry.importance = data.importance
    if data.is_core_personality is not None:
        entry.is_core_personality = data.is_core_personality
    if data.tags is not None:
        entry.tags = data.tags

    from services.personalization_service import update_personalized_prompt_from_all_answers
    await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)

    await current_user.session.flush()

    await current_user.session.refresh(entry)

    updated_at_value = entry.updated_at.isoformat() if entry.updated_at else None

    await current_user.session.commit()

    return {
        "status": "success",
        "message": "Entry updated",
        "entry": {
            "id": entry.id,
            "section_id": entry.section_id,
            "content": entry.content,
            "subblock_name": entry.subblock_name,
            "entity_type": entry.entity_type,
            "importance": entry.importance,
            "is_core_personality": entry.is_core_personality,
            "tags": entry.tags,
            "updated_at": updated_at_value
        }
    }


@app.delete("/profile/section-data/{data_id}")
async def delete_section_data_entry(
    data_id: int,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Delete an entry"""
    from sqlalchemy import select, delete
    from db.models import ProfileSectionData

    query = select(ProfileSectionData).where(
        ProfileSectionData.id == data_id,
        ProfileSectionData.user_id == current_user.user.id
    )
    result = await current_user.session.execute(query)
    entry = result.scalar_one_or_none()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    await current_user.session.execute(
        delete(ProfileSectionData).where(ProfileSectionData.id == data_id)
    )

    from services.personalization_service import update_personalized_prompt_from_all_answers
    await update_personalized_prompt_from_all_answers(current_user.session, current_user.user.id)

    await current_user.session.commit()

    return {
        "status": "success",
        "message": "Entry deleted"
    }


@app.post("/profile/sections/custom")
async def create_custom_section(
    section_data: CustomSectionRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Create a custom profile section"""
    service = ProfileService(current_user.session)

    section = await service.create_custom_section(
        current_user.user.id,
        section_data.name,
        section_data.icon
    )
    await current_user.session.commit()

    return {
        "status": "success",
        "message": "Custom section created",
        "section_id": section.id,
    }


@app.get("/profile/sections/{section_id}/summary", response_model=SectionSummaryResponse)
async def get_section_summary(
    section_id: int,
    current_user: CurrentUserContext = Depends(get_current_user)
) -> SectionSummaryResponse:
    """Get summary statistics for a section"""
    service = ProfileService(current_user.session)

    section = await service.get_section_detail(section_id, current_user.user.id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    summary = await service.get_section_summary(current_user.user.id, section_id)

    return SectionSummaryResponse(**summary)


@app.put("/profile/sections/{section_id}")
async def update_section(
    section_id: int,
    update_data: SectionUpdateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Update a custom section (only custom sections can be updated)"""
    service = ProfileService(current_user.session)

    section = await service.get_section_detail(section_id, current_user.user.id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if not section.is_custom or section.user_id != current_user.user.id:
        raise HTTPException(
            status_code=403,
            detail="Only custom sections can be updated by their owner"
        )

    updated_section = await service.update_section(
        section_id,
        update_data.name,
        update_data.icon,
        update_data.order_index
    )

    if not updated_section:
        raise HTTPException(status_code=400, detail="Failed to update section")

    return {
        "status": "success",
        "message": "Section updated",
        "section_id": updated_section.id,
    }


@app.delete("/profile/sections/{section_id}")
async def delete_section(
    section_id: int,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Delete a custom section (only custom sections can be deleted by their owner)"""
    service = ProfileService(current_user.session)

    section = await service.get_section_detail(section_id, current_user.user.id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")

    if not section.is_custom or section.user_id != current_user.user.id:
        raise HTTPException(
            status_code=403,
            detail="Only custom sections can be deleted by their owner"
        )

    deleted = await service.delete_section(section_id, current_user.user.id)

    if not deleted:
        raise HTTPException(status_code=400, detail="Failed to delete section")

    return {
        "status": "success",
        "message": "Section deleted",
        "section_id": section_id,
    }



@app.get("/steps/templates", response_model=AnswerTemplateListResponse)
async def get_templates(
    current_user: CurrentUserContext = Depends(get_current_user)
) -> AnswerTemplateListResponse:
    """Get all available templates (author + user's custom)"""
    service = TemplateService(current_user.session)
    templates = await service.get_all_templates(current_user.user.id)

    from api.schemas import AnswerTemplateSchema
    template_schemas = []
    for template in templates:
        template_schemas.append(AnswerTemplateSchema(
            id=template.id,
            user_id=template.user_id,
            name=template.name,
            template_type=template.template_type.value if hasattr(template.template_type, 'value') else str(template.template_type),
            structure=template.structure,
            created_at=template.created_at,
            updated_at=template.updated_at
        ))

    return AnswerTemplateListResponse(
        templates=template_schemas,
        active_template_id=current_user.user.active_template_id
    )


@app.post("/steps/templates")
async def create_template(
    template_data: AnswerTemplateCreateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Create a custom template"""
    service = TemplateService(current_user.session)

    template = await service.create_template(
        current_user.user.id,
        template_data.name,
        template_data.structure
    )

    return {
        "status": "success",
        "message": "Template created",
        "template_id": template.id,
    }


@app.put("/steps/templates/{template_id}")
async def update_template(
    template_id: int,
    update_data: AnswerTemplateUpdateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Update a custom template (only user's own templates)"""
    service = TemplateService(current_user.session)

    updated_template = await service.update_template(
        template_id,
        current_user.user.id,
        update_data.name,
        update_data.structure
    )

    if not updated_template:
        raise HTTPException(
            status_code=404,
            detail="Template not found or you don't have permission to update it"
        )

    return {
        "status": "success",
        "message": "Template updated",
        "template_id": updated_template.id,
    }


@app.patch("/me/template")
async def set_active_template(
    template_request: ActiveTemplateRequest,
    current_user: CurrentUserContext = Depends(get_current_user)
):
    """Set active template for user (None to reset to default)"""
    service = TemplateService(current_user.session)

    success = await service.set_active_template(
        current_user.user,
        template_request.template_id
    )

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Template not found or not available"
        )

    return {
        "status": "success",
        "message": "Active template updated",
        "template_id": template_request.template_id,
    }

@app.post("/session/context")
async def save_session_context(
    payload: dict,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Save or update session context"""
    from repositories.SessionContextRepository import SessionContextRepository
    from db.models import SessionType
    from api.schemas import SessionContextResponse

    session_context_repo = SessionContextRepository(current_context.session)

    session_type_map = {
        "STEPS": SessionType.STEPS,
        "DAY": SessionType.DAY,
        "CHAT": SessionType.CHAT
    }
    session_type_str = payload.get("session_type", "").upper()
    session_type = session_type_map.get(session_type_str)
    if not session_type:
        raise HTTPException(status_code=400, detail="Invalid session_type")

    context_data = payload.get("context_data", {})

    context = await session_context_repo.create_or_update_context(
        current_context.user.id,
        session_type,
        context_data
    )
    await current_context.session.commit()

    return SessionContextResponse(
        id=context.id,
        user_id=context.user_id,
        session_type=context.session_type.value,
        context_data=context.context_data or {},
        created_at=context.created_at.isoformat(),
        updated_at=context.updated_at.isoformat()
    )

@app.get("/session/context")
async def get_session_context(
    session_type: Optional[str] = None,
    current_context: CurrentUserContext = Depends(get_current_user)
):
    """Get active session context"""
    from repositories.SessionContextRepository import SessionContextRepository
    from db.models import SessionType
    from api.schemas import SessionContextResponse

    session_context_repo = SessionContextRepository(current_context.session)

    session_type_enum = None
    if session_type:
        session_type_map = {
            "STEPS": SessionType.STEPS,
            "DAY": SessionType.DAY,
            "CHAT": SessionType.CHAT
        }
        session_type_enum = session_type_map.get(session_type.upper())

    context = await session_context_repo.get_active_context(
        current_context.user.id,
        session_type_enum
    )

    if not context:
        return None

    return SessionContextResponse(
        id=context.id,
        user_id=context.user_id,
        session_type=context.session_type.value,
        context_data=context.context_data or {},
        created_at=context.created_at.isoformat(),
        updated_at=context.updated_at.isoformat()
    )



@app.get("/user/state", response_model=SessionStateResponse)
async def get_user_state(
    current_context: CurrentUserContext = Depends(get_current_user)
) -> SessionStateResponse:
    """Get operational state (SessionState) for current user"""
    repo = SessionStateRepository(current_context.session)
    state = await repo.get_by_user_id(current_context.user.id)

    if not state:
        raise HTTPException(status_code=404, detail="SessionState not found")

    return SessionStateResponse(
        id=state.id,
        user_id=state.user_id,
        recent_messages=state.recent_messages,
        daily_snapshot=state.daily_snapshot,
        active_blocks=state.active_blocks,
        pending_topics=state.pending_topics,
        group_signals=state.group_signals,
        created_at=state.created_at,
        updated_at=state.updated_at
    )


@app.post("/user/state", response_model=SessionStateResponse)
async def update_user_state(
    payload: SessionStateUpdateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> SessionStateResponse:
    """Update operational state (SessionState) for current user"""
    repo = SessionStateRepository(current_context.session)
    state = await repo.create_or_update(
        user_id=current_context.user.id,
        recent_messages=payload.recent_messages,
        daily_snapshot=payload.daily_snapshot,
        active_blocks=payload.active_blocks,
        pending_topics=payload.pending_topics,
        group_signals=payload.group_signals,
    )
    await current_context.session.commit()
    await current_context.session.refresh(state)

    return SessionStateResponse(
        id=state.id,
        user_id=state.user_id,
        recent_messages=state.recent_messages,
        daily_snapshot=state.daily_snapshot,
        active_blocks=state.active_blocks,
        pending_topics=state.pending_topics,
        group_signals=state.group_signals,
        created_at=state.created_at,
        updated_at=state.updated_at
    )


@app.get("/user/frames", response_model=FrameTrackingResponse)
async def get_user_frames(
    current_context: CurrentUserContext = Depends(get_current_user)
) -> FrameTrackingResponse:
    """Get frame tracking (FrameTracking) for current user"""
    repo = FrameTrackingRepository(current_context.session)
    tracking = await repo.get_by_user_id(current_context.user.id)

    if not tracking:
        raise HTTPException(status_code=404, detail="FrameTracking not found")

    return FrameTrackingResponse(
        id=tracking.id,
        user_id=tracking.user_id,
        confirmed=tracking.confirmed,
        candidates=tracking.candidates,
        tracking=tracking.tracking,
        archetypes=tracking.archetypes,
        meta_flags=tracking.meta_flags,
        created_at=tracking.created_at,
        updated_at=tracking.updated_at
    )


@app.post("/user/frames", response_model=FrameTrackingResponse)
async def update_user_frames(
    payload: FrameTrackingUpdateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> FrameTrackingResponse:
    """Update frame tracking (FrameTracking) for current user"""
    repo = FrameTrackingRepository(current_context.session)
    tracking = await repo.create_or_update(
        user_id=current_context.user.id,
        confirmed=payload.confirmed,
        candidates=payload.candidates,
        tracking=payload.tracking,
        archetypes=payload.archetypes,
        meta_flags=payload.meta_flags,
    )
    await current_context.session.commit()
    await current_context.session.refresh(tracking)

    return FrameTrackingResponse(
        id=tracking.id,
        user_id=tracking.user_id,
        confirmed=tracking.confirmed,
        candidates=tracking.candidates,
        tracking=tracking.tracking,
        archetypes=tracking.archetypes,
        meta_flags=tracking.meta_flags,
        created_at=tracking.created_at,
        updated_at=tracking.updated_at
    )


@app.get("/user/qa-status", response_model=QAStatusResponse)
async def get_user_qa_status(
    current_context: CurrentUserContext = Depends(get_current_user)
) -> QAStatusResponse:
    """Get QA status for current user"""
    repo = QAStatusRepository(current_context.session)
    qa_status = await repo.get_by_user_id(current_context.user.id)

    if not qa_status:
        raise HTTPException(status_code=404, detail="QAStatus not found")

    return QAStatusResponse(
        id=qa_status.id,
        user_id=qa_status.user_id,
        last_prompt_included=qa_status.last_prompt_included,
        trace_ok=qa_status.trace_ok,
        open_threads=qa_status.open_threads,
        rebuild_required=qa_status.rebuild_required,
        created_at=qa_status.created_at,
        updated_at=qa_status.updated_at
    )


@app.post("/user/qa-status", response_model=QAStatusResponse)
async def update_user_qa_status(
    payload: QAStatusUpdateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> QAStatusResponse:
    """Update QA status for current user"""
    repo = QAStatusRepository(current_context.session)
    qa_status = await repo.create_or_update(
        user_id=current_context.user.id,
        last_prompt_included=payload.last_prompt_included,
        trace_ok=payload.trace_ok,
        open_threads=payload.open_threads,
        rebuild_required=payload.rebuild_required,
    )
    await current_context.session.commit()
    await current_context.session.refresh(qa_status)

    return QAStatusResponse(
        id=qa_status.id,
        user_id=qa_status.user_id,
        last_prompt_included=qa_status.last_prompt_included,
        trace_ok=qa_status.trace_ok,
        open_threads=qa_status.open_threads,
        rebuild_required=qa_status.rebuild_required,
        created_at=qa_status.created_at,
        updated_at=qa_status.updated_at
    )


@app.get("/user/tracker-summary", response_model=TrackerSummaryResponse)
async def get_user_tracker_summary(
    date: Optional[date_class] = None,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TrackerSummaryResponse:
    """Get tracker summary for current user (by date or latest)"""
    repo = TrackerSummaryRepository(current_context.session)

    if date:
        summary = await repo.get_by_user_and_date(current_context.user.id, date)
    else:
        summary = await repo.get_latest(current_context.user.id)

    if not summary:
        raise HTTPException(status_code=404, detail="TrackerSummary not found")

    return TrackerSummaryResponse(
        id=summary.id,
        user_id=summary.user_id,
        thinking=summary.thinking,
        feeling=summary.feeling,
        behavior=summary.behavior,
        relationships=summary.relationships,
        health=summary.health,
        date=summary.date,
        created_at=summary.created_at,
        updated_at=summary.updated_at
    )


@app.post("/user/tracker-summary", response_model=TrackerSummaryResponse)
async def create_or_update_tracker_summary(
    payload: TrackerSummaryCreateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TrackerSummaryResponse:
    """Create or update tracker summary for current user"""
    repo = TrackerSummaryRepository(current_context.session)
    summary = await repo.create_or_update(
        user_id=current_context.user.id,
        thinking=payload.thinking,
        feeling=payload.feeling,
        behavior=payload.behavior,
        relationships=payload.relationships,
        health=payload.health,
        summary_date=payload.date,
    )
    await current_context.session.commit()
    await current_context.session.refresh(summary)

    return TrackerSummaryResponse(
        id=summary.id,
        user_id=summary.user_id,
        thinking=summary.thinking,
        feeling=summary.feeling,
        behavior=summary.behavior,
        relationships=summary.relationships,
        health=summary.health,
        date=summary.date,
        created_at=summary.created_at,
        updated_at=summary.updated_at
    )


@app.get("/user/meta", response_model=UserMetaResponse)
async def get_user_meta(
    current_context: CurrentUserContext = Depends(get_current_user)
) -> UserMetaResponse:
    """Get user metadata for current user"""
    repo = UserMetaRepository(current_context.session)
    meta = await repo.get_by_user_id(current_context.user.id)

    if not meta:
        raise HTTPException(status_code=404, detail="UserMeta not found")

    return UserMetaResponse(
        id=meta.id,
        user_id=meta.user_id,
        metasloy_signals=meta.metasloy_signals,
        prompt_revision_history=meta.prompt_revision_history,
        time_zone=meta.time_zone,
        language=meta.language,
        data_flags=meta.data_flags,
        created_at=meta.created_at,
        updated_at=meta.updated_at
    )


@app.put("/user/meta", response_model=UserMetaResponse)
async def update_user_meta(
    payload: UserMetaUpdateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> UserMetaResponse:
    """Update user metadata for current user"""
    repo = UserMetaRepository(current_context.session)
    meta = await repo.create_or_update(
        user_id=current_context.user.id,
        metasloy_signals=payload.metasloy_signals,
        prompt_revision_history=payload.prompt_revision_history,
        time_zone=payload.time_zone,
        language=payload.language,
        data_flags=payload.data_flags,
    )
    await current_context.session.commit()
    await current_context.session.refresh(meta)

    return UserMetaResponse(
        id=meta.id,
        user_id=meta.user_id,
        metasloy_signals=meta.metasloy_signals,
        prompt_revision_history=meta.prompt_revision_history,
        time_zone=meta.time_zone,
        language=meta.language,
        data_flags=meta.data_flags,
        created_at=meta.created_at,
        updated_at=meta.updated_at
    )



@app.post("/template-progress/start", response_model=TemplateProgressResponse)
async def start_template_progress(
    payload: TemplateProgressStartRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TemplateProgressResponse:
    """
    service = TemplateService(current_context.session)
    result = await service.start_template_filling(
        user_id=current_context.user.id,
        step_id=payload.step_id,
        question_id=payload.question_id
    )
    await current_context.session.commit()

    field_info = None
    if result.get("field_info"):
        field_info = TemplateFieldInfo(**result["field_info"])

    return TemplateProgressResponse(
        progress_id=result.get("progress_id"),
        status=result.get("status", "IN_PROGRESS"),
        current_field=result.get("current_field"),
        current_situation=result.get("current_situation"),
        field_info=field_info,
        progress_summary=result.get("progress_summary"),
        is_resumed=result.get("is_resumed", False),
        is_complete=result.get("is_complete", False)
    )


@app.post("/template-progress/submit", response_model=TemplateFieldSubmitResponse)
async def submit_template_field(
    payload: TemplateFieldSubmitRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TemplateFieldSubmitResponse:
    """
    service = TemplateService(current_context.session)
    result = await service.submit_field_value(
        user_id=current_context.user.id,
        step_id=payload.step_id,
        question_id=payload.question_id,
        value=payload.value
    )
    await current_context.session.commit()

    field_info = None
    if result.get("field_info"):
        field_info = TemplateFieldInfo(**result["field_info"])

    return TemplateFieldSubmitResponse(
        success=result.get("success", False),
        error=result.get("error"),
        validation_error=result.get("validation_error", False),
        next_field=result.get("next_field"),
        field_info=field_info,
        current_situation=result.get("current_situation"),
        is_situation_complete=result.get("is_situation_complete", False),
        is_all_situations_complete=result.get("is_all_situations_complete", False),
        ready_for_conclusion=result.get("ready_for_conclusion", False),
        is_complete=result.get("is_complete", False),
        progress_summary=result.get("progress_summary"),
        formatted_answer=result.get("formatted_answer")
    )


@app.post("/template-progress/pause", response_model=TemplatePauseResponse)
async def pause_template_progress(
    payload: TemplatePauseRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TemplatePauseResponse:
    """
    service = TemplateService(current_context.session)
    result = await service.pause_template_filling(
        user_id=current_context.user.id,
        step_id=payload.step_id,
        question_id=payload.question_id
    )
    await current_context.session.commit()

    return TemplatePauseResponse(
        success=result.get("success", False),
        error=result.get("error"),
        status=result.get("status"),
        progress_summary=result.get("progress_summary"),
        resume_info=result.get("resume_info")
    )


@app.get("/template-progress/current", response_model=TemplateProgressResponse)
async def get_current_template_progress(
    step_id: int,
    question_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TemplateProgressResponse:
    """
    service = TemplateService(current_context.session)
    result = await service.get_template_progress(
        user_id=current_context.user.id,
        step_id=step_id,
        question_id=question_id
    )

    if not result:
        raise HTTPException(status_code=404, detail="Template progress not found")

    field_info = None
    if result.get("field_info"):
        field_info = TemplateFieldInfo(**result["field_info"])

    return TemplateProgressResponse(
        progress_id=result.get("progress_id"),
        status=result.get("status", "IN_PROGRESS"),
        current_field=result.get("current_field"),
        current_situation=result.get("current_situation"),
        field_info=field_info,
        progress_summary=result.get("progress_summary"),
        is_complete=result.get("is_complete", False),
        situations=result.get("situations"),
        conclusion=result.get("conclusion")
    )


@app.get("/template-progress/fields-info", response_model=TemplateFieldsInfoResponse)
async def get_template_fields_info(
    current_context: CurrentUserContext = Depends(get_current_user)
) -> TemplateFieldsInfoResponse:
    """Get template fields information."""
    service = TemplateService(current_context.session)

    return TemplateFieldsInfoResponse(
        fields=service.get_template_fields_info(),
        min_situations=service.get_min_situations()
    )


@app.delete("/template-progress/cancel")
async def cancel_template_progress(
    step_id: int,
    question_id: int,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> dict:
    """Cancel template progress."""
    service = TemplateService(current_context.session)
    result = await service.cancel_template_filling(
        user_id=current_context.user.id,
        step_id=step_id,
        question_id=question_id
    )
    await current_context.session.commit()

    return result



from services.step10_service import Step10Service


@app.post("/step10/start", response_model=Step10StartResponse)
async def start_step10_analysis(
    payload: Step10StartRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> Step10StartResponse:
    """Start step 10 daily analysis."""
    service = Step10Service(current_context.session)
    result = await service.start_analysis(
        user_id=current_context.user.id,
        analysis_date=payload.analysis_date
    )
    await current_context.session.commit()

    if not result.get("question_data"):
        raise HTTPException(
            status_code=500,
            detail="Не удалось загрузить вопросы для самоанализа. Попробуй позже."
        )

    question_data = Step10QuestionData(
        number=result["question_data"]["number"],
        text=result["question_data"]["text"],
        subtext=result["question_data"].get("subtext")
    )

    return Step10StartResponse(
        analysis_id=result["analysis_id"],
        status=result["status"],
        current_question=result["current_question"],
        question_data=question_data,
        progress_summary=result["progress_summary"],
        is_resumed=result["is_resumed"],
        is_complete=result["is_complete"]
    )


@app.post("/step10/submit", response_model=Step10SubmitAnswerResponse)
async def submit_step10_answer(
    payload: Step10SubmitAnswerRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> Step10SubmitAnswerResponse:
    """Submit answer for step 10 daily analysis."""
    service = Step10Service(current_context.session)
    result = await service.submit_answer(
        user_id=current_context.user.id,
        question_number=payload.question_number,
        answer=payload.answer,
        analysis_date=payload.analysis_date
    )
    await current_context.session.commit()

    if not result.get("success"):
        return Step10SubmitAnswerResponse(
            success=False,
            error=result.get("error"),
            is_complete=False,
            progress_summary=""
        )

    next_question_data = None
    if result.get("next_question_data"):
        qd = result["next_question_data"]
        next_question_data = Step10QuestionData(
            number=qd["number"],
            text=qd["text"],
            subtext=qd.get("subtext")
        )

    return Step10SubmitAnswerResponse(
        success=True,
        next_question=result.get("next_question"),
        next_question_data=next_question_data,
        is_complete=result.get("is_complete", False),
        progress_summary=result.get("progress_summary", "")
    )


@app.post("/step10/pause", response_model=Step10PauseResponse)
async def pause_step10_analysis(
    payload: Step10PauseRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> Step10PauseResponse:
    """Pause step 10 daily analysis."""
    service = Step10Service(current_context.session)
    result = await service.pause_analysis(
        user_id=current_context.user.id,
        analysis_date=payload.analysis_date
    )
    await current_context.session.commit()

    if not result.get("success"):
        return Step10PauseResponse(
            success=False,
            error=result.get("error"),
            status="",
            progress_summary="",
            current_question=0,
            resume_info=""
        )

    question_data = None
    if result.get("question_data"):
        qd = result["question_data"]
        question_data = Step10QuestionData(
            number=qd["number"],
            text=qd["text"],
            subtext=qd.get("subtext")
        )

    return Step10PauseResponse(
        success=True,
        status=result.get("status", "PAUSED"),
        progress_summary=result.get("progress_summary", ""),
        current_question=result.get("current_question", 0),
        question_data=question_data,
        resume_info=result.get("resume_info", "")
    )


@app.get("/step10/progress", response_model=Step10ProgressResponse)
async def get_step10_progress(
    analysis_date: Optional[date] = None,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> Optional[Step10ProgressResponse]:
    """Get step 10 daily analysis progress."""
    service = Step10Service(current_context.session)
    result = await service.get_analysis_progress(
        user_id=current_context.user.id,
        analysis_date=analysis_date
    )

    if not result:
        return None

    question_data = None
    if result.get("question_data"):
        qd = result["question_data"]
        question_data = Step10QuestionData(
            number=qd["number"],
            text=qd["text"],
            subtext=qd.get("subtext")
        )

    return Step10ProgressResponse(
        analysis_id=result["analysis_id"],
        status=result["status"],
        current_question=result["current_question"],
        question_data=question_data,
        progress_summary=result["progress_summary"],
        answers=result.get("answers"),
        is_complete=result.get("is_complete", False)
    )



@app.post("/gratitudes", response_model=GratitudeItem)
async def create_gratitude(
    payload: GratitudeCreateRequest,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> GratitudeItem:
    """Создать новую благодарность"""
    repo = GratitudeRepository(current_context.session)
    gratitude = await repo.create(
        user_id=current_context.user.id,
        text=payload.text
    )

    return GratitudeItem(
        id=gratitude.id,
        text=gratitude.text,
        created_at=gratitude.created_at
    )


@app.get("/gratitudes", response_model=GratitudeListResponse)
async def get_gratitudes(
    page: int = 1,
    page_size: int = 20,
    current_context: CurrentUserContext = Depends(get_current_user)
) -> GratitudeListResponse:
    """Получить список благодарностей пользователя"""
    repo = GratitudeRepository(current_context.session)

    offset = (page - 1) * page_size
    gratitudes = await repo.get_user_gratitudes(
        user_id=current_context.user.id,
        limit=page_size,
        offset=offset
    )

    total = await repo.get_count(current_context.user.id)

    items = [
        GratitudeItem(
            id=g.id,
            text=g.text,
            created_at=g.created_at
        )
        for g in gratitudes
    ]

    return GratitudeListResponse(
        gratitudes=items,
        total=total,
        page=page,
        page_size=page_size
    )

