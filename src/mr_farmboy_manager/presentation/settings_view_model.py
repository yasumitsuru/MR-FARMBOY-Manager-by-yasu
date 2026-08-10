"""View model de configurações validado para consumo direto pelo QML."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from mr_farmboy_manager.manual_paths import (
    DirectoryValidationCode,
    DirectoryValidationResult,
    validate_directory_path,
    validate_save_root_path,
)
from mr_farmboy_manager.settings import AppSettings, SettingsStore


DirectoryChooser = Callable[[], str | None]


class SettingsViewModel(QObject):
    """Mantém um rascunho de caminhos e só persiste valores operacionais válidos."""

    changed = Signal()
    settingsApplied = Signal(str, str)

    def __init__(
        self,
        store: SettingsStore,
        backup_root: Path,
        save_chooser: DirectoryChooser | None = None,
        game_chooser: DirectoryChooser | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._backup_root = backup_root
        self._save_chooser = save_chooser or self._choose_directory
        self._game_chooser = game_chooser or self._choose_directory
        self._save_root = ""
        self._game_install_root = ""
        self._save_validation = validate_save_root_path("")
        self._game_validation = validate_directory_path("")
        self._save_root_message = ""
        self._game_install_message = ""
        self._persisted = AppSettings()
        self.reload()

    @Slot(str)
    def setSaveRoot(self, value: str) -> None:
        before = self._public_values()
        self._set_save_root(value)
        self._notify_if_changed(before)

    @Slot(str)
    def setGameInstallRoot(self, value: str) -> None:
        before = self._public_values()
        self._set_game_install_root(value)
        self._notify_if_changed(before)

    @Slot()
    def chooseSaveRoot(self) -> None:
        chosen = self._save_chooser()
        if chosen:
            self.setSaveRoot(chosen)

    @Slot()
    def chooseGameInstallRoot(self) -> None:
        chosen = self._game_chooser()
        if chosen:
            self.setGameInstallRoot(chosen)

    @Slot()
    def save(self) -> None:
        if not self.canSave:
            return
        settings = AppSettings(self._save_root, self._game_install_root)
        self._store.save(settings)
        before = self._public_values()
        self._persisted = settings
        self._notify_if_changed(before)
        self.settingsApplied.emit(settings.save_directory, settings.game_install_directory)

    @Slot()
    def reload(self) -> None:
        settings = self._store.load()
        before = self._public_values()
        self._set_save_root(settings.save_directory)
        self._set_game_install_root(settings.game_install_directory)
        self._persisted = AppSettings(self._save_root, self._game_install_root)
        self._notify_if_changed(before)

    def _set_save_root(self, value: str) -> None:
        validation = validate_save_root_path(value)
        self._save_validation = validation
        self._save_root = self._display_path(value, validation)
        self._save_root_message = self._message_for(validation, is_save_root=True)

    def _set_game_install_root(self, value: str) -> None:
        validation = validate_directory_path(value)
        self._game_validation = validation
        self._game_install_root = self._display_path(value, validation)
        self._game_install_message = self._message_for(validation, is_save_root=False)

    @staticmethod
    def _display_path(value: str, validation: DirectoryValidationResult) -> str:
        if validation.is_valid and validation.path is not None:
            return str(validation.path)
        return str(value).strip()

    @staticmethod
    def _message_for(
        validation: DirectoryValidationResult, *, is_save_root: bool
    ) -> str:
        if validation.code is DirectoryValidationCode.NORMALIZED:
            return "A pasta do slot foi normalizada para a raiz dos saves."
        if validation.code is DirectoryValidationCode.NOT_FOUND:
            return "Diretório não encontrado."
        if validation.code is DirectoryValidationCode.NOT_DIRECTORY:
            return "O caminho informado não é um diretório."
        if validation.code is DirectoryValidationCode.EMPTY:
            return ""
        return "Diretório de saves válido." if is_save_root else "Diretório do jogo válido."

    @staticmethod
    def _choose_directory() -> str | None:
        selected = QFileDialog.getExistingDirectory(None, "Selecionar diretório")
        return selected or None

    def _public_values(self) -> tuple[str, str, str, str, str, str, bool, bool]:
        return (
            self._save_root,
            self._game_install_root,
            self.saveRootState,
            self.gameInstallState,
            self._save_root_message,
            self._game_install_message,
            self.hasUnsavedChanges,
            self.canSave,
        )

    def _notify_if_changed(
        self, before: tuple[str, str, str, str, str, str, bool, bool]
    ) -> None:
        if self._public_values() != before:
            self.changed.emit()

    saveRoot = Property(str, lambda self: self._save_root, notify=changed)
    gameInstallRoot = Property(str, lambda self: self._game_install_root, notify=changed)
    backupRootLabel = Property(str, lambda self: str(self._backup_root), constant=True)
    saveRootState = Property(
        str,
        lambda self: "valid" if self._save_validation.is_valid else self._save_validation.code.value,
        notify=changed,
    )
    gameInstallState = Property(
        str,
        lambda self: "valid" if self._game_validation.is_valid else self._game_validation.code.value,
        notify=changed,
    )
    saveRootMessage = Property(str, lambda self: self._save_root_message, notify=changed)
    gameInstallMessage = Property(str, lambda self: self._game_install_message, notify=changed)
    hasUnsavedChanges = Property(
        bool,
        lambda self: AppSettings(self._save_root, self._game_install_root) != self._persisted,
        notify=changed,
    )
    canSave = Property(
        bool,
        lambda self: self._save_validation.code
        in {DirectoryValidationCode.EMPTY, DirectoryValidationCode.VALID, DirectoryValidationCode.NORMALIZED}
        and self._game_validation.code
        in {DirectoryValidationCode.EMPTY, DirectoryValidationCode.VALID},
        notify=changed,
    )


__all__ = ["DirectoryChooser", "SettingsViewModel"]
