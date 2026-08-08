"""Listagem de backups persistentes na interface principal."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QListWidget, QPushButton

from mr_farmboy_manager.backups import (
    BackupCreationResult,
    BackupDiscoveryResult,
    BackupErrorCode,
    BackupRecord,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    app = QApplication.instance()
    return app if app is not None else QApplication([])


def _record(
    root: Path,
    *,
    slot_number: int,
    hour: int,
    suffix: str,
    file_count: int = 2,
    total_size_bytes: int = 4096,
) -> BackupRecord:
    created_at = datetime(2026, 8, 8, hour, 30, tzinfo=UTC)
    backup_id = (
        f"save_{slot_number}-20260808T{hour:02d}3000Z-" + suffix * 32
    )
    return BackupRecord(
        backup_id=backup_id,
        slot_number=slot_number,
        created_at_utc=created_at,
        destination=root / backup_id,
        file_count=file_count,
        total_size_bytes=total_size_bytes,
    )


def _backup_widgets(window):
    backups = window.findChild(QListWidget, "backups_list")
    empty = window.findChild(QLabel, "empty_backups_label")
    status = window.findChild(QLabel, "backup_list_status_label")
    assert backups is not None and empty is not None and status is not None
    return backups, empty, status


def test_empty_backup_discovery_has_explicit_state(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    backup_root = tmp_path / "backups"
    received: list[Path] = []

    def loader(root: Path) -> BackupDiscoveryResult:
        received.append(root)
        return BackupDiscoveryResult((), (), None, "Nenhum backup encontrado.")

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=loader,
        backup_root=backup_root,
    )
    try:
        backups, empty, status = _backup_widgets(window)

        assert received == [backup_root]
        assert backups.count() == 0
        assert backups.isHidden()
        assert not empty.isHidden()
        assert empty.text() == "Nenhum backup criado"
        assert status.text() == "Nenhum backup encontrado."
    finally:
        window.close()


def test_multiple_backups_show_slot_time_size_and_clear_id(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    backup_root = tmp_path / "backups"
    newest = _record(backup_root, slot_number=2, hour=15, suffix="b")
    older = _record(
        backup_root,
        slot_number=1,
        hour=10,
        suffix="a",
        file_count=1,
        total_size_bytes=512,
    )
    result = BackupDiscoveryResult(
        (newest, older),
        ("entrada-quebrada",),
        None,
        "2 backup(s) encontrado(s). 1 entrada(s) inválida(s) ignorada(s).",
    )
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: result,
        backup_root=backup_root,
    )
    try:
        backups, empty, status = _backup_widgets(window)

        assert backups.count() == 2
        assert not backups.isHidden()
        assert empty.isHidden()
        first = backups.item(0).text()
        second = backups.item(1).text()
        assert first.startswith("Backup — Slot 2")
        assert "2026-08-08 15:30 UTC" in first
        assert "2 arquivos" in first
        assert "4,0 KiB" in first
        assert f"ID: {newest.backup_id}" in first
        assert second.startswith("Backup — Slot 1")
        assert "1 arquivo" in second
        assert "512 B" in second
        assert f"ID: {older.backup_id}" in second
        assert "1 entrada(s) inválida(s)" in status.text()
        assert "entrada-quebrada" not in status.text()
    finally:
        window.close()


def test_backup_discovery_exception_is_sanitized(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    private_token = f"segredo-{tmp_path}"

    def loader(_root: Path) -> BackupDiscoveryResult:
        raise PermissionError(private_token)

    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=loader,
        backup_root=tmp_path / "backups",
    )
    try:
        backups, empty, status = _backup_widgets(window)

        assert backups.count() == 0
        assert empty.text() == "Backups indisponíveis"
        assert status.text() == "Não foi possível listar os backups."
        assert private_token not in status.text()
        assert str(tmp_path) not in status.text()
    finally:
        window.close()


def test_successful_creation_refreshes_backup_list_immediately(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    save_path = tmp_path / "game_data" / "save_4"
    save_path.mkdir(parents=True)
    summary = SaveSlotSummary(SaveSlot(4, save_path), 1)
    backup_root = tmp_path / "backups"
    created = _record(backup_root, slot_number=4, hour=16, suffix="c")
    discoveries = iter(
        (
            BackupDiscoveryResult((), (), None, "Nenhum backup encontrado."),
            BackupDiscoveryResult((created,), (), None, "1 backup(s) encontrado(s)."),
        )
    )
    loads: list[Path] = []

    def backup_loader(root: Path) -> BackupDiscoveryResult:
        loads.append(root)
        return next(discoveries)

    window = create_main_window(
        qt_app,
        loader=lambda: [summary],
        backup_creator=lambda *_args: BackupCreationResult(
            created,
            None,
            "Backup criado com sucesso.",
        ),
        backup_loader=backup_loader,
        backup_root=backup_root,
    )
    slots = window.findChild(QListWidget, "save_slots_list")
    button = window.findChild(QPushButton, "create_backup_button")
    assert slots is not None and button is not None
    try:
        backups, empty, status = _backup_widgets(window)
        assert backups.count() == 0

        slots.setCurrentRow(0)
        button.click()
        qt_app.processEvents()

        assert loads == [backup_root, backup_root]
        assert backups.count() == 1
        assert empty.isHidden()
        assert created.backup_id in backups.item(0).text()
        assert status.text() == "1 backup(s) encontrado(s)."
    finally:
        window.close()


def test_failed_discovery_result_uses_safe_empty_state(
    qt_app: QApplication, tmp_path: Path
) -> None:
    from mr_farmboy_manager.application import create_main_window

    result = BackupDiscoveryResult(
        (),
        (),
        BackupErrorCode.DISCOVERY_FAILED,
        "Não foi possível listar os backups.",
    )
    window = create_main_window(
        qt_app,
        loader=lambda: [],
        backup_loader=lambda _root: result,
        backup_root=tmp_path / "backups",
    )
    try:
        backups, empty, status = _backup_widgets(window)
        assert backups.count() == 0
        assert empty.text() == "Backups indisponíveis"
        assert status.text() == result.public_message
    finally:
        window.close()
