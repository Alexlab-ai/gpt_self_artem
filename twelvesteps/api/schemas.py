from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Dict, List

from pydantic import BaseModel, Field

from db.models import User as UserModel


class ChatRequest(BaseModel):
    telegram_id: str
    message: Optional[str] = None
    debug: bool = False


class ChatResponse(BaseModel):
    reply: str
    log : Optional[Log]

class Log(BaseModel):
    classification_result: str
    blocks_used: str
    plan : str
    prompt_changes : Optional[str]



class TelegramAuthRequest(BaseModel):
    telegram_id: str = Field(..., min_length=1)
    username: Optional[str] = None
    first_name: Optional[str] = None


class UserSchema(BaseModel):
    id: int
    telegram_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    display_name: Optional[str] = None
    role: Optional[str] = None
    program_experience: Optional[str] = None
    sobriety_date: Optional[date] = None
    personal_prompt: Optional[str] = None
    relapse_dates: Optional[List[str]] = None
    sponsor_ids: Optional[List[int]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    last_active: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TelegramAuthResponse(BaseModel):
    user: UserSchema
    is_new: bool
    access_token: str


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None)
    program_experience: Optional[str] = Field(default=None)
    sobriety_date: Optional[date] = Field(default=None)

class SosRequest(BaseModel):
    telegram_id: int | str

class SosResponse(BaseModel):
    reply: str

class SosChatRequest(BaseModel):
    """Request for SOS chat dialog"""
    help_type: Optional[str] = Field(default=None, description="Type of help: question, memory, formulation, support, custom")
    custom_text: Optional[str] = Field(default=None, description="Custom help description if help_type is 'custom'")
    message: Optional[str] = Field(default=None, description="User message in the chat dialog")
    conversation_history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Previous messages in the conversation")

class SosChatResponse(BaseModel):
    """Response from SOS chat dialog"""
    reply: str
    is_finished: bool = Field(default=False, description="Whether the conversation is finished and should ask about saving draft")
    conversation_history: List[Dict[str, str]] = Field(default_factory=list, description="Updated conversation history")

class OpenStepQuestion(BaseModel):
    step_id: int
    question_id: int

class AnswerRequest(BaseModel):
    text: str
    is_template_format: bool = Field(default=False, description="Whether answer is in template JSON format")
    skip_validation: bool = Field(default=False, description="Skip minimum length validation (for intentional short answers)")

class StepResponse(BaseModel):
    message: str
    is_completed: bool = False

class StepInfoResponse(BaseModel):
    """Current step information"""
    step_id: Optional[int] = None
    step_number: Optional[int] = None
    step_title: Optional[str] = None
    step_description: Optional[str] = None
    total_steps: Optional[int] = None
    answered_questions: Optional[int] = None
    total_questions: Optional[int] = None
    status: Optional[str] = None

class StepListResponse(BaseModel):
    """List of all steps"""
    steps: list[dict] = Field(default_factory=list)

class StepQuestionItem(BaseModel):
    """Single question item"""
    id: int
    text: str

class StepQuestionsResponse(BaseModel):
    """List of questions for a step"""
    step_id: int
    step_number: int
    questions: list[StepQuestionItem] = Field(default_factory=list)

class DraftRequest(BaseModel):
    """Request to save draft"""
    draft_text: str

class DraftResponse(BaseModel):
    """Response for draft operations"""
    success: bool
    draft: Optional[str] = None

class PreviousAnswerResponse(BaseModel):
    """Response with previous answer"""
    question_id: int
    answer_text: Optional[str] = None

class SwitchQuestionRequest(BaseModel):
    """Request to switch to a specific question"""
    question_id: int

class StepsSettingsResponse(BaseModel):
    """Response with current steps settings"""
    active_template_id: Optional[int] = None
    active_template_name: Optional[str] = None
    reminders_enabled: bool = Field(default=False)
    reminder_time: Optional[str] = Field(default=None, description="Time in HH:MM format")
    reminder_days: Optional[List[int]] = Field(default_factory=list, description="Days of week (0-6, Monday=0)")

class StepsSettingsUpdateRequest(BaseModel):
    """Request to update steps settings"""
    active_template_id: Optional[int] = None
    reminders_enabled: Optional[bool] = None
    reminder_time: Optional[str] = Field(default=None, description="Time in HH:MM format")
    reminder_days: Optional[List[int]] = Field(default=None, description="Days of week (0-6, Monday=0)")

class StatusTail(BaseModel):
    id: int
    type: str
    payload: Optional[dict[str, Any]] = None


class StatusResponse(BaseModel):
    current_step: Optional[int] = None
    current_step_status: Optional[str] = None
    open_step_question: Optional[OpenStepQuestion] = None
    tails: list[StatusTail] = Field(default_factory=list)


def build_user_schema(user: UserModel) -> UserSchema:
    role_value = user.user_role.name.upper() if user.user_role else None
    return UserSchema(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        display_name=user.display_name,
        role=role_value,
        program_experience=user.program_experience,
        sobriety_date=user.sobriety_date,
        personal_prompt=user.personal_prompt,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )



