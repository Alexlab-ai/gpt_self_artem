"""Compatibility wrapper. Main registration now lives in bot.handlers_modules."""

from bot.handlers_modules import register_handlers

__all__ = ["register_handlers"]
