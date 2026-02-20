"""Pydantic models for type safety across the application."""

from pydantic import BaseModel, Field
from typing import Optional


class UserRequest(BaseModel):
    """User's original animation request."""
    prompt: str = Field(..., description="Original user prompt for animation")


class RefinedRequest(BaseModel):
    """Refined and clarified animation request."""
    original_prompt: str = Field(..., description="Original user prompt")
    refined_description: str = Field(..., description="Refined and detailed description for Manim code generation")


class ManimCode(BaseModel):
    """Generated Manim Python code."""
    code: str = Field(..., description="Complete Manim Python code")
    scene_name: Optional[str] = Field(None, description="Name of the Scene class in the code")


class ManimExecutionResult(BaseModel):
    """Result of Manim code execution."""
    success: bool = Field(..., description="Whether execution was successful")
    video_path: Optional[str] = Field(None, description="Path to generated video file")
    stderr: Optional[str] = Field(None, description="Error output if execution failed")
    stdout: Optional[str] = Field(None, description="Standard output from execution")


class GraphResult(BaseModel):
    """Final result from LangGraph execution."""
    user_request: UserRequest
    refined: RefinedRequest
    code: ManimCode
    execution: ManimExecutionResult
    retries: int = Field(0, description="Number of retry attempts made")
