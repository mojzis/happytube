"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API Keys
    youtube_api_key: str = Field(..., alias="YTKEY", description="YouTube Data API key")
    anthropic_api_key: str = Field(..., description="Anthropic Claude API key")

    # Application
    log_level: str = Field(default="INFO", description="Logging level")
    environment: str = Field(default="development", description="Environment name")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the standard logging levels.

        Args:
            v: Log level string

        Returns:
            Uppercase log level string

        Raises:
            ValueError: If log level is not valid
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper

    @property
    def has_all_credentials(self) -> bool:
        """Check if all required credentials are configured.

        Returns:
            True if both YouTube and Anthropic API keys are set
        """
        return bool(self.youtube_api_key and self.anthropic_api_key)


def get_settings() -> Settings:
    """Get application settings singleton.

    Returns:
        Settings instance loaded from environment
    """
    return Settings()
