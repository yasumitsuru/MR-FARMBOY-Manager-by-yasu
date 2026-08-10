"""Contratos do estado agregado do dashboard QML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mr_farmboy_manager.backups import BackupRecord
from mr_farmboy_manager.presentation.dashboard_view_model import DashboardViewModel
from mr_farmboy_manager.save_details import CropProgressDetails, SaveSlotDetails
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


def _details() -> SaveSlotDetails:
    summary = SaveSlotSummary(SaveSlot(2, Path("C:/temporary/save_2")), 12)
    return SaveSlotDetails(
        summary, None, 0, 0, (), None,
        CropProgressDetails(10, 8, 5, 4, 3, 2, 1, ()),
    )


def _backups() -> tuple[BackupRecord, ...]:
    return (
        BackupRecord("backup-older", 2, datetime(2026, 8, 10, 10, tzinfo=UTC), Path("C:/b"), 1, 2),
        BackupRecord("backup-newer", 2, datetime(2026, 8, 10, 11, tzinfo=UTC), Path("C:/b"), 1, 2),
    )


def test_dashboard_uses_real_crop_metrics(qapp) -> None:
    vm = DashboardViewModel()

    vm.update(2, _details(), _backups(), "valid", datetime(2026, 8, 10, 12, tzinfo=UTC))

    assert vm.slotCount == 2
    assert vm.backupCount == 2
    assert vm.selectedSlotLabel == "Slot 2"
    assert vm.plantedCount == 8
    assert vm.wateredCount == 5
    assert vm.fertilizedCount == 4
    assert vm.maturedCount == 3
    assert vm.harvestableCount == 2
    assert vm.deadCount == 1
    assert vm.recordCount == 10
    assert vm.lastBackupLabel == "2026-08-10 11:00 UTC"
    assert vm.lastUpdatedLabel == "2026-08-10 12:00 UTC"
    assert vm.hasSelectedSlot is True
    assert not hasattr(vm, "money")
