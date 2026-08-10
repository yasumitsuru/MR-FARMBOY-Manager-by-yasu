"""Modelo QML dos slots de save descobertos."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from mr_farmboy_manager.save_slots import SaveSlotSummary


class SaveSlotsModel(QAbstractListModel):
    SlotIdRole = Qt.UserRole + 1
    DisplayNameRole = Qt.UserRole + 2
    SlotNumberRole = Qt.UserRole + 3
    RecordCountRole = Qt.UserRole + 4
    PathLabelRole = Qt.UserRole + 5
    SelectedRole = Qt.UserRole + 6

    _ROLE_NAMES = {
        SlotIdRole: b"slotId",
        DisplayNameRole: b"displayName",
        SlotNumberRole: b"slotNumber",
        RecordCountRole: b"recordCount",
        PathLabelRole: b"pathLabel",
        SelectedRole: b"selected",
    }

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[SaveSlotSummary, ...] = ()
        self._rows: tuple[dict[int, object], ...] = ()
        self._selected_id: str | None = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES

    def replace(self, summaries: Sequence[SaveSlotSummary]) -> None:
        self.beginResetModel()
        self._items = tuple(summaries)
        known_ids = {summary.slot.name for summary in self._items}
        if self._selected_id not in known_ids:
            self._selected_id = None
        self._rows = tuple(self._row_for(summary) for summary in self._items)
        self.endResetModel()

    def set_selected(self, slot_id: str | None) -> None:
        if slot_id == self._selected_id:
            return
        self._selected_id = slot_id
        rows = list(self._rows)
        changed_rows: list[int] = []
        for row, values in enumerate(rows):
            is_selected = values[self.SlotIdRole] == slot_id
            if values[self.SelectedRole] == is_selected:
                continue
            updated = dict(values)
            updated[self.SelectedRole] = is_selected
            rows[row] = updated
            changed_rows.append(row)

        self._rows = tuple(rows)
        for row in changed_rows:
            self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [self.SelectedRole])

    def _row_for(self, summary: SaveSlotSummary) -> dict[int, object]:
        slot = summary.slot
        return {
            self.SlotIdRole: slot.name,
            self.DisplayNameRole: f"Slot {slot.number}",
            self.SlotNumberRole: slot.number,
            self.RecordCountRole: summary.tres_file_count,
            self.PathLabelRole: slot.path.name,
            self.SelectedRole: slot.name == self._selected_id,
        }
