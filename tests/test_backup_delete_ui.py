"""Integração UI da exclusão confirmada de backups."""

from __future__ import annotations

from datetime import UTC, datetime
import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
)

from mr_farmboy_manager.backups import (
    BackupDeletionResult,
    BackupDiscoveryResult,
    BackupErrorCode,
    BackupRecord,
    create_backup,
)
from mr_farmboy_manager.save_slots import SaveSlot


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _record(root: Path, slot_number: int = 2) -> BackupRecord:
    backup_id = f"save_{slot_number}-20260808T123000Z-" + "a" * 32
    return BackupRecord(
        backup_id=backup_id,
        slot_number=slot_number,
        created_at_utc=datetime(2026, 8, 8, 12, 30, tzinfo=UTC),
        destination=root / backup_id,
        file_count=1,
        total_size_bytes=2048,
    )


def _widgets(window):
    backups = window.findChild(QListWidget, "backups_list")
    delete_button = window.findChild(QPushButton, "delete_backup_button")
    restore_button = window.findChild(QPushButton, "restore_backup_button")
    status = window.findChild(QLabel, "backup_management_status_label")
    assert (
        backups is not None
        and delete_button is not None
        and restore_button is not None
        and status is not None
    )
    return backups, delete_button, restore_button, status


def test_delete_starts_disabled_and_selection_enables_without_active_slot(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_deleter=lambda *_args, **_kwargs: pytest.fail("não deve excluir"),
        delete_confirmer=lambda _record: pytest.fail("não deve confirmar"),
    )
    try:
        backups, delete_button, restore_button, status = _widgets(window)
        assert not delete_button.isEnabled()

        backups.setCurrentRow(0)
        qt_app.processEvents()

        assert delete_button.isEnabled()
        assert not restore_button.isEnabled()
        assert "Slot 2" in status.text()
    finally:
        window.close()


def test_default_delete_confirmation_shows_identity_and_defaults_to_no(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    observed: list[tuple[str, str, object, object]] = []

    def warning(_parent, title, message, buttons, default_button):
        observed.append((title, message, buttons, default_button))
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "warning", warning)
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_deleter=lambda *_args, **_kwargs: pytest.fail("não deve excluir"),
    )
    try:
        backups, delete_button, _restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()

        assert len(observed) == 1
        title, message, buttons, default_button = observed[0]
        assert title == "Confirmar exclusão"
        assert "Slot: 2" in message
        assert "2026-08-08 12:30 UTC" in message
        assert "2,0 KiB" in message
        assert record.backup_id in message
        assert buttons == (
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        assert default_button == QMessageBox.StandardButton.No
        assert status.text() == "Exclusão cancelada."
        assert delete_button.isEnabled()
    finally:
        window.close()


def test_confirmation_refusal_never_calls_delete_service(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    confirmations: list[BackupRecord] = []

    def confirmer(candidate: BackupRecord) -> bool:
        confirmations.append(candidate)
        return False

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_deleter=lambda *_args, **_kwargs: pytest.fail("não deve excluir"),
        delete_confirmer=confirmer,
    )
    try:
        backups, delete_button, _restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()

        assert confirmations == [record]
        assert status.text() == "Exclusão cancelada."
        assert delete_button.isEnabled()
    finally:
        window.close()


def test_confirmed_delete_calls_domain_and_refreshes_backup_list(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    discoveries = iter(
        (
            BackupDiscoveryResult((record,), (), None, "1 backup encontrado."),
            BackupDiscoveryResult((), (), None, "Nenhum backup encontrado."),
        )
    )
    received: list[tuple[Path, str, bool]] = []

    def deleter(backup_root, backup_id, *, confirmed):
        received.append((backup_root, backup_id, confirmed))
        return BackupDeletionResult(
            record.backup_id,
            None,
            "Backup excluído com sucesso.",
        )

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: next(discoveries),
        backup_root=root,
        backup_deleter=deleter,
        delete_confirmer=lambda candidate: candidate == record,
    )
    try:
        backups, delete_button, restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()
        qt_app.processEvents()

        assert received == [(root, record.backup_id, True)]
        assert backups.count() == 0
        assert backups.currentRow() == -1
        assert not delete_button.isEnabled()
        assert not restore_button.isEnabled()
        assert status.text() == "Backup excluído com sucesso."
    finally:
        window.close()


def test_delete_failure_preserves_selection_and_reenables_action(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_deleter=lambda *_args, **_kwargs: BackupDeletionResult(
            None,
            BackupErrorCode.DELETE_FAILED,
            "Não foi possível excluir o backup.",
        ),
        delete_confirmer=lambda _record: True,
    )
    try:
        backups, delete_button, _restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()

        assert backups.currentRow() == 0
        assert delete_button.isEnabled()
        assert status.text() == "Não foi possível excluir o backup."
    finally:
        window.close()


def test_delete_exception_is_sanitized_and_keeps_selection(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    root = tmp_path / "backups"
    record = _record(root)
    private_token = f"private-{tmp_path}"

    def deleter(*_args, **_kwargs) -> BackupDeletionResult:
        raise PermissionError(private_token)

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_deleter=deleter,
        delete_confirmer=lambda _record: True,
    )
    try:
        backups, delete_button, _restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()

        assert backups.currentRow() == 0
        assert delete_button.isEnabled()
        assert status.text() == "Não foi possível excluir o backup."
        assert private_token not in status.text()
        assert str(tmp_path) not in status.text()
    finally:
        window.close()


@pytest.mark.skipif(os.name != "nt", reason="exclusão segura implementada no Win32")
def test_default_delete_service_changes_only_temporary_backup_root(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    game_data = tmp_path / "game_data"
    slot_path = game_data / "save_1"
    slot_path.mkdir(parents=True)
    (slot_path / "player_data.tres").write_bytes(b"active")
    root = tmp_path / "manager" / "backups"
    created = create_backup(
        SaveSlot(1, slot_path),
        game_data,
        root,
        created_at=datetime(2026, 8, 8, 12, 30, tzinfo=UTC),
        suffix="d" * 32,
    )
    assert created.is_success and created.backup is not None

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_root=root,
        delete_confirmer=lambda _record: True,
    )
    try:
        backups, delete_button, _restore_button, status = _widgets(window)
        backups.setCurrentRow(0)
        delete_button.click()
        qt_app.processEvents()

        assert not created.backup.destination.exists()
        assert backups.count() == 0
        assert "excluído" in status.text().lower()
        assert (slot_path / "player_data.tres").read_bytes() == b"active"
    finally:
        window.close()
