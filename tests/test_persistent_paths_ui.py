"""UI integration tests for persisted manual-path settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
)
from mr_farmboy_manager.settings import AppSettings, QtSettingsStore


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _store(tmp_path: Path) -> QtSettingsStore:
    return QtSettingsStore(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )


def _input(window, object_name: str) -> QLineEdit:
    result = window.findChild(QLineEdit, object_name)
    assert result is not None
    return result


def _button(window, object_name: str) -> QPushButton:
    result = window.findChild(QPushButton, object_name)
    assert result is not None
    return result


def test_injected_store_restores_paths_once_without_loading_manual_saves(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """A missing load call would leave the persisted paths out of the form."""
    from mr_farmboy_manager.application import create_main_window

    class CountingStore:
        def __init__(self) -> None:
            self.load_calls = 0

        def load(self) -> AppSettings:
            self.load_calls += 1
            return AppSettings("save-value", "game-value")

        def save(self, settings: AppSettings) -> None:
            raise AssertionError("creating the window must not save settings")

    manual_loader_calls = 0

    def manual_loader(_path: str) -> SaveSlotsLoadResult:
        nonlocal manual_loader_calls
        manual_loader_calls += 1
        raise AssertionError("creating the window must not load manual saves")

    store = CountingStore()
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        manual_save_loader=manual_loader,
        settings_store=store,
    )

    assert store.load_calls == 1
    assert _input(window, "save_path_input").text() == "save-value"
    assert _input(window, "game_install_path_input").text() == "game-value"
    assert manual_loader_calls == 0


def test_no_store_keeps_both_path_fields_empty(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An implicit settings backend would make direct window creation non-isolated."""
    from mr_farmboy_manager.application import create_main_window

    def fail_if_instantiated(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("direct window creation must not instantiate QtSettingsStore")

    monkeypatch.setattr(
        "mr_farmboy_manager.application.QtSettingsStore", fail_if_instantiated
    )

    window = create_main_window(qt_app, loader=lambda: [])

    assert _input(window, "save_path_input").text() == ""
    assert _input(window, "game_install_path_input").text() == ""


def test_chooser_selections_persist_and_restore_both_paths(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Dropping either chooser write would lose that path after reopening."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "saves"
    game_directory = tmp_path / "game"
    save_directory.mkdir()
    game_directory.mkdir()
    store = _store(tmp_path)

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: save_directory,
        game_install_directory_chooser=lambda: game_directory,
        settings_store=store,
    )
    _button(window, "browse_save_path_button").click()
    _button(window, "browse_game_install_button").click()
    QApplication.processEvents()

    reopened = create_main_window(
        qt_app, loader=lambda: [], settings_store=_store(tmp_path)
    )

    assert _input(reopened, "save_path_input").text() == str(save_directory)
    assert _input(reopened, "game_install_path_input").text() == str(game_directory)


def test_valid_edit_then_invalid_edit_keeps_last_persisted_save_path(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Saving invalid text would overwrite a previously valid save directory."""
    from mr_farmboy_manager.application import create_main_window

    valid_directory = tmp_path / "valid-saves"
    valid_directory.mkdir()
    window = create_main_window(
        qt_app, loader=lambda: [], settings_store=_store(tmp_path)
    )
    save_path_input = _input(window, "save_path_input")

    save_path_input.setText(str(valid_directory))
    save_path_input.editingFinished.emit()
    save_path_input.setText(str(tmp_path / "missing-saves"))
    save_path_input.editingFinished.emit()

    assert _store(tmp_path).load() == AppSettings(save_directory=str(valid_directory))


def test_valid_edit_then_invalid_edit_keeps_last_game_path_and_saved_path(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """An invalid game edit must preserve it and the previously saved path."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "existing-saves"
    valid_game_directory = tmp_path / "valid-game"
    save_directory.mkdir()
    valid_game_directory.mkdir()
    store = _store(tmp_path)
    store.save(AppSettings(save_directory=str(save_directory)))
    window = create_main_window(qt_app, loader=lambda: [], settings_store=store)
    game_path_input = _input(window, "game_install_path_input")

    game_path_input.setText(str(valid_game_directory))
    game_path_input.editingFinished.emit()
    game_path_input.setText(str(tmp_path / "missing-game"))
    game_path_input.editingFinished.emit()

    assert _store(tmp_path).load() == AppSettings(
        save_directory=str(save_directory),
        game_install_directory=str(valid_game_directory),
    )


def test_valid_manual_load_persists_save_directory(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """A successful manual load without persistence would be lost on reopening."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "manual-saves"
    save_directory.mkdir()

    def manual_loader(path: str) -> SaveSlotsLoadResult:
        return SaveSlotsLoadResult(
            validation=DirectoryValidationResult(
                DirectoryValidationCode.VALID, Path(path)
            ),
            summaries=(),
        )

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        manual_save_loader=manual_loader,
        settings_store=_store(tmp_path),
    )
    _input(window, "save_path_input").setText(str(save_directory))
    _button(window, "load_saves_button").click()
    QApplication.processEvents()

    assert _store(tmp_path).load() == AppSettings(save_directory=str(save_directory))


def test_cancelled_chooser_does_not_change_persisted_paths(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Treating a cancelled chooser as a value would erase saved settings."""
    from mr_farmboy_manager.application import create_main_window

    store = _store(tmp_path)
    expected = AppSettings("existing-save", "existing-game")
    store.save(expected)
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: None,
        game_install_directory_chooser=lambda: None,
        settings_store=store,
    )

    _button(window, "browse_save_path_button").click()
    _button(window, "browse_game_install_button").click()
    QApplication.processEvents()

    assert _store(tmp_path).load() == expected
