"""Contratos observáveis das páginas QML de configurações e diagnósticos."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt


def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, f"Ponto estável ausente: {name}"
    return found


def _show(root: QObject, index: int) -> None:
    _find(root, "appShell").setProperty("currentIndex", index)


def _click(item: QObject) -> None:
    assert QMetaObject.invokeMethod(item, "click", Qt.ConnectionType.DirectConnection)


def test_normalized_path_feedback_is_visible(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 3)
    fake_controller.settings.set_fixture_save_root(
        "C:/game_data", "Raiz normalizada para game_data."
    )
    qapp.processEvents()

    assert _find(qml_shell, "saveRootField").property("text") == "C:/game_data"
    assert "normalizada" in _find(qml_shell, "saveRootMessage").property("text").lower()


@pytest.mark.parametrize(
    ("save_state", "game_state", "expected_save", "expected_game"),
    [
        ("valid", "valid", "Válido", "Válido"),
        ("not_found", "not_directory", "Inválido", "Inválido"),
        ("empty", "empty", "Não definido", "Não definido"),
    ],
)
def test_path_badges_cover_valid_invalid_and_unset_states(
    qapp, qml_shell, fake_controller, save_state, game_state, expected_save, expected_game
) -> None:
    _show(qml_shell, 3)
    fake_controller.settings.set_fixture_states(save_state, game_state)
    qapp.processEvents()

    assert _find(qml_shell, "saveRootBadge").property("label") == expected_save
    assert _find(qml_shell, "gameInstallBadge").property("label") == expected_game


def test_dirty_settings_enable_save_and_cancelled_chooser_is_neutral(
    qapp, qml_shell, fake_controller
) -> None:
    _show(qml_shell, 3)
    button = _find(qml_shell, "saveSettingsButton")
    assert button.property("enabled") is False

    fake_controller.settings.setSaveRoot("C:/edited")
    qapp.processEvents()
    assert button.property("enabled") is True

    _click(_find(qml_shell, "chooseSaveRootButton"))
    qapp.processEvents()
    assert fake_controller.settings.saveRoot == "C:/edited"

    _click(button)
    qapp.processEvents()
    assert button.property("enabled") is False


def test_diagnostics_empty_error_and_readable_event_text(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 4)
    fake_controller.diagnostics.set_fixture_events("", "Log indisponível.")
    qapp.processEvents()
    assert "indisponível" in _find(qml_shell, "diagnosticsEvents").property("text").lower()

    fake_controller.diagnostics.set_fixture_events("evento longo\ncom detalhes", "Não foi possível ler o log.")
    qapp.processEvents()
    events = _find(qml_shell, "diagnosticsEvents")
    assert events.property("selectByMouse") is True
    assert events.property("wrapsText") is True
    assert "não foi possível" in _find(qml_shell, "diagnosticsStatus").property("text").lower()


def test_pages_keep_a_single_outer_scroll_view_when_narrow(qapp, qml_shell) -> None:
    qml_shell.setWidth(360)
    _show(qml_shell, 3)
    qapp.processEvents()
    assert _find(qml_shell, "settingsPage").property("narrowLayout") is True
    assert _find(qml_shell, "settingsScrollView").property("contentWidth") == _find(qml_shell, "settingsScrollView").property("availableWidth")

    _show(qml_shell, 4)
    qapp.processEvents()
    assert _find(qml_shell, "diagnosticsPage").property("narrowLayout") is True
    assert _find(qml_shell, "diagnosticsScrollView").property("contentWidth") == _find(qml_shell, "diagnosticsScrollView").property("availableWidth")


def test_diagnostic_buttons_reach_python(qapp, qml_shell, fake_controller) -> None:
    _show(qml_shell, 4)
    _click(_find(qml_shell, "copyDiagnosticButton"))
    _click(_find(qml_shell, "openLogsButton"))
    qapp.processEvents()

    assert fake_controller.diagnostics.copy_calls == 1
    assert fake_controller.diagnostics.open_calls == 1
