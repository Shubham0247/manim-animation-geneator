"""Configuration management using Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import AliasChoices, Field
from pathlib import Path
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Azure OpenAI Configuration
    azure_openai_api_key: str = Field(
        validation_alias=AliasChoices("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    azure_openai_endpoint: str = Field(
        validation_alias=AliasChoices("AZURE_OPENAI_ENDPOINT", "OPENAI_ENDPOINT", "OPENAI_API_BASE")
    )
    azure_openai_deployment: str = Field(
        validation_alias=AliasChoices("AZURE_OPENAI_DEPLOYMENT", "OPENAI_DEPLOYMENT", "OPENAI_MODEL")
    )
    azure_openai_api_version: str = "2024-02-15-preview"
    # If not provided, we'll use the Azure deployment name as the model.
    openai_model: Optional[str] = None
    
    # LangSmith Configuration (optional, for LangGraph Studio)
    langsmith_api_key: Optional[str] = None
    
    # Manim Configuration
    manim_output_dir: Path = Path("videos")
    manim_default_quality: str = "medium"  # low, medium, high
    manim_default_resolution: str = "1920x1080"
    
    # LangGraph Configuration
    max_retries: int = 3

    # MCP Configuration
    mcp_timeout_seconds: int = 300
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra="ignore"


# Global settings instance
settings = Settings()
