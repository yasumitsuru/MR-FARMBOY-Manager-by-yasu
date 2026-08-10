"""Contratos da ponte de saves para a interface QML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    SaveSlotsLoadResult,
)
from mr_farmboy_manager.save_details import (
    CropProgressDetails,
    PlayerProgressDetails,
    SaveSlotDetails,
)
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary
from mr_farmboy_manager.presentation.saves_view_model import SavesViewModel

from .fakes import ControlledOperationRunner


def loaded_result(root: Path, numbers: tuple[int, ...]) -> SaveSlotsLoadResult:
    return SaveSlotsLoadResult(
        DirectoryValidationResult(DirectoryValidationCode.VALID, root),
        tuple(
            SaveSlotSummary(SaveSlot(number, root / f"save_{number}"), number)
            for number in numbers
        ),
    )


def details_for(summary: SaveSlotSummary) -> SaveSlotDetails:
    return SaveSlotDetails(
        summary=summary,
        latest_modified_at=datetime(2026, 8, 10, 12, 30, tzinfo=UTC),
        inspected_file_count=2,
        total_property_count=12,
        failed_files=("player_data.tres",),
        player_progress=PlayerProgressDetails(1, 2, 3, 4, 5, 6),
        crop_progress=CropProgressDetails(
            record_count=4,
            planted_count=3,
            watered_count=2,
            fertilized_count=1,
            matured_count=1,
            harvestable_count=1,
            dead_count=0,
            growth_state_counts=((2, 3), (4, 1)),
        ),
    )


def configured_saves_view_model(
    runner: ControlledOperationRunner, root: Path
) -> SavesViewModel:
    vm = SavesViewModel(
        runner,
        loader=lambda _path: loaded_result(root, (1, 2)),
        details_loader=details_for,
    )
    vm.setSaveRoot(str(root))
    vm.refresh()
    runner.complete_next()
    return vm


def test_idle_state_exposes_no_selection_or_actions(qapp) -> None:
    vm = SavesViewModel(ControlledOperationRunner())

    assert vm.state == "idle"
    assert vm.detailsState == "idle"
    assert vm.selectedSlotId == ""
    assert vm.statusMessage == ""
    assert vm.errorMessage == ""
    assert vm.canRefresh is False
    assert vm.canCreateBackup is False
    assert vm.slotsModel.rowCount() == 0


def test_save_root_notifies_only_when_refresh_capability_changes(
    tmp_path: Path, qapp
) -> None:
    vm = SavesViewModel(ControlledOperationRunner())
    notifications: list[bool] = []
    vm.changed.connect(lambda: notifications.append(vm.canRefresh))

    vm.setSaveRoot(str(tmp_path))
    vm.setSaveRoot(str(tmp_path))

    assert notifications == [True]


def test_refresh_moves_loading_to_ready_and_preserves_selection(
    tmp_path: Path, qapp
) -> None:
    runner = ControlledOperationRunner()
    vm = SavesViewModel(runner, loader=lambda _path: loaded_result(tmp_path, (1, 2)))
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()

    assert vm.state == "loading"
    runner.complete_next()
    vm.selectSlot("save_2")

    assert vm.state == "ready"
    assert vm.selectedSlotId == "save_2"
    assert vm.canCreateBackup is True

    vm.refresh()
    runner.complete_next()
    runner.complete_next()
    assert vm.state == "ready"
    assert vm.selectedSlotId == "save_2"


def test_refresh_exposes_empty_result(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = SavesViewModel(runner, loader=lambda _path: loaded_result(tmp_path, ()))
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()
    runner.complete_next()

    assert vm.state == "empty"
    assert vm.statusMessage == "Nenhum save encontrado."
    assert vm.canCreateBackup is False


def test_refresh_error_uses_runner_public_message(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = SavesViewModel(runner)
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()
    runner.fail_next("Não foi possível concluir a operação.")

    assert vm.state == "error"
    assert vm.errorMessage == "Não foi possível concluir a operação."
    assert vm.statusMessage == ""


def test_refresh_removes_selection_and_details_when_slot_disappears(
    tmp_path: Path, qapp
) -> None:
    runner = ControlledOperationRunner()
    results = [loaded_result(tmp_path, (1, 2)), loaded_result(tmp_path, (1,))]
    vm = SavesViewModel(runner, loader=lambda _path: results.pop(0))
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()
    runner.complete_next()
    vm.selectSlot("save_2")
    vm.refresh()
    runner.complete_next()
    runner.complete_next()

    assert vm.selectedSlotId == ""
    assert vm.detailsState == "idle"
    assert vm.canCreateBackup is False


def test_stale_detail_result_cannot_replace_new_selection(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = configured_saves_view_model(runner, tmp_path)

    vm.selectSlot("save_1")
    vm.selectSlot("save_2")
    runner.complete_next()

    assert vm.selectedSlotId == "save_2"
    assert vm.detailsState == "loading"


def test_details_exposes_optional_metrics_and_zero_growth_total(
    tmp_path: Path, qapp
) -> None:
    runner = ControlledOperationRunner()
    vm = configured_saves_view_model(runner, tmp_path)
    vm.selectSlot("save_1")
    runner.complete_next()

    assert vm.detailsState == "ready"
    assert vm.details.recordCount == 4
    assert vm.details.plantedCount == 3
    assert vm.details.inspectedFileCount == 2
    assert vm.details.failedFileCount == 1
    assert vm.details.latestModifiedLabel == "2026-08-10 12:30 UTC"
    assert vm.details.hasCropProgress is True
    assert vm.details.hasPlayerProgress is True
    assert vm.details.growthStatesModel.data(
        vm.details.growthStatesModel.index(0, 0), 260
    ) == 0.75

    zero_runner = ControlledOperationRunner()
    vm = SavesViewModel(
        zero_runner,
        loader=lambda _path: loaded_result(tmp_path, (1,)),
        details_loader=lambda summary: SaveSlotDetails(
            summary, None, 0, 0, (), None,
            CropProgressDetails(0, 0, 0, 0, 0, 0, 0, ((7, 0),)),
        ),
    )
    vm.setSaveRoot(str(tmp_path))
    vm.refresh()
    zero_runner.complete_next()
    vm.selectSlot("save_1")
    zero_runner.complete_next()
    assert vm.details.growthStatesModel.data(
        vm.details.growthStatesModel.index(0, 0), 260
    ) == 0.0


def test_selection_notifications_only_emit_for_actual_changes(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    vm = configured_saves_view_model(runner, tmp_path)
    received: list[object] = []
    vm.selectedSummaryChanged.connect(received.append)

    vm.selectSlot("save_1")
    vm.selectSlot("save_1")
    vm.clearSelection()
    vm.clearSelection()

    assert [summary.slot.name if summary is not None else None for summary in received] == [
        "save_1",
        None,
    ]
