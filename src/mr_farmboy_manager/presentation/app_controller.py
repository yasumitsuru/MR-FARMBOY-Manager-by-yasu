"""Composition root dos ViewModels expostos ao QML."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from mr_farmboy_manager.settings import QtSettingsStore, SettingsStore

from .backups_view_model import BackupsViewModel
from .dashboard_view_model import DashboardViewModel
from .diagnostics_view_model import DiagnosticsViewModel
from .operation_runner import OperationRunner, QtOperationRunner
from .saves_view_model import SavesViewModel
from .settings_view_model import SettingsViewModel


class AppController(QObject):
    """Coordena ViewModels, sem conter lógica de filesystem própria."""

    changed = Signal()
    AUTO_REFRESH_INTERVAL_MS = 300000

    def __init__(
        self,
        settings_store: SettingsStore | None = None,
        backup_root: Path | str | None = None,
        *,
        log_path: Path | str | None = None,
        runner: OperationRunner | None = None,
        saves: SavesViewModel | None = None,
        backups: BackupsViewModel | None = None,
        settings: SettingsViewModel | None = None,
        dashboard: DashboardViewModel | None = None,
        diagnostics: DiagnosticsViewModel | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner or QtOperationRunner(self)
        self._backup_root = Path(backup_root) if backup_root is not None else Path.cwd() / "backups"
        self._settings = settings or SettingsViewModel(settings_store or QtSettingsStore(), self._backup_root, parent=self)
        self._saves = saves or SavesViewModel(self._runner, parent=self)
        self._backups = backups or BackupsViewModel(self._runner, self._backup_root, parent=self)
        self._dashboard = dashboard or DashboardViewModel(self)
        self._diagnostics = diagnostics or DiagnosticsViewModel(log_path, parent=self)
        self._timer = QTimer(self)
        self._timer.setInterval(self.AUTO_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._auto_refresh)
        self._initialized = False
        self._busy_snapshot = self.busy

        self._settings.settingsApplied.connect(self._apply_settings)
        self._settings.changed.connect(self._recompute_dashboard)
        self._saves.selectedSummaryChanged.connect(self._backups.setSelectedSummary)
        self._saves.selectedSummaryChanged.connect(self._recompute_dashboard)
        self._saves.changed.connect(self._child_state_changed)
        self._backups.changed.connect(self._child_state_changed)
        self._settings.changed.connect(self._child_state_changed)

    @Slot()
    def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._settings.reload()
        self._saves.setSaveRoot(self._settings.saveRoot)
        self._saves.refresh()
        self._backups.refresh()
        self._diagnostics.refresh()
        self._recompute_dashboard()
        self._timer.start()
        self._child_state_changed()

    @Slot(result=bool)
    def shutdown(self) -> bool:
        self._timer.stop()
        self._initialized = False
        return self._runner.shutdown()

    @Slot()
    def triggerAutoRefreshForTest(self) -> None:
        """Hook determinístico para testar a política do timer sem esperar cinco minutos."""
        self._auto_refresh()

    @Slot()
    def _auto_refresh(self) -> None:
        if self._backups.mutationState != "idle":
            return
        self._saves.refresh()
        self._backups.refresh()

    @Slot(str, str)
    def _apply_settings(self, save_root: str, _game_install_root: str) -> None:
        self._saves.setSaveRoot(save_root)
        self._saves.refresh()
        self._recompute_dashboard()

    @Slot()
    def _recompute_dashboard(self) -> None:
        details = self._saves._loaded_details if self._saves.detailsState == "ready" else None
        backups = tuple(getattr(self._backups, "_backups", ()))
        self._dashboard.update(
            self._saves.slotsModel.rowCount(),
            details,
            backups,
            self._settings.saveRootState,
            datetime.now(UTC) if self._saves.state in {"ready", "empty"} else None,
        )

    @Slot()
    def _child_state_changed(self) -> None:
        self._recompute_dashboard()
        current = self.busy
        if current != self._busy_snapshot:
            self._busy_snapshot = current
            self.changed.emit()

    saves = Property(QObject, lambda self: self._saves, constant=True)
    backups = Property(QObject, lambda self: self._backups, constant=True)
    settings = Property(QObject, lambda self: self._settings, constant=True)
    dashboard = Property(QObject, lambda self: self._dashboard, constant=True)
    diagnostics = Property(QObject, lambda self: self._diagnostics, constant=True)
    busy = Property(
        bool,
        lambda self: self._saves.state == "loading"
        or self._saves.detailsState == "loading"
        or self._backups.state == "loading"
        or self._backups.mutationState != "idle",
        notify=changed,
    )
    autoRefreshInterval = Property(int, lambda self: self.AUTO_REFRESH_INTERVAL_MS, constant=True)


__all__ = ["AppController"]
