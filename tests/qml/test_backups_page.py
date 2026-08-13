"""Contratos observáveis da página QML de backups."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt


def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, f"Ponto estável ausente: {name}"
    return found


def _show_backups(root: QObject) -> None:
    _find(root, "appShell").setProperty("currentIndex", 2)


def _click(item: QObject) -> None:
    assert QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)


def test_delete_opens_dialog_before_python_confirmation(qapp, qml_shell, fake_controller) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    _show_backups(qml_shell)
    _click(_find(qml_shell, "deleteBackupButton"))
    qapp.processEvents()

    assert _find(qml_shell, "backupConfirmDialog").property("visible") is True
    assert fake_controller.backups.confirm_calls == []


def test_dialog_uses_immutable_backup_identity_and_cancel_does_not_mutate(qapp, qml_shell, fake_controller) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    _show_backups(qml_shell)
    _click(_find(qml_shell, "deleteBackupButton"))
    dialog = _find(qml_shell, "backupConfirmDialog")
    fake_controller.backups._selected_backup_id = "other-backup"
    fake_controller.backups.changed.emit()
    _click(_find(dialog, "confirmDialogCancelButton"))
    qapp.processEvents()

    assert fake_controller.backups.confirm_calls == []
    assert fake_controller.backups.cancel_calls == 1


def test_delete_confirmation_keeps_copied_values_and_uses_danger_variant(qapp, qml_shell, fake_controller) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    _show_backups(qml_shell)
    _click(_find(qml_shell, "deleteBackupButton"))
    dialog = _find(qml_shell, "backupConfirmDialog")
    fake_controller.backups._selected_backup_id = "other-backup"
    fake_controller.backups.changed.emit()
    _click(_find(dialog, "confirmDialogConfirmButton"))
    qapp.processEvents()

    assert fake_controller.backups.confirm_calls == [("delete", "backup-id")]
    assert _find(dialog, "confirmDialogConfirmButton").property("variant") == "danger"


def test_create_and_restore_controls_reach_their_safe_python_boundaries(qapp, qml_shell, fake_controller) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    _show_backups(qml_shell)
    _click(_find(qml_shell, "createBackupButton"))
    qapp.processEvents()
    assert fake_controller.backups.create_calls == 1

    fake_controller.backups.set_fixture_state("ready")
    _click(_find(qml_shell, "restoreBackupButton"))
    dialog = _find(qml_shell, "backupConfirmDialog")
    assert dialog.property("visible") is True
    _click(_find(dialog, "confirmDialogConfirmButton"))
    assert fake_controller.backups.confirm_calls == [("restore", "backup-id")]


@pytest.mark.parametrize("state", ["loading", "creating", "restoring", "deleting"])
def test_mutating_states_disable_selection_and_conflicting_actions(qapp, qml_shell, fake_controller, state: str) -> None:
    fake_controller.backups.model_fixture_backup("backup-id")
    fake_controller.backups.selectBackup("backup-id")
    fake_controller.backups.set_fixture_state(state)
    _show_backups(qml_shell)
    qapp.processEvents()

    assert _find(qml_shell, "createBackupButton").property("enabled") is False
    assert _find(qml_shell, "restoreBackupButton").property("enabled") is False
    assert _find(qml_shell, "deleteBackupButton").property("enabled") is False
    assert _find(qml_shell, "backupsList").property("interactive") is False
    assert _find(qml_shell, "backupIdentityLabel").property("text") == "backup-id"


def test_backups_page_exposes_adaptive_layout_and_empty_error_states(qapp, qml_shell, fake_controller) -> None:
    _show_backups(qml_shell)
    page = _find(qml_shell, "backupsPage")
    qml_shell.setWidth(1400)
    qapp.processEvents()
    assert page.property("wideLayout") is True
    assert _find(qml_shell, "backupsEmptyState").property("visible") is True

    qml_shell.setWidth(900)
    fake_controller.backups.set_fixture_state("error")
    qapp.processEvents()
    assert page.property("wideLayout") is False
    assert _find(qml_shell, "backupsErrorMessage").property("visible") is True
