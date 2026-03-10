"""
INTERNAL ROUTER — Зона бекенда (разработчик)

Внутренние эндпоинты для управления состоянием:
- Session context
- User state (SessionState)
- Frame tracking
- QA status
- Tracker summary
- User meta

Сюда же добавлять: платежи, шифрование, и т.д.
"""

from typing import Optional
from datetime import date as date_class
from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import CurrentUserContext, get_current_user
from api.schemas import (
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
)
from repositories.SessionStateRepository import SessionStateRepository
from repositories.FrameTrackingRepository import FrameTrackingRepository
from repositories.QAStatusRepository import QAStatusRepository
from repositories.UserMetaRepository import UserMetaRepository
from repositories.TrackerSummaryRepository import TrackerSummaryRepository

router = APIRouter()


# ===========================================================================
#  SESSION CONTEXT
# ===========================================================================

@router.post("/session/context")
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

@router.get("/session/context")
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


# ===========================================================================
#  USER STATE
# ===========================================================================

@router.get("/user/state", response_model=SessionStateResponse)
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


@router.post("/user/state", response_model=SessionStateResponse)
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


# ===========================================================================
#  FRAME TRACKING
# ===========================================================================

@router.get("/user/frames", response_model=FrameTrackingResponse)
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


@router.post("/user/frames", response_model=FrameTrackingResponse)
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


# ===========================================================================
#  QA STATUS
# ===========================================================================

@router.get("/user/qa-status", response_model=QAStatusResponse)
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


@router.post("/user/qa-status", response_model=QAStatusResponse)
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


# ===========================================================================
#  TRACKER SUMMARY
# ===========================================================================

@router.get("/user/tracker-summary", response_model=TrackerSummaryResponse)
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


@router.post("/user/tracker-summary", response_model=TrackerSummaryResponse)
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


# ===========================================================================
#  USER META
# ===========================================================================

@router.get("/user/meta", response_model=UserMetaResponse)
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


@router.put("/user/meta", response_model=UserMetaResponse)
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
