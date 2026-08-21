"""Dublês QML determinísticos, sem I/O e sem diálogos nativos."""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal, Slot


class FakeSaveSlotsModel(QAbstractListModel):
    """Modelo mínimo que preserva as roles públicas da lista de saves."""

    SlotIdRole = Qt.ItemDataRole.UserRole + 1
    DisplayNameRole = Qt.ItemDataRole.UserRole + 2
    SlotNumberRole = Qt.ItemDataRole.UserRole + 3
    RecordCountRole = Qt.ItemDataRole.UserRole + 4
    PathLabelRole = Qt.ItemDataRole.UserRole + 5
    SelectedRole = Qt.ItemDataRole.UserRole + 6

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[int, object]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.SlotIdRole: b"slotId",
            self.DisplayNameRole: b"displayName",
            self.SlotNumberRole: b"slotNumber",
            self.RecordCountRole: b"recordCount",
            self.PathLabelRole: b"pathLabel",
            self.SelectedRole: b"selected",
        }

    def replace(self, slots: tuple[int, ...]) -> None:
        self.beginResetModel()
        self._rows = [
            {
                self.SlotIdRole: f"save_{number}",
                self.DisplayNameRole: f"Slot {number}",
                self.SlotNumberRole: number,
                self.RecordCountRole: number * 3,
                self.PathLabelRole: f"save_{number}",
                self.SelectedRole: number == slots[0],
            }
            for number in slots
        ]
        self.endResetModel()


class FakeGrowthStatesModel(FakeSaveSlotsModel):
    """Modelo de crescimento com as roles consumidas pelos trilhos QML."""

    def replace_fixture(self, values: tuple[tuple[str, int, int], ...]) -> None:
        self.beginResetModel()
        self._rows = [
            {
                self.SlotIdRole: label,
                self.DisplayNameRole: label,
                self.SlotNumberRole: value,
                self.RecordCountRole: total,
                self.PathLabelRole: label,
                self.SelectedRole: False,
                Qt.ItemDataRole.UserRole + 7: label,
                Qt.ItemDataRole.UserRole + 8: value,
                Qt.ItemDataRole.UserRole + 9: total,
                Qt.ItemDataRole.UserRole + 10: value / total if total else 0.0,
            }
            for label, value, total in values
        ]
        self.endResetModel()

    def roleNames(self) -> dict[int, bytes]:
        return {
            Qt.ItemDataRole.UserRole + 7: b"label",
            Qt.ItemDataRole.UserRole + 8: b"value",
            Qt.ItemDataRole.UserRole + 9: b"total",
            Qt.ItemDataRole.UserRole + 10: b"ratio",
        }


