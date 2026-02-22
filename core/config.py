from pathlib import Path
from typing import Optional
from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # OpenAI (non-Azure) configuration
    openai_api_key: Optional[str] = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY"))
    openai_base_url: Optional[str] = Field(default=None, validation_alias=AliasChoices("OPENAI_BASE_URL"))

    # Azure OpenAI Configuration
    azure_openai_api_key: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    azure_openai_endpoint: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_OPENAI_ENDPOINT", "OPENAI_ENDPOINT", "OPENAI_API_BASE"),
    )
    azure_openai_deployment: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AZURE_OPENAI_DEPLOYMENT", "OPENAI_DEPLOYMENT"),
    )
    azure_openai_api_version: str = "2024-02-15-preview"

    # If not provided for Azure, deployment name is used. For OpenAI, a default model is used.
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_llm_credentials(self) -> "Settings":
        """Require either OpenAI or Azure OpenAI credentials."""
        azure_enabled = bool(self.azure_openai_endpoint and self.azure_openai_deployment)
        openai_enabled = bool(self.openai_api_key)

        if azure_enabled:
            if not (self.azure_openai_api_key or self.openai_api_key):
                raise ValueError(
                    "Azure OpenAI is configured but no API key was provided. "
                    "Set AZURE_OPENAI_API_KEY (or OPENAI_API_KEY)."
                )
        elif not openai_enabled:
            raise ValueError(
                "Missing LLM credentials. Configure either OPENAI_API_KEY for OpenAI, "
                "or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_DEPLOYMENT + AZURE_OPENAI_API_KEY for Azure OpenAI."
            )

        return self


# Global settings instance
settings = Settings()