class ProfileQuestionSchema(BaseModel):
    id: int
    section_id: int
    question_text: str
    order_index: int
    is_optional: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileAnswerSchema(BaseModel):
    id: int
    user_id: int
    question_id: int
    answer_text: str
    version: int
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileSectionDataSchema(BaseModel):
    id: int
    user_id: int
    section_id: int
    content: Optional[str] = None
    subblock_name: Optional[str] = None
    entity_type: Optional[str] = None
    importance: Optional[float] = None
    is_core_personality: bool = False
    tags: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfileSectionDataCreateRequest(BaseModel):
    section_id: Optional[int] = None
    content: str
    subblock_name: Optional[str] = None
    entity_type: Optional[str] = None
    importance: Optional[float] = 1.0
    is_core_personality: bool = False
    tags: Optional[str] = None


class ProfileSectionDataUpdateRequest(BaseModel):
    content: Optional[str] = None
    subblock_name: Optional[str] = None
    entity_type: Optional[str] = None
    importance: Optional[float] = None
    is_core_personality: Optional[bool] = None
    tags: Optional[str] = None


class ProfileSectionSchema(BaseModel):
    id: int
    name: str
    icon: Optional[str] = None
    is_custom: bool
    user_id: Optional[int] = None
    order_index: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfileSectionDetailSchema(ProfileSectionSchema):
    questions: list[ProfileQuestionSchema] = Field(default_factory=list)
    has_data: bool = False

    class Config:
        from_attributes = True


class ProfileSectionListResponse(BaseModel):
    sections: list[ProfileSectionSchema]


class ProfileSectionDetailResponse(BaseModel):
    section: ProfileSectionDetailSchema


class ProfileAnswerRequest(BaseModel):
    question_id: Optional[int] = None
    answer_text: str = Field(..., min_length=1)


class FreeTextRequest(BaseModel):
    section_id: Optional[int] = None
    text: str = Field(..., min_length=1)


class CustomSectionRequest(BaseModel):
    name: str = Field(..., min_length=1)
    icon: Optional[str] = None


