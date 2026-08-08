"""Teste de jornada para a configuração inicial e carga manual de saves."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
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


def _widget(window, widget_type, object_name: str):
    widget = window.findChild(widget_type, object_name)
    assert widget is not None
    return widget


def test_first_run_configures_then_loads_saves_without_restarting(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """A primeira configuração só carrega saves após o clique explícito."""
    from mr_farmboy_manager.application import create_main_window

    save_directory = tmp_path / "saves"
    save_directory.mkdir()
    store = QtSettingsStore(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    summary = SaveSlotSummary(
        slot=SaveSlot(number=1, path=save_directory / "save_1"),
        tres_file_count=3,
    )
    loaded_paths: list[str] = []

    def manual_loader(path: str) -> SaveSlotsLoadResult:
        loaded_paths.append(path)
        return SaveSlotsLoadResult(
            validation=DirectoryValidationResult(
                DirectoryValidationCode.VALID, Path(path)
            ),
            summaries=(summary,),
        )

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: save_directory,
        manual_save_loader=manual_loader,
        settings_store=store,
    )
    try:
        path_input = _widget(window, QLineEdit, "save_path_input")
        path_status = _widget(window, QLabel, "save_path_status_label")
        browse_button = _widget(window, QPushButton, "browse_save_path_button")
        load_button = _widget(window, QPushButton, "load_saves_button")
        save_list = _widget(window, QListWidget, "save_slots_list")

        assert store.load() == AppSettings()
        assert path_status.text() == "Nenhuma pasta dos saves configurada."

        browse_button.click()
        QApplication.processEvents()

        assert path_input.text() == str(save_directory)
        assert path_status.text() == "Pasta dos saves válida."
        assert store.load() == AppSettings(save_directory=str(save_directory))
        assert loaded_paths == []

        load_button.click()
        QApplication.processEvents()

        assert loaded_paths == [str(save_directory)]
        assert save_list.count() == 1
        assert save_list.item(0).text() == "save_1 — Slot 1 — 3 arquivos .tres"
        assert load_button.toolTip() == (
            "Valida a pasta configurada e carrega os saves sem reiniciar o aplicativo."
        )
    finally:
        window.close()
