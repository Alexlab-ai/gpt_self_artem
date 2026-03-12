"""Steps handlers — re-export hub.

All handler functions are split into sub-modules for maintainability:
  steps_core.py       — entry point, answer mode, about, settings
  steps_actions.py    — step action callbacks (draft, edit, complete, etc.)
  steps_navigation.py — navigation callbacks (select step, questions, back)
  steps_progress.py   — progress viewing callbacks
  steps_template.py   — template selection and filling
  steps_helpers.py    — shared helper (get_step_with_progress)
"""

# Core handlers
from .steps_core import (
    handle_steps,
    handle_step_answer_mode,
    handle_step_answer,
    handle_about_step,
    handle_steps_settings,
    handle_steps_settings_callback,
)

# Step action callbacks
from .steps_actions import handle_step_action_callback

# Navigation callbacks
from .steps_navigation import (
    handle_steps_navigation_callback,
    handle_step_selection_callback,
    handle_question_view_callback,
    handle_question_select_callback,
    handle_step_questions_list_callback,
    handle_questions_group_callback,
)

# Progress callbacks
from .steps_progress import (
    handle_progress_callback,
    handle_progress_questions_group_callback,
)

# Template handlers
from .steps_template import (
    handle_template_selection,
    handle_template_filling_callback,
    handle_template_field_input,
)

__all__ = [
    "handle_steps",
    "handle_step_answer_mode",
    "handle_step_answer",
    "handle_about_step",
    "handle_steps_settings",
    "handle_steps_settings_callback",
    "handle_step_action_callback",
    "handle_steps_navigation_callback",
    "handle_step_selection_callback",
    "handle_question_view_callback",
    "handle_question_select_callback",
    "handle_step_questions_list_callback",
    "handle_questions_group_callback",
    "handle_progress_callback",
    "handle_progress_questions_group_callback",
    "handle_template_selection",
    "handle_template_filling_callback",
    "handle_template_field_input",
]