class FakeViewModel(QObject):
    """Superfície extensível para páginas QML, com estado previsível."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._state = "idle"
        self._status_message = ""
        self._error_message = ""

    @Slot()
    def refresh(self) -> None:
        self._state = "ready"
        self.changed.emit()

    state = Property(str, lambda self: self._state, notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)


class FakeDashboardViewModel(QObject):
    """Snapshot de dados reais projetado para a página Dashboard."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._values: dict[str, int | str | bool] = {
            "slotCount": 0,
            "backupCount": 0,
            "selectedSlotLabel": "Não disponível",
            "lastBackupLabel": "Não disponível",
            "lastUpdatedLabel": "10/08/2026 14:30",
            "configurationState": "valid",
            "recordCount": 0,
            "plantedCount": 0,
            "wateredCount": 0,
            "fertilizedCount": 0,
            "maturedCount": 0,
            "harvestableCount": 0,
            "deadCount": 0,
            "hasSelectedSlot": False,
        }
        self._growth_states_model = QObject(self)

    @Slot(int, int)
    def set_fixture_values(self, slot_count: int, planted: int) -> None:
        self._values.update(
            {
                "slotCount": slot_count,
                "recordCount": planted,
                "plantedCount": planted,
                "hasSelectedSlot": planted > 0,
                "selectedSlotLabel": "Slot 1" if planted > 0 else "Não disponível",
            }
        )
        self.changed.emit()

    slotCount = Property(int, lambda self: self._values["slotCount"], notify=changed)
    backupCount = Property(int, lambda self: self._values["backupCount"], notify=changed)
    selectedSlotLabel = Property(str, lambda self: self._values["selectedSlotLabel"], notify=changed)
    lastBackupLabel = Property(str, lambda self: self._values["lastBackupLabel"], notify=changed)
    lastUpdatedLabel = Property(str, lambda self: self._values["lastUpdatedLabel"], notify=changed)
    configurationState = Property(str, lambda self: self._values["configurationState"], notify=changed)
    recordCount = Property(int, lambda self: self._values["recordCount"], notify=changed)
    plantedCount = Property(int, lambda self: self._values["plantedCount"], notify=changed)
    wateredCount = Property(int, lambda self: self._values["wateredCount"], notify=changed)
    fertilizedCount = Property(int, lambda self: self._values["fertilizedCount"], notify=changed)
    maturedCount = Property(int, lambda self: self._values["maturedCount"], notify=changed)
    harvestableCount = Property(int, lambda self: self._values["harvestableCount"], notify=changed)
    deadCount = Property(int, lambda self: self._values["deadCount"], notify=changed)
    hasSelectedSlot = Property(bool, lambda self: self._values["hasSelectedSlot"], notify=changed)
    growthStatesModel = Property(QObject, lambda self: self._growth_states_model, constant=True)


class FakeSaveDetails(QObject):
    changed = Signal()
    recordCount = Property(int, lambda self: 3, constant=True)
    plantedCount = Property(int, lambda self: 2, constant=True)
    wateredCount = Property(int, lambda self: 1, constant=True)
    fertilizedCount = Property(int, lambda self: 1, constant=True)
    maturedCount = Property(int, lambda self: 0, constant=True)
    harvestableCount = Property(int, lambda self: 0, constant=True)
    deadCount = Property(int, lambda self: 0, constant=True)
    inspectedFileCount = Property(int, lambda self: 3, constant=True)
    failedFileCount = Property(int, lambda self: 0, constant=True)
    latestModifiedLabel = Property(str, lambda self: "10/08/2026 14:30", constant=True)
    hasCropProgress = Property(bool, lambda self: True, constant=True)
    hasPlayerProgress = Property(bool, lambda self: False, constant=True)
    growthStatesModel = Property(QObject, lambda self: self._growth_states_model, constant=True)

    def __init__(self) -> None:
        super().__init__()
        self._growth_states_model = FakeGrowthStatesModel()
        self._growth_states_model.replace_fixture((("Plantado", 2, 3), ("Regado", 1, 3)))


