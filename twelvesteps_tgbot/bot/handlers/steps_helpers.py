from bot.backend import BACKEND_CLIENT
from bot.config import format_step_progress_indicator


async def get_step_with_progress(token):
    """Get step info and formatted progress indicator.

    Returns (step_info, progress_indicator) tuple.
    If step_info is None or has no step_number, progress_indicator is "".
    """
    step_info = await BACKEND_CLIENT.get_current_step_info(token)
    if not step_info or not step_info.get("step_number"):
        return step_info, ""
    progress = format_step_progress_indicator(
        step_number=step_info.get("step_number"),
        total_steps=step_info.get("total_steps", 12),
        step_title=step_info.get("step_title"),
        answered_questions=step_info.get("answered_questions", 0),
        total_questions=step_info.get("total_questions", 0),
    )
    return step_info, progress