class SectionUpdateRequest(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    order_index: Optional[int] = None


class SectionSummaryResponse(BaseModel):
    section_id: int
    section_name: str
    questions_count: int
    answers_count: int
    last_updated: Optional[datetime] = None



class AnswerTemplateSchema(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    template_type: str
    structure: dict
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm to handle enum serialization"""
        data = {
            "id": obj.id,
            "user_id": obj.user_id,
            "name": obj.name,
            "template_type": obj.template_type.value if hasattr(obj.template_type, 'value') else str(obj.template_type),
            "structure": obj.structure,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at
        }
        return cls(**data)

    class Config:
        from_attributes = True


class AnswerTemplateListResponse(BaseModel):
    templates: list[AnswerTemplateSchema]
    active_template_id: Optional[int] = None


class AnswerTemplateCreateRequest(BaseModel):
    name: str = Field(..., min_length=1)
    structure: dict = Field(..., description="JSON structure of the template")


class AnswerTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    structure: Optional[dict] = None


class ActiveTemplateRequest(BaseModel):
    template_id: Optional[int] = None



class TemplateProgressStartRequest(BaseModel):
    """Запрос на начало/продолжение заполнения шаблона"""
    step_id: int
    question_id: int


class TemplateFieldInfo(BaseModel):
    """Информация о поле шаблона"""
    key: str
    name: str
    description: Optional[str] = None
    min_items: Optional[int] = None
    situation_number: Optional[int] = None
    is_conclusion: bool = False
    is_complete: bool = False


class TemplateProgressResponse(BaseModel):
    """Ответ с информацией о прогрессе шаблона"""
    progress_id: Optional[int] = None
    status: str
    current_field: Optional[str] = None
    current_situation: Optional[int] = None
    field_info: Optional[TemplateFieldInfo] = None
    progress_summary: Optional[str] = None
    is_resumed: bool = False
    is_complete: bool = False
    situations: Optional[List[Dict[str, Any]]] = None
    conclusion: Optional[str] = None


class TemplateFieldSubmitRequest(BaseModel):
    """Запрос на сохранение значения поля"""
    step_id: int
    question_id: int
    value: str


class TemplateFieldSubmitResponse(BaseModel):
    """Ответ после сохранения поля"""
    success: bool
    error: Optional[str] = None
    validation_error: bool = False
    next_field: Optional[str] = None
    field_info: Optional[TemplateFieldInfo] = None
    current_situation: Optional[int] = None
    is_situation_complete: bool = False
    is_all_situations_complete: bool = False
    ready_for_conclusion: bool = False
    is_complete: bool = False
    progress_summary: Optional[str] = None
    formatted_answer: Optional[str] = None


class TemplatePauseRequest(BaseModel):
    """Запрос на паузу заполнения шаблона"""
    step_id: int
    question_id: int


class TemplatePauseResponse(BaseModel):
    """Ответ на паузу"""
    success: bool
    error: Optional[str] = None
    status: Optional[str] = None
    progress_summary: Optional[str] = None
    resume_info: Optional[str] = None


class TemplateFieldsInfoResponse(BaseModel):
    """Информация о всех полях шаблона"""
    fields: List[Dict[str, Any]]
    min_situations: int



class Step10QuestionData(BaseModel):
    """Данные вопроса для самоанализа"""
    number: int
    text: str
    subtext: Optional[str] = None


class Step10StartRequest(BaseModel):
    """Запрос на начало самоанализа"""
    analysis_date: Optional[date] = None


class Step10StartResponse(BaseModel):
    """Ответ при начале самоанализа"""
    analysis_id: int
    status: str
    current_question: int
    question_data: Step10QuestionData
    progress_summary: str
    is_resumed: bool
    is_complete: bool


class Step10SubmitAnswerRequest(BaseModel):
    """Запрос на сохранение ответа"""
    question_number: int
    answer: str
    analysis_date: Optional[date] = None


class Step10SubmitAnswerResponse(BaseModel):
    """Ответ при сохранении ответа"""
    success: bool
    error: Optional[str] = None
    next_question: Optional[int] = None
    next_question_data: Optional[Step10QuestionData] = None
    is_complete: bool
    progress_summary: str


class Step10PauseRequest(BaseModel):
    """Запрос на паузу"""
    analysis_date: Optional[date] = None


class Step10PauseResponse(BaseModel):
    """Ответ при паузе"""
    success: bool
    error: Optional[str] = None
    status: str
    progress_summary: str
    current_question: int
    question_data: Optional[Step10QuestionData] = None
    resume_info: str


class Step10ProgressResponse(BaseModel):
    """Текущий прогресс самоанализа"""
    analysis_id: int
    status: str
    current_question: int
    question_data: Optional[Step10QuestionData] = None
    progress_summary: str
    answers: Optional[List[Dict[str, Any]]] = None
    is_complete: bool



class SessionContextResponse(BaseModel):
    id: int
    user_id: int
    session_type: str
    context_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class SessionStateResponse(BaseModel):
    id: int
    user_id: int
    recent_messages: Optional[List[Dict[str, Any]]] = None
    daily_snapshot: Optional[Dict[str, Any]] = None
    active_blocks: Optional[List[str]] = None
    pending_topics: Optional[List[str]] = None
    group_signals: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class SessionStateUpdateRequest(BaseModel):
    recent_messages: Optional[List[Dict[str, Any]]] = None
    daily_snapshot: Optional[Dict[str, Any]] = None
    active_blocks: Optional[List[str]] = None
    pending_topics: Optional[List[str]] = None
    group_signals: Optional[List[str]] = None


class FrameTrackingResponse(BaseModel):
    id: int
    user_id: int
    confirmed: Optional[List[Dict[str, Any]]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    tracking: Optional[Dict[str, Any]] = None
    archetypes: Optional[List[str]] = None
    meta_flags: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime


class FrameTrackingUpdateRequest(BaseModel):
    confirmed: Optional[List[Dict[str, Any]]] = None
    candidates: Optional[List[Dict[str, Any]]] = None
    tracking: Optional[Dict[str, Any]] = None
    archetypes: Optional[List[str]] = None
    meta_flags: Optional[List[str]] = None


class QAStatusResponse(BaseModel):
    id: int
    user_id: int
    last_prompt_included: Optional[bool] = None
    trace_ok: Optional[bool] = None
    open_threads: Optional[int] = None
    rebuild_required: Optional[bool] = None
    created_at: datetime
    updated_at: datetime


class QAStatusUpdateRequest(BaseModel):
    last_prompt_included: Optional[bool] = None
    trace_ok: Optional[bool] = None
    open_threads: Optional[int] = None
    rebuild_required: Optional[bool] = None


class TrackerSummaryResponse(BaseModel):
    id: int
    user_id: int
    thinking: Optional[List[str]] = None
    feeling: Optional[List[str]] = None
    behavior: Optional[List[str]] = None
    relationships: Optional[List[str]] = None
    health: Optional[List[str]] = None
    date: date
    created_at: datetime
    updated_at: datetime


class TrackerSummaryCreateRequest(BaseModel):
    thinking: Optional[List[str]] = None
    feeling: Optional[List[str]] = None
    behavior: Optional[List[str]] = None
    relationships: Optional[List[str]] = None
    health: Optional[List[str]] = None
    date: Optional[date] = None


class UserMetaResponse(BaseModel):
    id: int
    user_id: int
    metasloy_signals: Optional[List[str]] = None
    prompt_revision_history: Optional[int] = None
    time_zone: Optional[str] = None
    language: Optional[str] = None
    data_flags: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class UserMetaUpdateRequest(BaseModel):
    metasloy_signals: Optional[List[str]] = None
    prompt_revision_history: Optional[int] = None
    time_zone: Optional[str] = None
    language: Optional[str] = None
    data_flags: Optional[Dict[str, Any]] = None



class GratitudeCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)


class GratitudeItem(BaseModel):
    id: int
    text: str
    created_at: datetime


class GratitudeListResponse(BaseModel):
    gratitudes: List[GratitudeItem]
    total: int
    page: int = 1
    page_size: int = 20
