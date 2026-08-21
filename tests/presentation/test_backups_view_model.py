"""Contratos da ponte de backups segura para a interface QML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from mr_farmboy_manager.backups import (
    BackupCreationResult,
    BackupDeletionResult,
    BackupDiscoveryResult,
    BackupErrorCode,
    BackupRecord,
    BackupRestoreResult,
)
from mr_farmboy_manager.presentation.backups_view_model import BackupsViewModel
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary

from .fakes import ControlledOperationRunner


BACKUP_ID = "save_1-20260810T120000Z-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
OTHER_BACKUP_ID = "save_2-20260810T130000Z-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


def backup_record(
    root: Path, backup_id: str = BACKUP_ID, *, slot_number: int = 1
) -> BackupRecord:
    return BackupRecord(
        backup_id=backup_id,
        slot_number=slot_number,
        created_at_utc=datetime(2026, 8, 10, 12, tzinfo=UTC),
        destination=root / backup_id,
        file_count=2,
        total_size_bytes=128,
    )


def discovery_success(record: BackupRecord) -> BackupDiscoveryResult:
    return BackupDiscoveryResult((record,), (), None, "1 backup(s) encontrado(s).")


def create_success(record: BackupRecord) -> BackupCreationResult:
    return BackupCreationResult(record, None, "Backup criado com sucesso.")


def restore_success(record: BackupRecord) -> BackupRestoreResult:
    return BackupRestoreResult(record, None, None, "Backup restaurado com sucesso.")


def delete_success(backup_id: str) -> BackupDeletionResult:
    return BackupDeletionResult(backup_id, None, "Backup excluído com sucesso.")


def ready_backups_vm(
    tmp_path: Path,
    *,
    creator: Mock | None = None,
    loader: Mock | None = None,
    restorer: Mock | None = None,
    deleter: Mock | None = None,
) -> tuple[BackupsViewModel, ControlledOperationRunner, BackupRecord]:
    backup_root = tmp_path / "backups"
    record = backup_record(backup_root)
    runner = ControlledOperationRunner()
    vm = BackupsViewModel(
        runner,
        backup_root,
        creator=creator if creator is not None else Mock(return_value=create_success(record)),
        loader=loader if loader is not None else Mock(return_value=discovery_success(record)),
        restorer=restorer if restorer is not None else Mock(return_value=restore_success(record)),
        deleter=deleter if deleter is not None else Mock(return_value=delete_success(record.backup_id)),
    )
    vm.setSelectedSummary(SaveSlotSummary(SaveSlot(1, tmp_path / "save_1"), 2))
    vm.refresh()
    runner.complete_next()
    return vm, runner, record


def test_restore_requires_matching_confirmation(tmp_path: Path, qapp) -> None:
    restorer = Mock(return_value=restore_success(backup_record(tmp_path / "backups")))
    vm, runner, record = ready_backups_vm(tmp_path, restorer=restorer)
    vm.selectBackup(record.backup_id)

    vm.requestRestore()
    vm.confirmAction("restore", "different-id")

    assert restorer.call_count == 0
    assert vm.mutationState == "idle"
    assert vm.selectedBackupId == record.backup_id
    assert runner._pending == []


def test_confirmation_snapshot_contains_slot_backup_identity_and_consequence(
    tmp_path: Path, qapp
) -> None:
    vm, _runner, record = ready_backups_vm(tmp_path)
    vm.selectBackup(record.backup_id)
    requests: list[tuple[str, str, str, str]] = []
    vm.confirmationRequested.connect(
        lambda action, backup_id, title, message: requests.append(
            (action, backup_id, title, message)
        )
    )

    vm.requestRestore()

    assert requests == [
        (
            "restore",
            record.backup_id,
            "Confirmar restauração",
            f"Slot 1\nBackup: {record.backup_id}\n\n"
            "Esta ação substituirá o save ativo após criar um backup preventivo.",
        )
    ]


def test_delete_runs_confirmed_service(tmp_path: Path, qapp) -> None:
    deleter = Mock(return_value=delete_success(BACKUP_ID))
    vm, runner, record = ready_backups_vm(tmp_path, deleter=deleter)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm.confirmAction("delete", record.backup_id)

    assert vm.mutationState == "deleting"
    assert vm.canCreate is False
    assert vm.canRestore is False
    assert vm.canDelete is False
    runner.complete_next()
    deleter.assert_called_once_with(tmp_path / "backups", record.backup_id, confirmed=True)


def test_create_without_selection_does_not_submit(tmp_path: Path, qapp) -> None:
    creator = Mock()
    vm = BackupsViewModel(ControlledOperationRunner(), tmp_path / "backups", creator=creator)

    vm.createForSelectedSlot()

    assert creator.call_count == 0
    assert vm.mutationState == "idle"
    assert vm.canCreate is False


def test_create_uses_selected_slot_and_enqueues_one_refresh(tmp_path: Path, qapp) -> None:
    record = backup_record(tmp_path / "backups")
    creator = Mock(return_value=create_success(record))
    vm, runner, _ = ready_backups_vm(tmp_path, creator=creator)

    vm.createForSelectedSlot()
    runner.complete_next()

    creator.assert_called_once_with(
        SaveSlot(1, tmp_path / "save_1"), tmp_path, tmp_path / "backups"
    )
    assert vm.mutationState == "idle"
    assert len(runner._pending) == 1


def test_restore_uses_confirmation_snapshot_after_selection_changes(
    tmp_path: Path, qapp
) -> None:
    backup_root = tmp_path / "backups"
    original = backup_record(backup_root)
    other = backup_record(backup_root, OTHER_BACKUP_ID, slot_number=2)
    loader = Mock(
        return_value=BackupDiscoveryResult(
            (original, other), (), None, "2 backup(s) encontrado(s)."
        )
    )
    restorer = Mock(return_value=restore_success(original))
    vm, runner, record = ready_backups_vm(
        tmp_path, loader=loader, restorer=restorer
    )
    vm.selectBackup(record.backup_id)

    vm.requestRestore()
    vm.setSelectedSummary(SaveSlotSummary(SaveSlot(2, tmp_path / "save_2"), 1))
    vm._selected_backup_id = other.backup_id
    vm._backups_model.set_selected(other.backup_id)
    vm.confirmAction("restore", record.backup_id)
    vm.confirmAction("restore", record.backup_id)

    assert vm._pending_confirmation is None
    assert len(runner._pending) == 1
    runner.complete_next()

    restorer.assert_called_once_with(
        SaveSlot(1, tmp_path / "save_1"),
        tmp_path,
        backup_root,
        record.backup_id,
        confirmed=True,
    )
    assert len(runner._pending) == 1


def test_delete_uses_confirmation_snapshot_after_selection_changes(
    tmp_path: Path, qapp
) -> None:
    backup_root = tmp_path / "backups"
    original = backup_record(backup_root)
    other = backup_record(backup_root, OTHER_BACKUP_ID, slot_number=2)
    loader = Mock(
        return_value=BackupDiscoveryResult(
            (original, other), (), None, "2 backup(s) encontrado(s)."
        )
    )
    deleter = Mock(return_value=delete_success(original.backup_id))
    vm, runner, record = ready_backups_vm(tmp_path, loader=loader, deleter=deleter)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm._selected_backup_id = other.backup_id
    vm._backups_model.set_selected(other.backup_id)
    vm.confirmAction("delete", record.backup_id)
    vm.confirmAction("delete", record.backup_id)

    assert vm._pending_confirmation is None
    assert len(runner._pending) == 1
    runner.complete_next()

    deleter.assert_called_once_with(backup_root, record.backup_id, confirmed=True)
    assert len(runner._pending) == 1


def test_confirmation_rejects_backup_removed_after_request(tmp_path: Path, qapp) -> None:
    deleter = Mock()
    vm, runner, record = ready_backups_vm(tmp_path, deleter=deleter)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm._backups = ()
    vm._backups_model.replace(())
    vm.confirmAction("delete", record.backup_id)

    assert deleter.call_count == 0
    assert runner._pending == []


def test_discovery_error_exposes_only_public_message(tmp_path: Path, qapp) -> None:
    record = backup_record(tmp_path / "backups")
    loader = Mock(
        return_value=BackupDiscoveryResult(
            (), (), BackupErrorCode.DISCOVERY_FAILED, "Não foi possível listar os backups."
        )
    )
    runner = ControlledOperationRunner()
    vm = BackupsViewModel(runner, tmp_path / "backups", loader=loader)

    vm.refresh()
    runner.complete_next()

    assert vm.state == "error"
    assert vm.errorMessage == "Não foi possível listar os backups."
    assert vm.backupsModel.rowCount() == 0
    assert record.backup_id not in vm.errorMessage


def test_failed_mutation_preserves_selection(tmp_path: Path, qapp) -> None:
    record = backup_record(tmp_path / "backups")
    deleter = Mock(
        return_value=BackupDeletionResult(
            None, BackupErrorCode.DELETE_FAILED, "Não foi possível excluir o backup."
        )
    )
    vm, runner, _ = ready_backups_vm(tmp_path, deleter=deleter)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm.confirmAction("delete", record.backup_id)
    runner.complete_next()

    assert vm.mutationState == "idle"
    assert vm.selectedBackupId == record.backup_id
    assert vm.errorMessage == "Não foi possível excluir o backup."
    assert runner._pending == []


def test_successful_cleanup_pending_delete_refreshes_once(tmp_path: Path, qapp) -> None:
    record = backup_record(tmp_path / "backups")
    loader = Mock(return_value=discovery_success(record))
    deleter = Mock(
        return_value=BackupDeletionResult(
            record.backup_id,
            BackupErrorCode.DELETE_CLEANUP_PENDING,
            "O backup foi excluído, mas uma limpeza temporária ficou pendente.",
            cleanup_pending=True,
        )
    )
    vm, runner, _ = ready_backups_vm(tmp_path, loader=loader, deleter=deleter)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm.confirmAction("delete", record.backup_id)
    runner.complete_next()

    assert vm.mutationState == "idle"
    assert vm.statusMessage == "O backup foi excluído, mas uma limpeza temporária ficou pendente."
    assert len(runner._pending) == 1
    runner.complete_next()
    assert loader.call_count == 2
    assert vm.statusMessage == "O backup foi excluído, mas uma limpeza temporária ficou pendente."


def test_runner_failure_uses_sanitized_public_message_and_preserves_selection(
    tmp_path: Path, qapp
) -> None:
    vm, runner, record = ready_backups_vm(tmp_path)
    vm.selectBackup(record.backup_id)

    vm.requestDelete()
    vm.confirmAction("delete", record.backup_id)
    runner.fail_next("Não foi possível concluir a operação.")

    assert vm.mutationState == "idle"
    assert vm.selectedBackupId == record.backup_id
    assert vm.errorMessage == "Não foi possível concluir a operação."
