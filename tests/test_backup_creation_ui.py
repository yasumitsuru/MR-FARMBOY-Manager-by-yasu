"""Integração UI do serviço seguro de criação de backups."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from mr_farmboy_manager.backups import (
    BACKUP_MANIFEST_FILENAME,
    BackupCreationResult,
    BackupErrorCode,
    BackupRecord,
)
from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _summary(tmp_path: Path) -> SaveSlotSummary:
    slot_path = tmp_path / "game_data" / "save_3"
    slot_path.mkdir(parents=True)
    return SaveSlotSummary(SaveSlot(3, slot_path), 2)


def _widgets(window):
    slots = window.findChild(QListWidget, "save_slots_list")
    button = window.findChild(QPushButton, "create_backup_button")
    status = window.findChild(QLabel, "backup_status_label")
    root = window.findChild(QLabel, "backup_root_label")
    assert slots is not None and button is not None
    assert status is not None and root is not None
    return slots, button, status, root


def test_backup_action_starts_disabled_and_does_not_call_service(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    calls = 0

    def creator(*_args) -> BackupCreationResult:
        nonlocal calls
        calls += 1
        raise AssertionError("serviço não deveria ser chamado")

    backup_root = tmp_path / "manager" / "backups"
    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_creator=creator,
        backup_root=backup_root,
    )
    try:
        slots, button, status, root = _widgets(window)

        assert slots.currentRow() == -1
        assert not button.isEnabled()
        assert "Selecione" in status.text()
        assert str(backup_root) in root.text()
        assert calls == 0
    finally:
        window.close()


def test_selection_enables_backup_and_success_reports_created_record(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    backup_root = tmp_path / "manager" / "backups"
    created_at = datetime(2026, 8, 8, 13, 45, 12, tzinfo=UTC)
    backup_id = "save_3-20260808T134512Z-" + "a" * 32
    received: list[tuple[SaveSlot, Path, Path]] = []
    button_at_call: list[bool] = []

    def creator(
        slot: SaveSlot, active_root: Path, destination_root: Path
    ) -> BackupCreationResult:
        received.append((slot, active_root, destination_root))
        button_at_call.append(button.isEnabled())
        return BackupCreationResult(
            backup=BackupRecord(
                backup_id=backup_id,
                slot_number=3,
                created_at_utc=created_at,
                destination=backup_root / backup_id,
                file_count=2,
                total_size_bytes=4096,
            ),
            error_code=None,
            public_message=f"Backup criado com sucesso: {backup_id}.",
        )

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_creator=creator,
        backup_root=backup_root,
    )
    slots, button, status, _root = _widgets(window)
    try:
        slots.setCurrentRow(0)
        qt_app.processEvents()

        assert button.isEnabled()
        assert "Slot 3" in status.text()

        button.click()
        qt_app.processEvents()

        assert received == [(summary.slot, summary.slot.path.parent, backup_root)]
        assert button_at_call == [False]
        assert button.isEnabled()
        assert backup_id in status.text()
        assert "2 arquivo" in status.text()
        assert "4,0 KiB" in status.text()
    finally:
        window.close()
        qt_app.processEvents()


def test_backup_failure_and_exception_are_sanitized(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    backup_root = tmp_path / "backups"
    outcomes: list[object] = [
        BackupCreationResult(
            backup=None,
            error_code=BackupErrorCode.COPY_FAILED,
            public_message="Não foi possível copiar o save.",
        ),
        PermissionError(f"private-token {tmp_path}"),
    ]

    def creator(*_args) -> BackupCreationResult:
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, BackupCreationResult)
        return outcome

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_creator=creator,
        backup_root=backup_root,
    )
    slots, button, status, _root = _widgets(window)
    try:
        slots.setCurrentRow(0)
        button.click()
        assert status.text() == "Não foi possível copiar o save."
        assert button.isEnabled()

        button.click()
        rendered = status.text()
        assert "Não foi possível criar o backup" in rendered
        assert "private-token" not in rendered
        assert str(tmp_path) not in rendered
        assert button.isEnabled()
    finally:
        window.close()


def test_refresh_that_removes_selection_disables_backup_action(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    loads = iter(([summary], []))
    window = create_main_window(
        qt_app,
        loader=lambda: list(next(loads)),
        backup_creator=lambda *_args: pytest.fail("não deve criar backup"),
        backup_root=tmp_path / "backups",
    )
    slots, button, status, _root = _widgets(window)
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    assert timer is not None
    try:
        slots.setCurrentRow(0)
        assert button.isEnabled()

        timer.timeout.emit()
        qt_app.processEvents()

        assert slots.count() == 0
        assert not button.isEnabled()
        assert "Selecione" in status.text()
    finally:
        window.close()


def test_default_creator_writes_only_to_injected_temporary_backup_root(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    source_file = summary.slot.path / "player_data.tres"
    source_file.write_text("save sintetico", encoding="utf-8")
    backup_root = tmp_path / "manager" / "backups"
    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_root=backup_root,
    )
    slots, button, status, _root = _widgets(window)
    try:
        slots.setCurrentRow(0)
        button.click()
        qt_app.processEvents()

        created = list(backup_root.iterdir())
        assert len(created) == 1
        assert (created[0] / BACKUP_MANIFEST_FILENAME).is_file()
        assert "criado com sucesso" in status.text()
        assert source_file.read_text(encoding="utf-8") == "save sintetico"
    finally:
        window.close()


def test_inconsistent_manual_failure_clears_stale_backup_selection(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    creator_calls = 0

    class FailedLoadResult:
        validation = DirectoryValidationResult(
            DirectoryValidationCode.VALID,
            summary.slot.path.parent,
        )
        summaries: tuple[SaveSlotSummary, ...] = ()
        is_success = False

    def creator(*_args) -> BackupCreationResult:
        nonlocal creator_calls
        creator_calls += 1
        raise AssertionError("seleção obsoleta não pode criar backup")

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        manual_save_loader=lambda _path: FailedLoadResult(),  # type: ignore[return-value]
        backup_creator=creator,
        backup_root=tmp_path / "backups",
    )
    slots, button, status, _root = _widgets(window)
    load_button = window.findChild(QPushButton, "load_saves_button")
    assert load_button is not None
    try:
        slots.setCurrentRow(0)
        assert button.isEnabled()

        load_button.click()
        qt_app.processEvents()

        assert slots.count() == 0
        assert not button.isEnabled()
        assert "Selecione" in status.text()
        button.click()
        assert creator_calls == 0
    finally:
        window.close()
