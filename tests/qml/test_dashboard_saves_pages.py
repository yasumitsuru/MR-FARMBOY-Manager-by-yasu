"""Contratos de integração bidirecional das páginas Dashboard e Saves."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt, qInstallMessageHandler
from PySide6.QtQuickControls2 import QQuickStyle


def _find(root: QObject, name: str) -> QObject:
    found = root.findChild(QObject, name)
    assert found is not None, f"Ponto estável ausente: {name}"
    return found


def _show_saves(root: QObject) -> None:
    _find(root, "appShell").setProperty("currentIndex", 1)


def test_basic_style_is_selected_before_any_qapplication_fixture() -> None:
    assert QQuickStyle.name() == "Basic"


def test_python_state_reaches_dashboard_and_saves(qapp, qml_shell, fake_controller) -> None:
    fake_controller.dashboard.set_fixture_values(2, 8)
    fake_controller.saves.model_fixture_slots((1, 2))
    qapp.processEvents()

    assert _find(qml_shell, "dashboardSlotCount").property("text") == "2"
    assert _find(qml_shell, "saveSlotsList").property("count") == 2


def test_refresh_button_reaches_python(qapp, qml_shell, fake_controller) -> None:
    _show_saves(qml_shell)
    button = _find(qml_shell, "refreshSavesButton")
    assert QMetaObject.invokeMethod(button, "click", Qt.ConnectionType.DirectConnection)
    qapp.processEvents()

    assert fake_controller.saves.refresh_calls == 1


@pytest.mark.parametrize("state", ["loading", "empty", "error"])
def test_saves_states_are_rendered_inside_the_panel(qapp, qml_shell, fake_controller, state: str) -> None:
    _show_saves(qml_shell)
    fake_controller.saves.set_fixture_state(state)
    qapp.processEvents()

    panel = _find(qml_shell, "saveDetailsPanel")
    assert panel.property("visible") is True
    if state == "error":
        assert _find(qml_shell, "savesErrorMessage").property("visible") is True


def test_selected_details_and_narrow_layout_remain_available(qapp, qml_shell, fake_controller) -> None:
    fake_controller.saves.model_fixture_slots((1, 2))
    _show_saves(qml_shell)
    qml_shell.setWidth(960)
    qapp.processEvents()

    assert _find(qml_shell, "savesPage").property("wideLayout") is False
    assert _find(qml_shell, "saveDetailsPanel").property("visible") is True
    assert _find(qml_shell, "saveDetailRecordCount").property("text") == "3"


def test_missing_dashboard_metrics_are_not_invented(qapp, qml_shell, fake_controller) -> None:
    fake_controller.dashboard.set_fixture_values(2, 0)
    qapp.processEvents()

    assert _find(qml_shell, "dashboardCropPanel").property("visible") is True
    assert _find(qml_shell, "dashboardNoSelectionState").property("visible") is True


def test_dashboard_and_saves_have_no_qml_warnings(qapp, fake_controller) -> None:
    from mr_farmboy_manager.qml_application import create_engine

    messages: list[str] = []
    previous = qInstallMessageHandler(lambda _kind, _context, message: messages.append(message))
    try:
        engine = create_engine(fake_controller)
        qapp.processEvents()
    finally:
        qInstallMessageHandler(previous)
    assert engine.rootObjects()
    assert not messages