class FakeSavesViewModel(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._slots_model = FakeSaveSlotsModel()
        self._details = FakeSaveDetails()
        self.refresh_calls = 0
        self._state = "idle"
        self._status_message = ""
        self._error_message = ""
        self._details_state = "idle"
        self._selected_slot_id = ""
        self._can_create_backup = False

    @Slot()
    def refresh(self) -> None:
        self.refresh_calls += 1
        self._state = "ready"
        self.changed.emit()

    def model_fixture_slots(self, slots: tuple[int, ...]) -> None:
        self._slots_model.replace(slots)
        self._state = "ready" if slots else "empty"
        self._selected_slot_id = f"save_{slots[0]}" if slots else ""
        self._details_state = "ready" if slots else "idle"
        self._can_create_backup = bool(slots)
        self.changed.emit()

    @Slot(str)
    def set_fixture_state(self, state: str) -> None:
        self._state = state
        self._error_message = "Não foi possível carregar os saves." if state == "error" else ""
        self.changed.emit()

    @Slot(str)
    def selectSlot(self, slot_id: str) -> None:
        self._selected_slot_id = slot_id
        self._details_state = "ready"
        self._can_create_backup = bool(slot_id)
        self.changed.emit()

    state = Property(str, lambda self: self._state, notify=changed)
    detailsState = Property(str, lambda self: self._details_state, notify=changed)
    selectedSlotId = Property(str, lambda self: self._selected_slot_id, notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)
    canRefresh = Property(bool, lambda self: self._state != "loading", notify=changed)
    canCreateBackup = Property(bool, lambda self: self._can_create_backup, notify=changed)
    slotsModel = Property(QObject, lambda self: self._slots_model, constant=True)
    details = Property(QObject, lambda self: self._details, constant=True)


class FakeBackupsModel(QAbstractListModel):
    """Lista de backups com as mesmas roles públicas do modelo de produção."""

    BackupIdRole = Qt.ItemDataRole.UserRole + 1
    SlotIdRole = Qt.ItemDataRole.UserRole + 2
    SlotLabelRole = Qt.ItemDataRole.UserRole + 3
    CreatedAtLabelRole = Qt.ItemDataRole.UserRole + 4
    SizeLabelRole = Qt.ItemDataRole.UserRole + 5
    IntegrityLabelRole = Qt.ItemDataRole.UserRole + 6
    SelectedRole = Qt.ItemDataRole.UserRole + 7

    def __init__(self) -> None:
        super().__init__()
        self._rows: list[dict[int, object]] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)

    def roleNames(self) -> dict[int, bytes]:
        return {
            self.BackupIdRole: b"backupId",
            self.SlotIdRole: b"slotId",
            self.SlotLabelRole: b"slotLabel",
            self.CreatedAtLabelRole: b"createdAtLabel",
            self.SizeLabelRole: b"sizeLabel",
            self.IntegrityLabelRole: b"integrityLabel",
            self.SelectedRole: b"selected",
        }

    def replace_fixture(self, backup_ids: tuple[str, ...], selected_id: str = "") -> None:
        self.beginResetModel()
        self._rows = [
            {
                self.BackupIdRole: backup_id,
                self.SlotIdRole: "save_1",
                self.SlotLabelRole: "Slot 1",
                self.CreatedAtLabelRole: "10/08/2026 14:30",
                self.SizeLabelRole: "2,4 MB",
                self.IntegrityLabelRole: "Íntegro",
                self.SelectedRole: backup_id == selected_id,
            }
            for backup_id in backup_ids
        ]
        self.endResetModel()

    def set_selected(self, backup_id: str) -> None:
        for row, values in enumerate(self._rows):
            selected = values[self.BackupIdRole] == backup_id
            if values[self.SelectedRole] != selected:
                values[self.SelectedRole] = selected
                self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [self.SelectedRole])


