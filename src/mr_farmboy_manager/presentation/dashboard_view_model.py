"""Estado agregado, somente leitura, exibido no dashboard QML."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from PySide6.QtCore import QObject, Property, Signal

from mr_farmboy_manager.backups import BackupRecord
from mr_farmboy_manager.save_details import SaveSlotDetails

from .formatters import format_created_at_label


class DashboardViewModel(QObject):
    """Projeta somente dados reais já carregados pelos outros ViewModels."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._values: dict[str, int | str | bool] = {}
        self._replace(self._empty_values())

    def update(
        self,
        slot_count: int,
        selected_details: SaveSlotDetails | None,
        backups: Sequence[BackupRecord],
        configuration_state: str,
        updated_at: datetime | None,
    ) -> None:
        """Substitui o snapshot por valores derivados dos DTOs carregados."""
        crops = selected_details.crop_progress if selected_details is not None else None
        latest_backup = max(backups, key=lambda item: item.created_at_utc, default=None)
        self._replace(
            {
                "slotCount": max(0, int(slot_count)),
                "backupCount": len(backups),
                "selectedSlotLabel": (
                    f"Slot {selected_details.summary.slot.number}"
                    if selected_details is not None
                    else "Não disponível"
                ),
                "lastBackupLabel": (
                    format_created_at_label(latest_backup.created_at_utc)
                    if latest_backup is not None
                    else "Não disponível"
                ),
                "lastUpdatedLabel": (
                    format_created_at_label(updated_at)
                    if updated_at is not None
                    else "Não disponível"
                ),
                "configurationState": str(configuration_state),
                "recordCount": crops.record_count if crops is not None else 0,
                "plantedCount": crops.planted_count if crops is not None else 0,
                "wateredCount": crops.watered_count if crops is not None else 0,
                "fertilizedCount": crops.fertilized_count if crops is not None else 0,
                "maturedCount": crops.matured_count if crops is not None else 0,
                "harvestableCount": crops.harvestable_count if crops is not None else 0,
                "deadCount": crops.dead_count if crops is not None else 0,
                "hasSelectedSlot": selected_details is not None,
            }
        )

    def _replace(self, values: dict[str, int | str | bool]) -> None:
        if values == self._values:
            return
        self._values = values
        self.changed.emit()

    @staticmethod
    def _empty_values() -> dict[str, int | str | bool]:
        return {
            "slotCount": 0,
            "backupCount": 0,
            "selectedSlotLabel": "Não disponível",
            "lastBackupLabel": "Não disponível",
            "lastUpdatedLabel": "Não disponível",
            "configurationState": "empty",
            "recordCount": 0,
            "plantedCount": 0,
            "wateredCount": 0,
            "fertilizedCount": 0,
            "maturedCount": 0,
            "harvestableCount": 0,
            "deadCount": 0,
            "hasSelectedSlot": False,
        }

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


__all__ = ["DashboardViewModel"]
