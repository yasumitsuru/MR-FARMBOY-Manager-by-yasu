"""Atualização imediata da UI após alterar a pasta dos saves."""

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLineEdit, QListWidget, QPushButton

from mr_farmboy_manager.application import create_main_window
from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _result_for(path: str, slot_number: int) -> SaveSlotsLoadResult:
    root = Path(path)
    summary = SaveSlotSummary(
        slot=SaveSlot(number=slot_number, path=root / f"save_{slot_number}"),
        tres_file_count=2,
    )
    return SaveSlotsLoadResult(
        validation=DirectoryValidationResult(
            code=DirectoryValidationCode.VALID,
            path=root,
        ),
        summaries=(summary,),
    )


def test_save_chooser_loads_new_configuration_and_preserves_active_source(
    qt_app: QApplication, tmp_path: Path
) -> None:
    save_root = tmp_path / "chosen-saves"
    save_root.mkdir()
    calls: list[str] = []

    def manual_loader(path: str) -> SaveSlotsLoadResult:
        calls.append(path)
        return _result_for(path, 4)

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        save_directory_chooser=lambda: save_root,
        manual_save_loader=manual_loader,
    )
    button = window.findChild(QPushButton, "browse_save_path_button")
    save_list = window.findChild(QListWidget, "save_slots_list")
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    assert button is not None
    assert save_list is not None
    assert timer is not None

    button.click()
    QApplication.processEvents()

    assert calls == [str(save_root)]
    assert save_list.count() == 1
    assert "Slot 4" in save_list.item(0).text()

    timer.timeout.emit()

    assert calls == [str(save_root), str(save_root)]


def test_finishing_save_path_edit_loads_new_configuration(
    qt_app: QApplication, tmp_path: Path
) -> None:
    save_root = tmp_path / "edited-saves"
    save_root.mkdir()
    calls: list[str] = []

    def manual_loader(path: str) -> SaveSlotsLoadResult:
        calls.append(path)
        return _result_for(path, 7)

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        manual_save_loader=manual_loader,
    )
    save_input = window.findChild(QLineEdit, "save_path_input")
    save_list = window.findChild(QListWidget, "save_slots_list")
    assert save_input is not None
    assert save_list is not None

    save_input.setText(str(save_root))
    save_input.editingFinished.emit()
    QApplication.processEvents()

    assert calls == [str(save_root)]
    assert save_list.count() == 1
    assert "Slot 7" in save_list.item(0).text()
