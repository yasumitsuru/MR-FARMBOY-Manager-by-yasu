"""Contratos dos modelos de lista expostos ao QML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from mr_farmboy_manager.backups import BackupRecord
from mr_farmboy_manager.presentation.backups_model import BackupsModel
from mr_farmboy_manager.presentation.growth_states_model import GrowthStatesModel
from mr_farmboy_manager.presentation.save_slots_model import SaveSlotsModel
from mr_farmboy_manager.save_slots import SaveSlot, SaveSlotSummary


def test_save_model_exposes_stable_roles(tmp_path: Path) -> None:
    """Detecta quebras nos valores de slot consumidos pelo QML."""
    summary = SaveSlotSummary(SaveSlot(2, tmp_path / "save_2"), 7)
    model = SaveSlotsModel()
    model.replace((summary,))

    index = model.index(0, 0)
    assert model.data(index, SaveSlotsModel.SlotIdRole) == "save_2"
    assert model.data(index, SaveSlotsModel.DisplayNameRole) == "Slot 2"
    assert model.data(index, SaveSlotsModel.RecordCountRole) == 7
    assert model.data(index, SaveSlotsModel.PathLabelRole) == "save_2"
    assert model.roleNames()[SaveSlotsModel.SelectedRole] == b"selected"


def test_save_model_notifies_only_rows_with_changed_selection(tmp_path: Path) -> None:
    """Detecta valor obsoleto de seleção durante a notificação QML."""
    model = SaveSlotsModel()
    model.replace(
        (
            SaveSlotSummary(SaveSlot(1, tmp_path / "save_1"), 1),
            SaveSlotSummary(SaveSlot(2, tmp_path / "save_2"), 2),
        )
    )
    changed: list[tuple[int, object]] = []
    model.dataChanged.connect(
        lambda first, _last, _roles: changed.append(
            (
                first.row(),
                model.data(first, SaveSlotsModel.SelectedRole),
            )
        )
    )

    model.set_selected("save_1")
    model.set_selected("save_2")

    assert changed == [(0, True), (0, False), (1, True)]


def test_models_replace_with_empty_data(tmp_path: Path) -> None:
    """Detecta modelos que deixam linhas obsoletas após uma atualização vazia."""
    saves = SaveSlotsModel()
    saves.replace((SaveSlotSummary(SaveSlot(1, tmp_path / "save_1"), 1),))
    saves.replace(())
    backups = BackupsModel()
    backups.replace(())

    assert saves.rowCount() == 0
    assert backups.rowCount() == 0


def test_backup_model_preserves_discovery_order_and_formats_labels(tmp_path: Path) -> None:
    """Detecta reordenação ou rótulos de backup inadequados para exibição."""
    newest = BackupRecord("save_2-new", 2, datetime(2026, 8, 8, 15, 30, tzinfo=UTC), tmp_path / "save_2-new", 2, 4096)
    older = BackupRecord("save_1-old", 1, datetime(2026, 8, 8, 10, 30, tzinfo=UTC), tmp_path / "save_1-old", 1, 512)
    model = BackupsModel()
    model.replace((newest, older))

    first = model.index(0, 0)
    second = model.index(1, 0)
    assert model.data(first, BackupsModel.BackupIdRole) == "save_2-new"
    assert model.data(first, BackupsModel.SlotIdRole) == "save_2"
    assert model.data(first, BackupsModel.SlotLabelRole) == "Slot 2"
    assert model.data(first, BackupsModel.CreatedAtLabelRole) == "2026-08-08 15:30 UTC"
    assert model.data(first, BackupsModel.SizeLabelRole) == "4,0 KiB"
    assert model.data(first, BackupsModel.IntegrityLabelRole) == "Íntegro"
    assert model.data(second, BackupsModel.SizeLabelRole) == "512 B"


def test_backup_model_notifies_changed_rows_after_selection_is_updated(
    tmp_path: Path,
) -> None:
    """Detecta seleção de backup obsoleta durante o sinal para o QML."""
    model = BackupsModel()
    model.replace(
        (
            BackupRecord(
                "save_1-first",
                1,
                datetime(2026, 8, 8, 10, 30, tzinfo=UTC),
                tmp_path / "save_1-first",
                1,
                512,
            ),
            BackupRecord(
                "save_2-second",
                2,
                datetime(2026, 8, 8, 15, 30, tzinfo=UTC),
                tmp_path / "save_2-second",
                2,
                4096,
            ),
        )
    )
    changed: list[tuple[int, object]] = []
    model.dataChanged.connect(
        lambda first, _last, _roles: changed.append(
            (
                first.row(),
                model.data(first, BackupsModel.SelectedRole),
            )
        )
    )

    model.set_selected("save_1-first")
    model.set_selected("save_2-second")

    assert changed == [(0, True), (0, False), (1, True)]


def test_growth_model_calculates_ratios_and_handles_zero_total() -> None:
    """Detecta divisões por zero e proporções erradas no gráfico de crescimento."""
    model = GrowthStatesModel()
    model.replace(((1, 2), (3, 1)), total=4)
    first = model.index(0, 0)
    assert model.data(first, GrowthStatesModel.LabelRole) == "Estado 1"
    assert model.data(first, GrowthStatesModel.ValueRole) == 2
    assert model.data(first, GrowthStatesModel.TotalRole) == 4
    assert model.data(first, GrowthStatesModel.RatioRole) == 0.5

    model.replace(((7, 0),), total=0)
    assert model.data(model.index(0, 0), GrowthStatesModel.RatioRole) == 0.0
