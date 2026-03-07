"""Compatibility wrapper. Main registration lives in bot.handlers package."""

from bot.handlers import register_handlers

__all__ = ["register_handlers"]
