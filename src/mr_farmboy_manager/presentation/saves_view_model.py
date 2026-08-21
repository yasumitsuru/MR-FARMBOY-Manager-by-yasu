"""View models de saves seguros para consumo direto pelo QML."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import QObject, Property, Signal, Slot

from mr_farmboy_manager.manual_paths import SaveSlotsLoadResult, load_save_slot_summaries
from mr_farmboy_manager.save_details import SaveSlotDetails, inspect_save_slot
from mr_farmboy_manager.save_slots import SaveSlotSummary

from .formatters import format_created_at_label
from .growth_states_model import GrowthStatesModel
from .operation_runner import OperationRunner
from .save_slots_model import SaveSlotsModel


class SaveDetailsViewModel(QObject):
    """Métricas agregadas de um slot, sem expor o DTO ou caminhos ao QML."""

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._growth_states_model = GrowthStatesModel(self)
        self._values: dict[str, int | str | bool] = {}
        self.clear()

    def clear(self) -> None:
        self._replace(
            {
                "recordCount": 0,
                "plantedCount": 0,
                "wateredCount": 0,
                "fertilizedCount": 0,
                "maturedCount": 0,
                "harvestableCount": 0,
                "deadCount": 0,
                "inspectedFileCount": 0,
                "failedFileCount": 0,
                "latestModifiedLabel": "",
                "hasCropProgress": False,
                "hasPlayerProgress": False,
            },
            (),
            0,
        )

    def apply(self, details: SaveSlotDetails) -> None:
        crops = details.crop_progress
        self._replace(
            {
                "recordCount": crops.record_count if crops is not None else 0,
                "plantedCount": crops.planted_count if crops is not None else 0,
                "wateredCount": crops.watered_count if crops is not None else 0,
                "fertilizedCount": crops.fertilized_count if crops is not None else 0,
                "maturedCount": crops.matured_count if crops is not None else 0,
                "harvestableCount": crops.harvestable_count if crops is not None else 0,
                "deadCount": crops.dead_count if crops is not None else 0,
                "inspectedFileCount": details.inspected_file_count,
                "failedFileCount": len(details.failed_files),
                "latestModifiedLabel": self._format_modified(details.latest_modified_at),
                "hasCropProgress": crops is not None,
                "hasPlayerProgress": details.player_progress is not None,
            },
            crops.growth_state_counts if crops is not None else (),
            crops.record_count if crops is not None else 0,
        )

    def _replace(
        self,
        values: dict[str, int | str | bool],
        growth_counts: tuple[tuple[int, int], ...],
        growth_total: int,
    ) -> None:
        values_changed = values != self._values
        self._values = values
        if growth_counts != getattr(self, "_growth_counts", ()) or growth_total != getattr(
            self, "_growth_total", 0
        ):
            self._growth_counts = growth_counts
            self._growth_total = growth_total
            self._growth_states_model.replace(growth_counts, growth_total)
        if values_changed:
            self.changed.emit()

    @staticmethod
    def _format_modified(value: datetime | None) -> str:
        return format_created_at_label(value) if value is not None else ""

    recordCount = Property(int, lambda self: self._values["recordCount"], notify=changed)
    plantedCount = Property(int, lambda self: self._values["plantedCount"], notify=changed)
    wateredCount = Property(int, lambda self: self._values["wateredCount"], notify=changed)
    fertilizedCount = Property(int, lambda self: self._values["fertilizedCount"], notify=changed)
    maturedCount = Property(int, lambda self: self._values["maturedCount"], notify=changed)
    harvestableCount = Property(int, lambda self: self._values["harvestableCount"], notify=changed)
    deadCount = Property(int, lambda self: self._values["deadCount"], notify=changed)
    inspectedFileCount = Property(int, lambda self: self._values["inspectedFileCount"], notify=changed)
    failedFileCount = Property(int, lambda self: self._values["failedFileCount"], notify=changed)
    latestModifiedLabel = Property(str, lambda self: self._values["latestModifiedLabel"], notify=changed)
    hasCropProgress = Property(bool, lambda self: self._values["hasCropProgress"], notify=changed)
    hasPlayerProgress = Property(bool, lambda self: self._values["hasPlayerProgress"], notify=changed)
    growthStatesModel = Property(QObject, lambda self: self._growth_states_model, constant=True)


class SavesViewModel(QObject):
    """Coordena a listagem e a inspeção serial de saves para o QML."""

    changed = Signal()
    selectedSummaryChanged = Signal(object)

    def __init__(
        self,
        runner: OperationRunner,
        loader: Callable[[str], SaveSlotsLoadResult] = load_save_slot_summaries,
        details_loader: Callable[[SaveSlotSummary], SaveSlotDetails] = inspect_save_slot,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._loader = loader
        self._details_loader = details_loader
        self._slots_model = SaveSlotsModel(self)
        self._details = SaveDetailsViewModel(self)
        self._loaded_details: SaveSlotDetails | None = None
        self._save_root = ""
        self._state = "idle"
        self._details_state = "idle"
        self._selected_summary: SaveSlotSummary | None = None
        self._status_message = ""
        self._error_message = ""
        self._refresh_request: int | None = None
        self._refresh_generation = 0
        self._refresh_context: tuple[int, str] | None = None
        self._detail_request: int | None = None
        self._detail_generation = 0
        self._detail_context: tuple[int, str] | None = None
        runner.succeeded.connect(self._operation_succeeded)
        runner.failed.connect(self._operation_failed)

    @Slot(str)
    def setSaveRoot(self, value: str) -> None:
        save_root = str(value).strip()
        if save_root == self._save_root:
            return
        before = self._public_values()
        self._save_root = save_root
        self._refresh_generation += 1
        self._refresh_request = None
        self._refresh_context = None
        self._clear_selection()
        self._set_values(state="idle", status_message="", error_message="")
        self._notify_if_changed(before)

    @Slot()
    def refresh(self) -> None:
        if not self._save_root or self._refresh_request is not None:
            return
        before = self._public_values()
        self._refresh_generation += 1
        generation = self._refresh_generation
        save_root = self._save_root
        self._set_values(state="loading", status_message="", error_message="")
        request_id = self._runner.submit(
            f"saves.refresh:{generation}", lambda: self._loader(save_root)
        )
        self._refresh_request = request_id
        self._refresh_context = generation, save_root
        self._notify_if_changed(before)

    @Slot(str)
    def selectSlot(self, slot_id: str) -> None:
        summary = self._summary_for(slot_id)
        if summary is None or summary == self._selected_summary:
            return
        before = self._public_values()
        self._selected_summary = summary
        self._slots_model.set_selected(summary.slot.name)
        self.selectedSummaryChanged.emit(summary)
        self._request_details(summary)
        self._notify_if_changed(before)

    @Slot()
    def clearSelection(self) -> None:
        before = self._public_values()
        self._clear_selection()
        self._notify_if_changed(before)

    def _clear_selection(self) -> None:
        if self._selected_summary is None and self._details_state == "idle":
            return
        self._selected_summary = None
        self._slots_model.set_selected(None)
        self._detail_generation += 1
        self._detail_request = None
        self._detail_context = None
        self._details.clear()
        self._loaded_details = None
        self._set_values(details_state="idle")
        self.selectedSummaryChanged.emit(None)

    def _request_details(self, summary: SaveSlotSummary) -> None:
        self._detail_generation += 1
        generation = self._detail_generation
        self._set_values(details_state="loading", error_message="")
        self._details.clear()
        request_id = self._runner.submit(
            f"saves.details:{generation}:{summary.slot.name}",
            lambda: self._details_loader(summary),
        )
        self._detail_request = request_id
        self._detail_context = generation, summary.slot.name

    @Slot(int, str, object)
    def _operation_succeeded(self, request_id: int, name: str, value: object) -> None:
        if (
            request_id == self._refresh_request
            and self._refresh_context is not None
            and name == f"saves.refresh:{self._refresh_context[0]}"
            and self._refresh_context[1] == self._save_root
        ):
            before = self._public_values()
            self._refresh_request = None
            self._refresh_context = None
            self._apply_refresh(value)
            self._notify_if_changed(before)
            return
        if request_id != self._detail_request or self._detail_context is None:
            return
        generation, slot_id = self._detail_context
        if (
            not name.startswith("saves.details:")
            or self._selected_summary is None
            or self._selected_summary.slot.name != slot_id
            or generation != self._detail_generation
            or not isinstance(value, SaveSlotDetails)
        ):
            return
        self._detail_request = None
        self._detail_context = None
        self._details.apply(value)
        self._loaded_details = value
        before = self._public_values()
        self._set_values(details_state="ready")
        self._notify_if_changed(before)

    @Slot(int, str, str)
    def _operation_failed(self, request_id: int, name: str, public_message: str) -> None:
        if (
            request_id == self._refresh_request
            and self._refresh_context is not None
            and name == f"saves.refresh:{self._refresh_context[0]}"
            and self._refresh_context[1] == self._save_root
        ):
            before = self._public_values()
            self._refresh_request = None
            self._refresh_context = None
            self._set_values(state="error", status_message="", error_message=public_message)
            self._notify_if_changed(before)
            return
        if request_id != self._detail_request or self._detail_context is None:
            return
        generation, slot_id = self._detail_context
        if (
            not name.startswith("saves.details:")
            or self._selected_summary is None
            or self._selected_summary.slot.name != slot_id
            or generation != self._detail_generation
        ):
            return
        self._detail_request = None
        self._detail_context = None
        self._details.clear()
        self._loaded_details = None
        before = self._public_values()
        self._set_values(details_state="error", error_message=public_message)
        self._notify_if_changed(before)

    def _apply_refresh(self, value: object) -> None:
        if not isinstance(value, SaveSlotsLoadResult) or not value.is_success:
            self._clear_selection()
            self._slots_model.replace(())
            self._set_values(
                state="error",
                status_message="",
                error_message="Não foi possível carregar os saves.",
            )
            return
        self._slots_model.replace(value.summaries)
        selected = self._summary_for(
            self._selected_summary.slot.name if self._selected_summary is not None else ""
        )
        if selected is None:
            self._clear_selection()
        else:
            self._selected_summary = selected
            self._slots_model.set_selected(selected.slot.name)
            self._request_details(selected)
        if value.summaries:
            self._set_values(state="ready", status_message="", error_message="")
        else:
            self._set_values(
                state="empty", status_message="Nenhum save encontrado.", error_message=""
            )

    def _summary_for(self, slot_id: str) -> SaveSlotSummary | None:
        for summary in self._slots_model._items:
            if summary.slot.name == slot_id:
                return summary
        return None

    def _set_values(self, **values: str) -> None:
        for name, value in values.items():
            attribute = f"_{name}"
            if getattr(self, attribute) != value:
                setattr(self, attribute, value)

    def _public_values(self) -> tuple[str, str, str, str, str, bool, bool]:
        return (
            self._state,
            self._details_state,
            self.selectedSlotId,
            self._status_message,
            self._error_message,
            self.canRefresh,
            self.canCreateBackup,
        )

    def _notify_if_changed(
        self, before: tuple[str, str, str, str, str, bool, bool]
    ) -> None:
        if self._public_values() != before:
            self.changed.emit()

    state = Property(str, lambda self: self._state, notify=changed)
    detailsState = Property(str, lambda self: self._details_state, notify=changed)
    selectedSlotId = Property(
        str,
        lambda self: self._selected_summary.slot.name if self._selected_summary is not None else "",
        notify=changed,
    )
    statusMessage = Property(str, lambda self: self._status_message, notify=changed)
    errorMessage = Property(str, lambda self: self._error_message, notify=changed)
    canRefresh = Property(
        bool, lambda self: bool(self._save_root) and self._refresh_request is None, notify=changed
    )
    canCreateBackup = Property(
        bool,
        lambda self: self._state == "ready" and self._selected_summary is not None,
        notify=changed,
    )
    slotsModel = Property(QObject, lambda self: self._slots_model, constant=True)
    details = Property(QObject, lambda self: self._details, constant=True)


__all__ = ["SaveDetailsViewModel", "SavesViewModel"]
