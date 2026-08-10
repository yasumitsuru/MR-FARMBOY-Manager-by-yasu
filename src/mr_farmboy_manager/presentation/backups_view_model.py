"""Ponte segura de operações de backup para consumo direto pelo QML."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot

from mr_farmboy_manager.backups import (
    BackupCreationResult,
    BackupDeletionResult,
    BackupDiscoveryResult,
    BackupRecord,
    BackupRestoreResult,
    create_backup,
    delete_backup,
    discover_backups,
    restore_backup,
)
from mr_farmboy_manager.save_slots import SaveSlotSummary

from .backups_model import BackupsModel
from .operation_runner import OperationRunner


_PUBLIC_FAILURE_MESSAGE = "Não foi possível concluir a operação."


class BackupsViewModel(QObject):
    """Coordena descoberta e mutações de backups sem expor caminhos ao QML."""

    changed = Signal()
    confirmationRequested = Signal(str, str, str, str)

    def __init__(
        self,
        runner: OperationRunner,
        backup_root: Path,
        *,
        creator: Callable[..., BackupCreationResult] = create_backup,
        loader: Callable[[Path], BackupDiscoveryResult] = discover_backups,
        restorer: Callable[..., BackupRestoreResult] = restore_backup,
        deleter: Callable[..., BackupDeletionResult] = delete_backup,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._backup_root = backup_root
        self._creator = creator
        self._loader = loader
        self._restorer = restorer
        self._deleter = deleter
        self._backups_model = BackupsModel(self)
        self._backups: tuple[BackupRecord, ...] = ()
        self._selected_summary: SaveSlotSummary | None = None
        self._selected_backup_id = ""
        self._state = "idle"
        self._mutation_state = "idle"
        self._status_message = ""
        self._error_message = ""
        self._refresh_request: int | None = None
        self._refresh_generation = 0
        self._refresh_keeps_status = False
        self._mutation_request: int | None = None
        self._mutation_context: tuple[str, str] | None = None
        self._pending_confirmation: tuple[str, str] | None = None
        runner.succeeded.connect(self._operation_succeeded)
        runner.failed.connect(self._operation_failed)

    @Slot(object)
    def setSelectedSummary(self, value: object) -> None:
        summary = value if isinstance(value, SaveSlotSummary) else None
        if summary == self._selected_summary:
            return
        before = self._public_values()
        self._selected_summary = summary
        self._notify_if_changed(before)

    @Slot()
    def refresh(self) -> None:
        self._start_refresh(clear_messages=True)

    def _start_refresh(self, *, clear_messages: bool) -> None:
        if self._refresh_request is not None or self._is_locked:
            return
        before = self._public_values()
        self._refresh_generation += 1
        generation = self._refresh_generation
        self._refresh_keeps_status = not clear_messages
        self._set_values(
            state="loading",
            **({"status_message": "", "error_message": ""} if clear_messages else {}),
        )
        self._refresh_request = self._runner.submit(
            f"backups.refresh:{generation}", lambda: self._loader(self._backup_root)
        )
        self._notify_if_changed(before)

    @Slot(str)
    def selectBackup(self, backup_id: str) -> None:
        if self._is_locked:
            return
        record = self._backup_for(backup_id)
        selected_id = record.backup_id if record is not None else ""
        if selected_id == self._selected_backup_id:
            return
        before = self._public_values()
        self._selected_backup_id = selected_id
        self._backups_model.set_selected(selected_id or None)
        self._notify_if_changed(before)

    @Slot()
    def createForSelectedSlot(self) -> None:
        if self._is_locked or self._selected_summary is None:
            return
        summary = self._selected_summary
        self._submit_mutation(
            "create",
            "",
            lambda: self._creator(summary.slot, summary.slot.path.parent, self._backup_root),
        )

    @Slot()
    def requestRestore(self) -> None:
        record = self._selected_record
        if self._is_locked or record is None or self._summary_for(record) is None:
            return
        self._request_confirmation(
            "restore",
            record,
            "Confirmar restauração",
            "Esta ação substituirá o save ativo após criar um backup preventivo.",
        )

    @Slot()
    def requestDelete(self) -> None:
        record = self._selected_record
        if self._is_locked or record is None:
            return
        self._request_confirmation(
            "delete",
            record,
            "Confirmar exclusão",
            "Esta ação excluirá permanentemente o backup selecionado.",
        )

    @Slot(str, str)
    def confirmAction(self, action: str, backup_id: str) -> None:
        pending = self._pending_confirmation
        if pending != (action, backup_id):
            return
        record = self._backup_for(backup_id)
        if record is None or self._selected_backup_id != backup_id:
            self._clear_confirmation()
            return
        if action == "restore":
            summary = self._summary_for(record)
            if summary is None:
                self._clear_confirmation()
                return
            self._clear_confirmation()
            self._submit_mutation(
                "restore",
                backup_id,
                lambda: self._restorer(
                    summary.slot,
                    summary.slot.path.parent,
                    self._backup_root,
                    backup_id,
                    confirmed=True,
                ),
            )
            return
        if action == "delete":
            self._clear_confirmation()
            self._submit_mutation(
                "delete",
                backup_id,
                lambda: self._deleter(self._backup_root, backup_id, confirmed=True),
            )
            return
        self._clear_confirmation()

    @Slot()
    def cancelConfirmation(self) -> None:
        if self._pending_confirmation is None:
            return
        before = self._public_values()
        self._clear_confirmation()
        self._set_values(status_message="Ação cancelada.", error_message="")
        self._notify_if_changed(before)

    def _request_confirmation(
        self, action: str, record: BackupRecord, title: str, message: str
    ) -> None:
        before = self._public_values()
        self._pending_confirmation = action, record.backup_id
        self._notify_if_changed(before)
        self.confirmationRequested.emit(action, record.backup_id, title, message)

    def _submit_mutation(
        self, action: str, backup_id: str, work: Callable[[], object]
    ) -> None:
        if self._mutation_request is not None or self._refresh_request is not None:
            return
        before = self._public_values()
        self._set_values(
            mutation_state={"create": "creating", "restore": "restoring", "delete": "deleting"}[action],
            status_message="",
            error_message="",
        )
        self._mutation_request = self._runner.submit(f"backups.{action}:{backup_id}", work)
        self._mutation_context = action, backup_id
        self._notify_if_changed(before)

    @Slot(int, str, object)
    def _operation_succeeded(self, request_id: int, name: str, value: object) -> None:
        if request_id == self._refresh_request and name == f"backups.refresh:{self._refresh_generation}":
            before = self._public_values()
            self._refresh_request = None
            keeps_status = self._refresh_keeps_status
            self._refresh_keeps_status = False
            self._apply_discovery(value, keeps_status=keeps_status)
            self._notify_if_changed(before)
            return
        if request_id != self._mutation_request or self._mutation_context is None:
            return
        action, backup_id = self._mutation_context
        if name != f"backups.{action}:{backup_id}":
            return
        before = self._public_values()
        self._mutation_request = None
        self._mutation_context = None
        self._set_values(mutation_state="idle")
        if self._mutation_succeeded(action, value):
            self._set_values(status_message=value.public_message, error_message="")
            self._notify_if_changed(before)
            self._start_refresh(clear_messages=False)
            return
        self._set_values(
            status_message="",
            error_message=value.public_message if self._is_mutation_result(value) else _PUBLIC_FAILURE_MESSAGE,
        )
        self._notify_if_changed(before)

    @Slot(int, str, str)
    def _operation_failed(self, request_id: int, name: str, public_message: str) -> None:
        if request_id == self._refresh_request and name == f"backups.refresh:{self._refresh_generation}":
            before = self._public_values()
            self._refresh_request = None
            self._set_values(state="error", status_message="", error_message=public_message)
            self._notify_if_changed(before)
            return
        if request_id != self._mutation_request or self._mutation_context is None:
            return
        action, backup_id = self._mutation_context
        if name != f"backups.{action}:{backup_id}":
            return
        before = self._public_values()
        self._mutation_request = None
        self._mutation_context = None
        self._set_values(
            mutation_state="idle", status_message="", error_message=public_message
        )
        self._notify_if_changed(before)

    def _apply_discovery(self, value: object, *, keeps_status: bool) -> None:
        if not isinstance(value, BackupDiscoveryResult) or not value.is_success:
            self._backups = ()
            self._selected_backup_id = ""
            self._backups_model.replace(())
            self._set_values(
                state="error", status_message="", error_message="Não foi possível listar os backups."
            )
            return
        self._backups = value.backups
        if self._backup_for(self._selected_backup_id) is None:
            self._selected_backup_id = ""
        self._backups_model.replace(self._backups)
        self._backups_model.set_selected(self._selected_backup_id or None)
        self._set_values(state="ready" if self._backups else "empty", error_message="")
        if not keeps_status:
            self._set_values(status_message=value.public_message)

    def _mutation_succeeded(self, action: str, value: object) -> bool:
        expected = {
            "create": BackupCreationResult,
            "restore": BackupRestoreResult,
            "delete": BackupDeletionResult,
        }[action]
        return isinstance(value, expected) and value.is_success

    @staticmethod
    def _is_mutation_result(value: object) -> bool:
        return isinstance(value, (BackupCreationResult, BackupRestoreResult, BackupDeletionResult))

    @property
    def _selected_record(self) -> BackupRecord | None:
        return self._backup_for(self._selected_backup_id)

    def _backup_for(self, backup_id: str) -> BackupRecord | None:
        return next((record for record in self._backups if record.backup_id == backup_id), None)

    def _summary_for(self, record: BackupRecord) -> SaveSlotSummary | None:
        summary = self._selected_summary
        if summary is not None and summary.slot.number == record.slot_number:
            return summary
        return None

    def _clear_confirmation(self) -> None:
        self._pending_confirmation = None

    @property
    def _is_locked(self) -> bool:
        return (
            self._refresh_request is not None
            or self._mutation_request is not None
            or self._pending_confirmation is not None
        )

    def _set_values(self, **values: str) -> None:
        for name, value in values.items():
            attribute = f"_{name}"
            if getattr(self, attribute) != value:
                setattr(self, attribute, value)

    def _public_values(self) -> tuple[str, str, str, str, str, bool, bool, bool]:
        return (
            self._state,
            self._mutation_state,
            self._selected_backup_id,
            self._status_message,
            self._error_message,
            self.canCreate,
            self.canRestore,
            self.canDelete,
        )

    def _notify_if_changed(self, before: tuple[str, str, str, str, str, bool, bool, bool]) -> None:
        if self._public_values() != before:
            self.changed.emit()

    state = Property(str, lambda self: self._state, notify=changed)
    mutationState = Property(str, lambda self: self._mutation_state, notify=changed)
    selectedBackupId = Property(str, lambda self: self._selected_backup_id, notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)
    canCreate = Property(
        bool,
        lambda self: self._state in {"ready", "empty"}
        and self._selected_summary is not None
        and not self._is_locked,
        notify=changed,
    )
    canRestore = Property(
        bool,
        lambda self: self._state == "ready"
        and self._selected_record is not None
        and self._summary_for(self._selected_record) is not None
        and not self._is_locked,
        notify=changed,
    )
    canDelete = Property(
        bool,
        lambda self: self._state == "ready" and self._selected_record is not None and not self._is_locked,
        notify=changed,
    )
    backupsModel = Property(QObject, lambda self: self._backups_model, constant=True)


__all__ = ["BackupsViewModel"]
