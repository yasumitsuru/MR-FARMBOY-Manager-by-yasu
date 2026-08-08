"""Tests for persistent application settings."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from mr_farmboy_manager.settings import AppSettings, QtSettingsStore


def _ini_settings(tmp_path) -> QSettings:
    """Create an isolated INI-backed QSettings instance."""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_app_settings_defaults_are_empty_and_immutable() -> None:
    """A mutable settings value cannot accidentally alter stored path state."""
    settings = AppSettings()

    assert settings.save_directory == ""
    assert settings.game_install_directory == ""
    assert not hasattr(settings, "__dict__")

    with pytest.raises(AttributeError):
        settings.save_directory = "C:/saves"


def test_load_returns_empty_paths_when_settings_are_absent(tmp_path) -> None:
    """An empty INI file produces the safe default application settings."""
    store = QtSettingsStore(_ini_settings(tmp_path))

    assert store.load() == AppSettings()


def test_save_then_load_round_trips_both_paths(tmp_path) -> None:
    """Both configured directories survive a save and subsequent load."""
    store = QtSettingsStore(_ini_settings(tmp_path))
    expected = AppSettings(
        save_directory="C:/MR FARMBOY/saves",
        game_install_directory="D:/Steam/MR FARMBOY",
    )

    store.save(expected)

    assert store.load() == expected


def test_new_store_instance_loads_latest_persisted_paths(tmp_path) -> None:
    """A later change is visible to a new store reading the same INI file."""
    ini_path = tmp_path / "settings.ini"
    first_store = QtSettingsStore(
        QSettings(str(ini_path), QSettings.Format.IniFormat)
    )
    first_store.save(
        AppSettings(
            save_directory="C:/old-save",
            game_install_directory="D:/old-game",
        )
    )
    first_store.save(
        AppSettings(
            save_directory="C:/new-save",
            game_install_directory="D:/new-game",
        )
    )

    reloaded = QtSettingsStore(
        QSettings(str(ini_path), QSettings.Format.IniFormat)
    ).load()

    assert reloaded == AppSettings(
        save_directory="C:/new-save",
        game_install_directory="D:/new-game",
    )
