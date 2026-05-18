"""Configuration helpers for the monitoring report automation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables or local config."""

    google_forms_url: str | None = None
    spreadsheet_id: str | None = None


def load_settings() -> Settings:
    """Load project settings.

    Placeholder for future environment and credentials loading.
    """
    raise NotImplementedError("Settings loading is not implemented yet.")
