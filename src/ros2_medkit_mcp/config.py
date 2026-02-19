"""Configuration management for ros2_medkit_mcp.

Loads settings from environment variables with sensible defaults.
"""

import os

from pydantic import BaseModel, Field


def _default_timeout() -> float:
    """Parse timeout from environment, falling back to 30s on empty values."""
    raw = os.getenv("ROS2_MEDKIT_TIMEOUT_S")
    if raw is None or raw.strip() == "":
        return 30.0
    try:
        return float(raw)
    except ValueError as exc:  # Preserve clear error for invalid input
        raise ValueError("ROS2_MEDKIT_TIMEOUT_S must be numeric") from exc


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    base_url: str = Field(
        default_factory=lambda: os.getenv("ROS2_MEDKIT_BASE_URL", "http://localhost:8080/api/v1"),
        description="Base URL of the ros2_medkit SOVD API",
    )
    bearer_token: str | None = Field(
        default_factory=lambda: os.getenv("ROS2_MEDKIT_BEARER_TOKEN") or None,
        description="Optional Bearer token for authentication",
    )
    timeout_seconds: float = Field(
        default_factory=_default_timeout,
        description="HTTP request timeout in seconds",
    )

    model_config = {"frozen": True}


def get_settings() -> Settings:
    """Create settings instance from current environment.

    Returns:
        Settings instance with values from environment variables.
    """
    return Settings()
