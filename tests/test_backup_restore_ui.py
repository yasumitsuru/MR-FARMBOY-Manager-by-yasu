"""Integração UI da restauração confirmada de backups."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from mr_farmboy_manager.backups import (
    BackupDiscoveryResult,
    BackupRecord,
    BackupRestoreResult,
    create_backup,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _summary(tmp_path: Path, slot_number: int = 2) -> SaveSlotSummary:
    slot_path = tmp_path / "game_data" / f"save_{slot_number}"
    slot_path.mkdir(parents=True)
    (slot_path / "player_data.tres").write_bytes(b"active")
    return SaveSlotSummary(SaveSlot(slot_number, slot_path), 1)


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
    button = window.findChild(QPushButton, "restore_backup_button")
    status = window.findChild(QLabel, "backup_management_status_label")
    assert backups is not None and button is not None and status is not None
    return backups, button, status


def test_restore_starts_disabled_and_requires_matching_active_slot(
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
        backup_restorer=lambda *_args, **_kwargs: pytest.fail(
            "não deve restaurar sem slot ativo"
        ),
        restore_confirmer=lambda _record: pytest.fail("não deve confirmar"),
    )
    try:
        backups, button, status = _widgets(window)
        assert not button.isEnabled()

        backups.setCurrentRow(0)
        qt_app.processEvents()

        assert not button.isEnabled()
        assert "Slot 2" in status.text()
        assert "não está disponível" in status.text()
    finally:
        window.close()


def test_confirmation_refusal_never_calls_restore_service(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    root = tmp_path / "backups"
    record = _record(root)
    confirmations: list[BackupRecord] = []
    calls = 0

    def confirmer(candidate: BackupRecord) -> bool:
        confirmations.append(candidate)
        return False

    def restorer(*_args, **_kwargs) -> BackupRestoreResult:
        nonlocal calls
        calls += 1
        raise AssertionError("serviço não deveria ser chamado")

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_restorer=restorer,
        restore_confirmer=confirmer,
    )
    try:
        backups, button, status = _widgets(window)
        backups.setCurrentRow(0)
        assert button.isEnabled()

        button.click()
        qt_app.processEvents()

        assert confirmations == [record]
        assert calls == 0
        assert status.text() == "Restauração cancelada."
        assert button.isEnabled()
    finally:
        window.close()


def test_confirmed_restore_calls_domain_and_refreshes_both_lists(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    root = tmp_path / "backups"
    record = _record(root)
    preventive = BackupRecord(
        backup_id="save_2-20260808T130000Z-" + "b" * 32,
        slot_number=2,
        created_at_utc=datetime(2026, 8, 8, 13, 0, tzinfo=UTC),
        destination=root / ("save_2-20260808T130000Z-" + "b" * 32),
        file_count=1,
        total_size_bytes=6,
    )
    discoveries = iter(
        (
            BackupDiscoveryResult((record,), (), None, "1 backup encontrado."),
            BackupDiscoveryResult(
                (preventive, record), (), None, "2 backups encontrados."
            ),
        )
    )
    save_loads = 0
    received: list[tuple[SaveSlot, Path, Path, str, bool]] = []

    def load_saves() -> list[SaveSlotSummary]:
        nonlocal save_loads
        save_loads += 1
        return [summary]

    def restorer(slot, active_root, backup_root, backup_id, *, confirmed):
        received.append((slot, active_root, backup_root, backup_id, confirmed))
        return BackupRestoreResult(
            record,
            preventive,
            None,
            "Backup restaurado com sucesso.",
        )

    window = create_main_window(
        qt_app,
        loader=load_saves,
        backup_loader=lambda _root: next(discoveries),
        backup_root=root,
        backup_restorer=restorer,
        restore_confirmer=lambda candidate: candidate == record,
    )
    try:
        backups, button, status = _widgets(window)
        backups.setCurrentRow(0)
        button.click()
        qt_app.processEvents()

        assert received == [
            (summary.slot, summary.slot.path.parent, root, record.backup_id, True)
        ]
        assert save_loads == 2
        assert backups.count() == 2
        assert backups.currentRow() == -1
        assert not button.isEnabled()
        assert status.text() == "Backup restaurado com sucesso."
    finally:
        window.close()


def test_restore_exception_is_sanitized_and_keeps_selection(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    root = tmp_path / "backups"
    record = _record(root)
    private_token = f"private-{tmp_path}"

    def restorer(*_args, **_kwargs) -> BackupRestoreResult:
        raise PermissionError(private_token)

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_restorer=restorer,
        restore_confirmer=lambda _record: True,
    )
    try:
        backups, button, status = _widgets(window)
        backups.setCurrentRow(0)
        button.click()

        assert "Não foi possível restaurar" in status.text()
        assert private_token not in status.text()
        assert str(tmp_path) not in status.text()
        assert button.isEnabled()
    finally:
        window.close()


def test_save_refresh_disables_and_reenables_restore_for_matching_slot(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    root = tmp_path / "backups"
    record = _record(root)
    loads = iter(([summary], [], [summary]))
    window = create_main_window(
        qt_app,
        loader=lambda: list(next(loads)),
        backup_loader=lambda _root: BackupDiscoveryResult(
            (record,), (), None, "1 backup encontrado."
        ),
        backup_root=root,
        backup_restorer=lambda *_args, **_kwargs: pytest.fail("não deve restaurar"),
        restore_confirmer=lambda _record: pytest.fail("não deve confirmar"),
    )
    timer = window.findChild(QTimer, "save_auto_refresh_timer")
    assert timer is not None
    try:
        backups, button, status = _widgets(window)
        backups.setCurrentRow(0)
        assert button.isEnabled()

        timer.timeout.emit()
        qt_app.processEvents()

        assert not button.isEnabled()
        assert "não está disponível" in status.text()

        timer.timeout.emit()
        qt_app.processEvents()

        assert button.isEnabled()
        assert "selecionado" in status.text()
    finally:
        window.close()


def test_default_restore_service_changes_only_temporary_active_slot(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    summary = _summary(tmp_path)
    root = tmp_path / "manager" / "backups"
    selected = create_backup(
        summary.slot,
        summary.slot.path.parent,
        root,
        created_at=datetime(2026, 8, 8, 12, 30, tzinfo=UTC),
        suffix="c" * 32,
    )
    assert selected.is_success and selected.backup is not None
    (summary.slot.path / "player_data.tres").write_bytes(b"changed-active")

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_root=root,
        restore_confirmer=lambda _record: True,
    )
    try:
        backups, button, status = _widgets(window)
        backups.setCurrentRow(0)
        button.click()
        qt_app.processEvents()

        assert (summary.slot.path / "player_data.tres").read_bytes() == b"active"
        assert "restaurado" in status.text().lower()
        assert len(list(root.iterdir())) == 2
    finally:
        window.close()
