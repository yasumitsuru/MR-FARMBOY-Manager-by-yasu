"""Coordenação determinística dos ViewModels da aplicação."""

from __future__ import annotations

from pathlib import Path

from mr_farmboy_manager.presentation.app_controller import AppController
from mr_farmboy_manager.presentation.backups_view_model import BackupsViewModel
from mr_farmboy_manager.presentation.saves_view_model import SavesViewModel
from mr_farmboy_manager.presentation.settings_view_model import SettingsViewModel
from mr_farmboy_manager.settings import AppSettings

from .fakes import ControlledOperationRunner


class _Store:
    def load(self) -> AppSettings:
        return AppSettings()

    def save(self, _settings: AppSettings) -> None:
        pass


class _Saves(SavesViewModel):
    def __init__(self, runner: ControlledOperationRunner) -> None:
        super().__init__(runner)
        self.refresh_calls = 0

    def refresh(self) -> None:
        self.refresh_calls += 1


class _Backups(BackupsViewModel):
    def __init__(self, runner: ControlledOperationRunner, root: Path) -> None:
        super().__init__(runner, root)
        self.refresh_calls = 0

    def refresh(self) -> None:
        self.refresh_calls += 1

    def setMutationStateForTest(self, value: str) -> None:
        self._mutation_state = value


def test_controller_timer_skips_active_mutation(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    saves = _Saves(runner)
    backups = _Backups(runner, tmp_path / "backups")
    settings = SettingsViewModel(_Store(), tmp_path / "backups")
    controller = AppController(
        _Store(), tmp_path / "backups", runner=runner, saves=saves, backups=backups, settings=settings,
    )

    assert controller.autoRefreshInterval == 300000
    backups.setMutationStateForTest("restoring")
    controller.triggerAutoRefreshForTest()

    assert saves.refresh_calls == 0
    assert backups.refresh_calls == 0


def test_initialize_applies_settings_refreshes_pages_and_shutdown_runner(tmp_path: Path, qapp) -> None:
    runner = ControlledOperationRunner()
    saves = _Saves(runner)
    backups = _Backups(runner, tmp_path / "backups")
    settings = SettingsViewModel(_Store(), tmp_path / "backups")
    controller = AppController(
        _Store(), tmp_path / "backups", runner=runner, saves=saves, backups=backups, settings=settings,
    )

    controller.initialize()

    assert saves.refresh_calls == 1
    assert backups.refresh_calls == 1
    assert controller.shutdown() is True