class FakeBackupsViewModel(QObject):
    """Contrato público do BackupsViewModel, sem I/O ou mutações reais."""

    changed = Signal()
    confirmationRequested = Signal(str, str, str, str)

    def __init__(self) -> None:
        super().__init__()
        self._model = FakeBackupsModel()
        self.confirm_calls: list[tuple[str, str]] = []
        self.cancel_calls = 0
        self.create_calls = 0
        self.refresh_calls = 0
        self.select_calls: list[str] = []
        self._state = "empty"
        self._mutation_state = "idle"
        self._selected_backup_id = ""
        self._status_message = ""
        self._error_message = ""
        self._pending: tuple[str, str] | None = None
        self._has_selected_summary = False

    def model_fixture_backup(self, backup_id: str) -> None:
        self._model.replace_fixture((backup_id,), self._selected_backup_id)
        self._state = "ready"
        self._has_selected_summary = True
        self.changed.emit()

    @Slot(object)
    def setSelectedSummary(self, value: object) -> None:
        self._has_selected_summary = value is not None
        self.changed.emit()

    @Slot(str)
    def selectBackup(self, backup_id: str) -> None:
        if self._locked:
            return
        self.select_calls.append(backup_id)
        self._selected_backup_id = backup_id
        self._model.set_selected(backup_id)
        self.changed.emit()

    @Slot()
    def createForSelectedSlot(self) -> None:
        if not self.canCreate:
            return
        self.create_calls += 1
        self._mutation_state = "creating"
        self.changed.emit()

    @Slot()
    def refresh(self) -> None:
        self.refresh_calls += 1
        self._state = "ready" if self._model.rowCount() else "empty"
        self.changed.emit()

    @Slot()
    def requestRestore(self) -> None:
        self._request(
            "restore",
            "Confirmar restauração",
            "Esta ação substituirá o save ativo após criar um backup preventivo.",
        )

    @Slot()
    def requestDelete(self) -> None:
        self._request(
            "delete",
            "Confirmar exclusão",
            "Esta ação excluirá permanentemente o backup selecionado.",
        )

    def _request(self, action: str, title: str, message: str) -> None:
        if self._locked or not self._selected_backup_id:
            return
        self._pending = action, self._selected_backup_id
        self.changed.emit()
        snapshot_message = (
            f"Slot 1\nBackup: {self._selected_backup_id}\n\n{message}"
        )
        self.confirmationRequested.emit(
            action, self._selected_backup_id, title, snapshot_message
        )

    @Slot(str, str)
    def confirmAction(self, action: str, backup_id: str) -> None:
        self.confirm_calls.append((action, backup_id))
        if self._pending != (action, backup_id):
            return
        self._pending = None
        self._mutation_state = "restoring" if action == "restore" else "deleting"
        self.changed.emit()

    @Slot()
    def cancelConfirmation(self) -> None:
        self.cancel_calls += 1
        self._pending = None
        self.changed.emit()

    @Slot(str)
    def set_fixture_state(self, state: str) -> None:
        self._state = state
        self._mutation_state = state if state in {"creating", "restoring", "deleting"} else "idle"
        self._error_message = "Não foi possível listar os backups." if state == "error" else ""
        self.changed.emit()

    @property
    def _locked(self) -> bool:
        return self._state == "loading" or self._mutation_state != "idle" or self._pending is not None

    state = Property(str, lambda self: self._state, notify=changed)
    mutationState = Property(str, lambda self: self._mutation_state, notify=changed)
    selectedBackupId = Property(str, lambda self: self._selected_backup_id, notify=changed)
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)
    canCreate = Property(bool, lambda self: self._state in {"ready", "empty"} and self._has_selected_summary and not self._locked, notify=changed)
    canRestore = Property(bool, lambda self: self._state == "ready" and bool(self._selected_backup_id) and not self._locked, notify=changed)
    canDelete = Property(bool, lambda self: self._state == "ready" and bool(self._selected_backup_id) and not self._locked, notify=changed)
    backupsModel = Property(QObject, lambda self: self._model, constant=True)


class FakeController(QObject):
    """Controller de composição usado pelo bootstrap QML."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.shutdown_calls = 0
        self.initialize_calls = 0
        self._dashboard = FakeDashboardViewModel()
        self._saves = FakeSavesViewModel()
        self._backups = FakeBackupsViewModel()
        self._settings = FakeViewModel()
        self._diagnostics = FakeViewModel()

    @Slot()
    def initialize(self) -> None:
        self.initialize_calls += 1

    @Slot(result=bool)
    def shutdown(self) -> bool:
        self.shutdown_calls += 1
        return True

    dashboard = Property(QObject, lambda self: self._dashboard, constant=True)
    saves = Property(QObject, lambda self: self._saves, constant=True)
    backups = Property(QObject, lambda self: self._backups, constant=True)
    settings = Property(QObject, lambda self: self._settings, constant=True)
    diagnostics = Property(QObject, lambda self: self._diagnostics, constant=True)
    busy = Property(bool, lambda self: False, constant=True)
