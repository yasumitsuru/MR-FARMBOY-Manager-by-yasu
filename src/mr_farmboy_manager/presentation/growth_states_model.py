"""Modelo QML da distribuição de estados de crescimento."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt


class GrowthStatesModel(QAbstractListModel):
    LabelRole = Qt.UserRole + 1
    ValueRole = Qt.UserRole + 2
    TotalRole = Qt.UserRole + 3
    RatioRole = Qt.UserRole + 4

    _ROLE_NAMES = {
        LabelRole: b"label",
        ValueRole: b"value",
        TotalRole: b"total",
        RatioRole: b"ratio",
    }

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        self._items: tuple[tuple[int, int], ...] = ()
        self._rows: tuple[dict[int, object], ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        return self._rows[index.row()].get(role)

    def roleNames(self) -> dict[int, bytes]:
        return self._ROLE_NAMES

    def replace(self, counts: Sequence[tuple[int, int]], total: int) -> None:
        self.beginResetModel()
        self._items = tuple(counts)
        self._rows = tuple(
            {
                self.LabelRole: f"Estado {state}",
                self.ValueRole: value,
                self.TotalRole: total,
                self.RatioRole: value / total if total else 0.0,
            }
            for state, value in self._items
        )
        self.endResetModel()
