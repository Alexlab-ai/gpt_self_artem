from datetime import datetime, date
from typing import Optional, List
from enum import Enum

from sqlalchemy import (
    CHAR,
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLEnum

from db.database import Base


class UserRole(Enum):
    admin = "admin"
    dependent = "dependent"
    sponsor = "sponsor"

class SenderRole(Enum):
    assistant = "assistant"
    user = "user"

class StepProgressStatus(Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class TailType(Enum):
    STEP_QUESTION = "STEP_QUESTION"
    STEP_COMPLETION = "STEP_COMPLETION"

class SessionType(Enum):
    STEPS = "STEPS"
    DAY = "DAY"
    CHAT = "CHAT"

class TemplateType(Enum):
    AUTHOR = "AUTHOR"
    CUSTOM = "CUSTOM"


blocks_frames = Table(
    "blocks_frames",
    Base.metadata,
    Column("block_id", ForeignKey("blocks.id", ondelete="CASCADE"), primary_key=True),
    Column("frame_id", ForeignKey("frames.id", ondelete="CASCADE"), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True, index=True)
    api_key: Mapped[Optional[str]] = mapped_column(CHAR(128), unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_role: Mapped[Optional[UserRole]] = mapped_column(
        SQLEnum(UserRole, name="user_role_enum", create_type=True),
        default=UserRole.dependent,
        server_default=UserRole.dependent.value,
    )
    personal_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    program_experience: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sobriety_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    active_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("answer_templates.id", ondelete="SET NULL"), nullable=True, index=True
    )
    relapse_dates: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    sponsor_ids: Mapped[Optional[List[int]]] = mapped_column(
        JSON, nullable=True
    )
    custom_fields: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    last_active: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[List["Message"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    frames: Mapped[List["Frame"]] = relationship(
        back_populates="user", cascade="all, delete"
    )
    session_contexts: Mapped[List["SessionContext"]] = relationship(
        back_populates="user", cascade="all, delete"
    )


class Frame(Base):
    __tablename__ = "frames"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emotion: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(default=0.0)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    thinking_frame: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    level_of_mind: Mapped[Optional[int]] = mapped_column(nullable=True)
    memory_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_block: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    strategy_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="frames")
    blocks: Mapped[List["Block"]] = relationship(
        secondary=blocks_frames,
        back_populates="frames"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sender_role: Mapped[Optional[SenderRole]] = mapped_column(
        SQLEnum(SenderRole, name="sender_role_enum", create_type=True)
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship(back_populates="messages")


class Block(Base):
    __tablename__ = "blocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[Optional[str]] = mapped_column(
        "label",
        String(255),
        unique=True,
        index=True,
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        server_default=text("TIMEZONE('utc', now())")
    )

    frames: Mapped[List["Frame"]] = relationship(
        secondary=blocks_frames,
        back_populates="blocks"
    )


class Step(Base):
    __tablename__ = "steps"

    id = Column(Integer, primary_key=True, index=True)
    index = Column(Integer, unique=True, nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    questions = relationship("Question", back_populates="step", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "step_questions"

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    step_id = Column(Integer, ForeignKey("steps.id", ondelete="CASCADE"), nullable=False)

    step = relationship("Step", back_populates="questions")
    answers = relationship("StepAnswer", back_populates="question", cascade="all, delete-orphan")
    tails = relationship("Tail", back_populates="question", cascade="all, delete-orphan")


class StepAnswer(Base):
    __tablename__ = "step_answers"

    table_args = (
        UniqueConstraint("user_id", "question_id", "version", name="uq_step_answer_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("step_questions.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    question: Mapped["Question"] = relationship(back_populates="answers")


class UserStep(Base):
    __tablename__ = "user_steps"

    table_args = (
        UniqueConstraint("user_id", "step_id", name="uq_user_step"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    status: Mapped[StepProgressStatus] = mapped_column(
        SQLEnum(StepProgressStatus, name="step_progress_status_enum", create_type=True),
        default=StepProgressStatus.NOT_STARTED,
        server_default=StepProgressStatus.NOT_STARTED.value,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionContext(Base):
    __tablename__ = "session_contexts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_type = Column(SQLEnum(SessionType, name="session_type_enum", create_type=True), nullable=False)
    context_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="session_contexts")


class SessionState(Base):
    __tablename__ = "session_states"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recent_messages: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True
    )
    daily_snapshot: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    active_blocks: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    pending_topics: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    group_signals: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()


class FrameTracking(Base):
    __tablename__ = "frame_tracking"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confirmed: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True
    )
    candidates: Mapped[Optional[List[dict]]] = mapped_column(
        JSON, nullable=True
    )
    tracking: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    archetypes: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    meta_flags: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()


class QAStatus(Base):
    __tablename__ = "qa_status"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_prompt_included: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False
    )
    trace_ok: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False
    )
    open_threads: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )
    rebuild_required: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()


class UserMeta(Base):
    __tablename__ = "user_meta"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    metasloy_signals: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    prompt_revision_history: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, default=0
    )
    time_zone: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    language: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, default='ru'
    )
    data_flags: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()


class TrackerSummary(Base):
    __tablename__ = "tracker_summaries"

    table_args = (
        UniqueConstraint("user_id", "date", name="uq_tracker_summary_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thinking: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    feeling: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    behavior: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    relationships: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    health: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )
    date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()


class Tail(Base):
    __tablename__ = "tails"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tail_type: Mapped[TailType] = mapped_column(
        SQLEnum(TailType, name="tail_type_enum", create_type=True),
        default=TailType.STEP_QUESTION,
        server_default=TailType.STEP_QUESTION.value,
    )
    step_id: Mapped[Optional[int]] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), nullable=True, index=True)

    step_question_id: Mapped[Optional[int]] = mapped_column(ForeignKey("step_questions.id", ondelete="CASCADE"), nullable=True, index=True)

    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()
    step: Mapped["Step"] = relationship()
    question: Mapped["Question"] = relationship(back_populates="tails")



class AnswerTemplate(Base):
    __tablename__ = "answer_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[TemplateType] = mapped_column(
        SQLEnum(TemplateType, name="template_type_enum", create_type=True),
        default=TemplateType.CUSTOM,
        server_default=TemplateType.CUSTOM.value,
    )
    structure: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(foreign_keys=[user_id])



class ProfileSection(Base):
    __tablename__ = "profile_sections"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[Optional["User"]] = relationship()
    questions: Mapped[List["ProfileQuestion"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="ProfileQuestion.order_index"
    )
    section_data: Mapped[List["ProfileSectionData"]] = relationship(
        back_populates="section", cascade="all, delete-orphan"
    )


class ProfileSectionData(Base):
    __tablename__ = "profile_section_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("profile_sections.id", ondelete="CASCADE"), index=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    subblock_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Название подблока (например, 'Юрист', 'Судья')")
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Тип сущности (profession, role, relationship и т.п.)")
    importance: Mapped[Optional[float]] = mapped_column(Float, nullable=True, server_default=text("1.0"), comment="Важность записи (0.0-1.0)")
    is_core_personality: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"), comment="Входит ли в ядро личности")
    tags: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Теги через запятую (эмоции, триггеры, тон)")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()
    section: Mapped["ProfileSection"] = relationship(back_populates="section_data")


class ProfileQuestion(Base):
    __tablename__ = "profile_questions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("profile_sections.id", ondelete="CASCADE"), index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    section: Mapped["ProfileSection"] = relationship(back_populates="questions")
    answers: Mapped[List["ProfileAnswer"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class ProfileAnswer(Base):
    __tablename__ = "profile_answers"

    table_args = (
        UniqueConstraint("user_id", "question_id", "version", name="uq_profile_answer_version"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("profile_questions.id", ondelete="CASCADE"), index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship()
    question: Mapped["ProfileQuestion"] = relationship(back_populates="answers")



class TemplateProgressStatus(Enum):
    """Статус прогресса по шаблону"""
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class TemplateProgress(Base):
    __tablename__ = "template_progress"

    __table_args__ = (
        UniqueConstraint("user_id", "step_id", "question_id", name="uq_template_progress_user_step_question"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[int] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("step_questions.id", ondelete="CASCADE"), index=True)

    status: Mapped[TemplateProgressStatus] = mapped_column(
        SQLEnum(TemplateProgressStatus, name="template_progress_status_enum", create_type=True),
        default=TemplateProgressStatus.IN_PROGRESS,
        server_default=TemplateProgressStatus.IN_PROGRESS.value,
    )

    current_situation: Mapped[int] = mapped_column(Integer, default=1)
    current_field: Mapped[str] = mapped_column(String(50), default="where")

    situations: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True)

    conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()



class Step10AnalysisStatus(Enum):
    """Статус ежедневного самоанализа по 10 шагу"""
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


class Step10DailyAnalysis(Base):
    __tablename__ = "step10_daily_analysis"

    __table_args__ = (
        UniqueConstraint("user_id", "analysis_date", name="uq_step10_analysis_user_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    analysis_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    status: Mapped[Step10AnalysisStatus] = mapped_column(
        SQLEnum(Step10AnalysisStatus, name="step10_analysis_status_enum", create_type=True),
        default=Step10AnalysisStatus.IN_PROGRESS,
        server_default=Step10AnalysisStatus.IN_PROGRESS.value,
    )

    current_question: Mapped[int] = mapped_column(Integer, default=1)

    answers: Mapped[Optional[List[dict]]] = mapped_column(JSON, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship()


class Gratitude(Base):
    """Модель для хранения благодарностей пользователя"""
    __tablename__ = "gratitudes"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    text: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship()

# Модель Subscription

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="free")  # free / active / trial / expired / cancelled
    plan: Mapped[str] = mapped_column(String(20), default="free")    # free / premium

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    payment_provider: Mapped[Optional[str]] = mapped_column(String(20))  # yookassa / cryptomus
    payment_id: Mapped[Optional[str]] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="subscription", uselist=False)

    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription", back_populates="user", uselist=False
    )

    @property
    def is_premium(self) -> bool:
        """Быстрая проверка активной подписки (включая trial)"""

        if not self.subscription:
            return False
        
        sub = self.subscription

        if sub.status not in ("active", "trial"):
            return False
        
        now = datetime.utcnow()

        if sub.expires_at and sub.expires_at < now:
            return False
        
        if sub.trial_ends_at and sub.trial_ends_at < now:
            return False
        
        return True