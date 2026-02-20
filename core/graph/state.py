"""LangGraph state definition."""

from typing import TypedDict, Optional
from core.models import UserRequest, RefinedRequest, ManimCode, ManimExecutionResult


class GraphState(TypedDict, total=False):
    """State passed between LangGraph nodes."""
    user_request: UserRequest
    refined: RefinedRequest
    manim_code: ManimCode
    execution: ManimExecutionResult
    error_message: str
    retries: int
