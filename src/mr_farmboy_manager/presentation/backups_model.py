"""Modelo QML dos backups descobertos."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from mr_farmboy_manager.backups import BackupRecord

from .formatters import format_created_at_label, format_size_label


class BackupsModel(QAbstractListModel):
    BackupIdRole = Qt.UserRole + 1
    SlotIdRole = Qt.UserRole + 2
    SlotLabelRole = Qt.UserRole + 3
    CreatedAtLabelRole = Qt.UserRole + 4
    SizeLabelRole = Qt.UserRole + 5
    IntegrityLabelRole = Qt.UserRole + 6
    SelectedRole = Qt.UserRole + 7

    _ROLE_NAMES = {
        BackupIdRole: b"backupId",
        SlotIdRole: b"slotId",
        SlotLabelRole: b"slotLabel",
        CreatedAtLabelRole: b"createdAtLabel",
        SizeLabelRole: b"sizeLabel",
        IntegrityLabelRole: b"integrityLabel",
        SelectedRole: b"selected",
    }

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[BackupRecord, ...] = ()
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

    def replace(self, backups: Sequence[BackupRecord]) -> None:
        self.beginResetModel()
        self._items = tuple(backups)
        known_ids = {backup.backup_id for backup in self._items}
        if self._selected_id not in known_ids:
            self._selected_id = None
        self._rows = tuple(self._row_for(backup) for backup in self._items)
        self.endResetModel()

    def set_selected(self, backup_id: str | None) -> None:
        if backup_id == self._selected_id:
            return
        self._selected_id = backup_id
        rows = list(self._rows)
        changed_rows: list[int] = []
        for row, values in enumerate(rows):
            is_selected = values[self.BackupIdRole] == backup_id
            if values[self.SelectedRole] == is_selected:
                continue
            updated = dict(values)
            updated[self.SelectedRole] = is_selected
            rows[row] = updated
            changed_rows.append(row)

        self._rows = tuple(rows)
        for row in changed_rows:
            self.dataChanged.emit(self.index(row, 0), self.index(row, 0), [self.SelectedRole])

    def _row_for(self, backup: BackupRecord) -> dict[int, object]:
        return {
            self.BackupIdRole: backup.backup_id,
            self.SlotIdRole: f"save_{backup.slot_number}",
            self.SlotLabelRole: f"Slot {backup.slot_number}",
            self.CreatedAtLabelRole: format_created_at_label(backup.created_at_utc),
            self.SizeLabelRole: format_size_label(backup.total_size_bytes),
            self.IntegrityLabelRole: "Íntegro",
            self.SelectedRole: backup.backup_id == self._selected_id,
        }
