"""Contratos do ViewModel de configurações para a interface QML."""

from __future__ import annotations

from pathlib import Path

from mr_farmboy_manager.presentation.settings_view_model import SettingsViewModel
from mr_farmboy_manager.settings import AppSettings


class FakeSettingsStore:
    """Persistência em memória que conserva o último valor operacional salvo."""

    def __init__(self, settings: AppSettings) -> None:
        self.current = settings
        self.saved: AppSettings | None = None

    def load(self) -> AppSettings:
        return self.current

    def save(self, settings: AppSettings) -> None:
        self.saved = settings
        self.current = settings


def test_normalized_slot_is_displayed_and_persisted_as_root(
    tmp_path: Path, qapp
) -> None:
    """A save slot selecionada não pode ser persistida no lugar da raiz."""
    root = tmp_path / "game_data"
    (root / "save_1").mkdir(parents=True)
    store = FakeSettingsStore(AppSettings("", ""))
    vm = SettingsViewModel(store, backup_root=tmp_path / "backups")

    vm.setSaveRoot(str(root / "save_1"))
    vm.save()

    assert vm.saveRoot == str(root)
    assert vm.saveRootState == "valid"
    assert "normalizada" in vm.saveRootMessage.lower()
    assert store.saved == AppSettings(str(root), "")


def test_empty_paths_are_valid_and_not_dirty(tmp_path: Path, qapp) -> None:
    """Configurações vazias são o estado seguro inicial, não um erro bloqueante."""
    vm = SettingsViewModel(FakeSettingsStore(AppSettings()), backup_root=tmp_path / "backups")

    assert vm.saveRoot == ""
    assert vm.gameInstallRoot == ""
    assert vm.saveRootState == "empty"
    assert vm.gameInstallState == "empty"
    assert vm.canSave is True
    assert vm.hasUnsavedChanges is False
    assert vm.backupRootLabel == str(tmp_path / "backups")


def test_invalid_path_cannot_replace_persisted_operational_settings(
    tmp_path: Path, qapp
) -> None:
    """Uma edição inválida não pode sobrescrever a configuração operacional salva."""
    save_root = tmp_path / "game_data"
    game_root = tmp_path / "game"
    save_root.mkdir()
    game_root.mkdir()
    original = AppSettings(str(save_root), str(game_root))
    store = FakeSettingsStore(original)
    vm = SettingsViewModel(store, backup_root=tmp_path / "backups")

    vm.setSaveRoot(str(tmp_path / "missing"))
    vm.save()

    assert vm.saveRootState == "not_found"
    assert vm.canSave is False
    assert store.saved is None
    assert store.load() == original


def test_valid_game_path_is_persisted_and_signal_uses_effective_values(
    tmp_path: Path, qapp
) -> None:
    """Salvar um diretório de jogo válido persiste e anuncia os valores aplicados."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    store = FakeSettingsStore(AppSettings())
    vm = SettingsViewModel(store, backup_root=tmp_path / "backups")
    applied: list[tuple[str, str]] = []
    vm.settingsApplied.connect(lambda save, game: applied.append((save, game)))

    vm.setGameInstallRoot(str(game_root))
    vm.save()

    assert vm.gameInstallState == "valid"
    assert store.saved == AppSettings("", str(game_root))
    assert applied == [("", str(game_root))]
    assert vm.hasUnsavedChanges is False


def test_chooser_cancellation_is_neutral_and_injected_choice_is_validated(
    tmp_path: Path, qapp
) -> None:
    """Cancelar não altera o rascunho; escolhas injetadas passam pelos validadores."""
    save_root = tmp_path / "game_data"
    game_root = tmp_path / "game"
    save_root.mkdir()
    game_root.mkdir()
    choices = iter([None, str(save_root), "", str(game_root)])
    chooser = lambda: next(choices)
    vm = SettingsViewModel(
        FakeSettingsStore(AppSettings()),
        backup_root=tmp_path / "backups",
        save_chooser=chooser,
        game_chooser=chooser,
    )

    vm.chooseSaveRoot()
    vm.chooseSaveRoot()
    vm.chooseGameInstallRoot()
    vm.chooseGameInstallRoot()

    assert vm.saveRoot == str(save_root)
    assert vm.gameInstallRoot == str(game_root)
    assert vm.hasUnsavedChanges is True


def test_reload_discards_dirty_draft_and_revalidates_persisted_values(
    tmp_path: Path, qapp
) -> None:
    """Reload deve recuperar a configuração salva e limpar o estado de edição."""
    root = tmp_path / "game_data"
    root.mkdir()
    store = FakeSettingsStore(AppSettings(str(root), ""))
    vm = SettingsViewModel(store, backup_root=tmp_path / "backups")

    vm.setSaveRoot(str(tmp_path / "other"))
    assert vm.hasUnsavedChanges is True

    vm.reload()

    assert vm.saveRoot == str(root)
    assert vm.saveRootState == "valid"
    assert vm.hasUnsavedChanges is False
    assert vm.canSave is True
