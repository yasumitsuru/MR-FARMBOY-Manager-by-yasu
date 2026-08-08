"""Persistent application configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QSettings


@dataclass(frozen=True, slots=True)
class AppSettings:
    """User-configurable directories used by the application."""

    save_directory: str = ""
    game_install_directory: str = ""


class SettingsStore(Protocol):
    """Persistence boundary for application settings."""

    def load(self) -> AppSettings:
        """Load the current application settings."""

    def save(self, settings: AppSettings) -> None:
        """Persist application settings."""


class QtSettingsStore:
    """Persist settings through Qt's ``QSettings`` backend."""

    _SAVE_DIRECTORY_KEY = "paths/save_directory"
    _GAME_INSTALL_DIRECTORY_KEY = "paths/game_install_directory"

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings("yasu", "MR FARMBOY Manager")

    def load(self) -> AppSettings:
        """Return stored paths, defaulting missing entries to empty strings."""
        return AppSettings(
            save_directory=self._value_as_string(self._SAVE_DIRECTORY_KEY),
            game_install_directory=self._value_as_string(
                self._GAME_INSTALL_DIRECTORY_KEY
            ),
        )

    def save(self, settings: AppSettings) -> None:
        """Store both paths and flush them to the backing settings store."""
        self._settings.setValue(self._SAVE_DIRECTORY_KEY, settings.save_directory)
        self._settings.setValue(
            self._GAME_INSTALL_DIRECTORY_KEY,
            settings.game_install_directory,
        )
        self._settings.sync()

    def _value_as_string(self, key: str) -> str:
        value = self._settings.value(key, "")
        return "" if value is None else str(value)
