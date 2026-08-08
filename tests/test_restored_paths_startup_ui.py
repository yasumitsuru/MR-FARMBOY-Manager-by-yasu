"""UI tests for restored manual paths during window startup."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QListWidget, QPushButton

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary
from mr_farmboy_manager.settings import AppSettings, QtSettingsStore


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _store(tmp_path: Path) -> QtSettingsStore:
    return QtSettingsStore(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )


def _summary(number: int, tres_file_count: int) -> SaveSlotSummary:
    return SaveSlotSummary(
        slot=SaveSlot(number=number, path=Path(f"save_{number}")),
        tres_file_count=tres_file_count,
    )


def _input(window, object_name: str) -> QLineEdit:
    result = window.findChild(QLineEdit, object_name)
    assert result is not None
    return result


def _label(window, object_name: str) -> QLabel:
    result = window.findChild(QLabel, object_name)
    assert result is not None
    return result


def _button(window, object_name: str) -> QPushButton:
    result = window.findChild(QPushButton, object_name)
    assert result is not None
    return result


def _valid_result(path: str, *summaries: SaveSlotSummary) -> SaveSlotsLoadResult:
    return SaveSlotsLoadResult(
        DirectoryValidationResult(DirectoryValidationCode.VALID, Path(path)),
        summaries,
    )


def test_restored_valid_save_path_loads_once_renders_and_becomes_refresh_source(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Without startup activation the initial list and later refresh use different sources."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "saves"
    save_directory.mkdir()
    store = _store(tmp_path)
    store.save(AppSettings(save_directory=str(save_directory)))
    calls: list[str] = []
    results = [_valid_result(str(save_directory), _summary(1, 2)), _valid_result(str(save_directory), _summary(2, 3))]

    def manual_loader(path: str) -> SaveSlotsLoadResult:
        calls.append(path)
        return results.pop(0)

    window = create_main_window(
        qt_app, loader=lambda: [], manual_save_loader=manual_loader, settings_store=store
    )
    save_list = window.findChild(QListWidget, "save_slots_list")
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    assert save_list is not None
    assert timer is not None
    assert calls == [str(save_directory)]
    assert save_list.item(0).text() == "save_1 — Slot 1 — 2 arquivos .tres"

    timer.timeout.emit()
    QApplication.processEvents()

    assert calls == [str(save_directory), str(save_directory)]
    assert save_list.item(0).text() == "save_2 — Slot 2 — 3 arquivos .tres"


def test_restored_invalid_save_path_stays_visible_with_guidance_without_activation(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """A stale persisted path must remain editable without replacing the initial source."""
    from mr_farmboy_manager.application import create_main_window

    missing_directory = tmp_path / "missing-saves"
    store = _store(tmp_path)
    store.save(AppSettings(save_directory=str(missing_directory)))
    manual_calls: list[str] = []
    initial_calls = 0
    deceptive_summary = _summary(9, 99)
    refreshed_initial_summary = _summary(3, 4)

    def initial_loader() -> list[SaveSlotSummary]:
        nonlocal initial_calls
        initial_calls += 1
        if initial_calls == 1:
            return []
        return [refreshed_initial_summary]

    window = create_main_window(
        qt_app,
        loader=initial_loader,
        manual_save_loader=lambda path: manual_calls.append(path)
        or _valid_result(path, deceptive_summary),
        settings_store=store,
    )
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert timer is not None
    assert save_list is not None
    assert _input(window, "save_path_input").text() == str(missing_directory)
    assert "não existe" in _label(window, "save_path_status_label").text()
    assert "corrija" in _label(window, "save_path_status_label").text().lower()
    assert manual_calls == [str(missing_directory)]
    assert save_list.count() == 0

    timer.timeout.emit()
    QApplication.processEvents()

    assert initial_calls == 2
    assert manual_calls == [str(missing_directory)]
    assert save_list.item(0).text() == "save_3 — Slot 3 — 4 arquivos .tres"
    assert store.load().save_directory == str(missing_directory)


def test_restored_existing_path_with_loader_failure_uses_initial_refresh_source(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Loader failure must be shown without activating an otherwise real directory."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "saves"
    save_directory.mkdir()
    store = _store(tmp_path)
    store.save(AppSettings(save_directory=str(save_directory)))
    manual_calls: list[str] = []
    initial_calls = 0
    refreshed_initial_summary = _summary(4, 5)

    def initial_loader() -> list[SaveSlotSummary]:
        nonlocal initial_calls
        initial_calls += 1
        if initial_calls == 1:
            return []
        return [refreshed_initial_summary]

    def failing_manual_loader(path: str) -> SaveSlotsLoadResult:
        manual_calls.append(path)
        return SaveSlotsLoadResult(
            DirectoryValidationResult(DirectoryValidationCode.NOT_FOUND, Path(path)),
            (),
        )

    window = create_main_window(
        qt_app,
        loader=initial_loader,
        manual_save_loader=failing_manual_loader,
        settings_store=store,
    )
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    save_list = window.findChild(QListWidget, "save_slots_list")
    empty_label = _label(window, "empty_save_slots_label")
    assert timer is not None
    assert save_list is not None
    assert manual_calls == [str(save_directory)]
    assert save_list.count() == 0
    assert empty_label.text() == "A pasta dos saves não existe."

    timer.timeout.emit()
    QApplication.processEvents()

    assert initial_calls == 2
    assert manual_calls == [str(save_directory)]
    assert save_list.item(0).text() == "save_4 — Slot 4 — 5 arquivos .tres"


def test_restored_game_install_path_reports_validation_without_loading_saves(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """The game directory is informational and must not invoke save loading."""
    from mr_farmboy_manager.application import create_main_window

    game_directory = tmp_path / "game"
    game_directory.mkdir()
    missing_game_directory = tmp_path / "missing-game"
    for path, expected_status in ((game_directory, "válida"), (missing_game_directory, "não existe")):
        store_directory = tmp_path / f"settings-{path.name}"
        store_directory.mkdir()
        store = _store(store_directory)
        store.save(AppSettings(game_install_directory=str(path)))
        manual_calls: list[str] = []
        window = create_main_window(
            qt_app,
            loader=lambda: [],
            manual_save_loader=lambda value: manual_calls.append(value) or _valid_result(value),
            settings_store=store,
        )

        assert _input(window, "game_install_path_input").text() == str(path)
        assert expected_status in _label(window, "game_install_path_status_label").text()
        assert manual_calls == []


def test_no_store_does_not_load_manual_saves_at_startup(qt_app: QApplication) -> None:
    """Direct window creation retains the original initial-loader-only behavior."""
    from mr_farmboy_manager.application import create_main_window

    manual_calls: list[str] = []
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        manual_save_loader=lambda path: manual_calls.append(path) or _valid_result(path),
    )

    assert window is not None
    assert manual_calls == []


def test_editing_and_chooser_update_status_without_persisting_invalid_values(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Status must track edits while persisted settings retain the last valid directories."""
    from mr_farmboy_manager.application import create_main_window

    valid_save = tmp_path / "valid-save"
    valid_game = tmp_path / "valid-game"
    valid_save.mkdir()
    valid_game.mkdir()
    invalid_save = tmp_path / "missing-save"
    invalid_game = tmp_path / "missing-game"
    store = _store(tmp_path)
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: invalid_save,
        game_install_directory_chooser=lambda: invalid_game,
        settings_store=store,
    )
    save_input = _input(window, "save_path_input")
    game_input = _input(window, "game_install_path_input")
    save_input.setText(str(valid_save))
    save_input.editingFinished.emit()
    game_input.setText(str(valid_game))
    game_input.editingFinished.emit()

    _button(window, "browse_save_path_button").click()
    _button(window, "browse_game_install_button").click()
    QApplication.processEvents()

    assert "não existe" in _label(window, "save_path_status_label").text()
    assert "não existe" in _label(window, "game_install_path_status_label").text()
    assert store.load() == AppSettings(str(valid_save), str(valid_game))
