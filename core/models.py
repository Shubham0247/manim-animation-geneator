from pydantic import BaseModel, Field
from typing import Optional


class UserRequest(BaseModel):
    prompt: str = Field(..., description="Original user prompt for animation")


class RefinedRequest(BaseModel):
    original_prompt: str = Field(..., description="Original user prompt")
    refined_description: str = Field(..., description="Refined and detailed description for Manim code generation")


class ManimCode(BaseModel):
    code: str = Field(..., description="Complete Manim Python code")
    scene_name: Optional[str] = Field(None, description="Name of the Scene class in the code")


class ManimExecutionResult(BaseModel):
    success: bool = Field(..., description="Whether execution was successful")
    video_path: Optional[str] = Field(None, description="Path to generated video file")
    stderr: Optional[str] = Field(None, description="Error output if execution failed")
    stdout: Optional[str] = Field(None, description="Standard output from execution")


class GraphResult(BaseModel):
    user_request: UserRequest
    refined: RefinedRequest
    code: ManimCode
    execution: ManimExecutionResult
    retries: int = Field(0, description="Number of retry attempts made")
