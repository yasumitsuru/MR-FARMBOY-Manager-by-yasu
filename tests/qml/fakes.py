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


class FakeController(QObject):
    """Controller de composição usado pelo bootstrap QML."""

    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.shutdown_calls = 0
        self.initialize_calls = 0
        self._dashboard = FakeDashboardViewModel()
        self._saves = FakeSavesViewModel()
        self._backups = FakeViewModel()
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
