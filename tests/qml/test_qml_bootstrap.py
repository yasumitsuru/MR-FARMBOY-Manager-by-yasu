"""Contratos do carregamento do shell QML embutido."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent, QQmlEngine

from mr_farmboy_manager.qml_application import create_engine, run


def test_qml_engine_loads_main_window(qapp, fake_controller) -> None:
    engine = create_engine(fake_controller)
    roots = engine.rootObjects()

    assert len(roots) == 1
    assert roots[0].objectName() == "mainWindow"
    assert roots[0].property("minimumWidth") == 960
    assert roots[0].findChild(object, "pageStack") is not None


def test_run_returns_nonzero_when_qml_creates_no_root(monkeypatch, qapp, fake_controller) -> None:
    engine = Mock(spec=QQmlApplicationEngine)
    engine.rootObjects.return_value = []
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda: fake_controller)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_engine", lambda controller: engine)

    assert run(start_event_loop=False) == 1
    assert fake_controller.initialize_calls == 1
    assert fake_controller.shutdown_calls == 1


def test_run_shuts_down_controller_after_noninteractive_start(monkeypatch, qapp, fake_controller) -> None:
    engine = Mock(spec=QQmlApplicationEngine)
    engine.rootObjects.return_value = [object()]
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_qml_application", lambda: qapp)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_controller", lambda: fake_controller)
    monkeypatch.setattr("mr_farmboy_manager.qml_application.create_engine", lambda controller: engine)

    assert run(start_event_loop=False) == 0
    assert fake_controller.initialize_calls == 1
    assert fake_controller.shutdown_calls == 1


@pytest.mark.parametrize(
    "component_name",
    [
        "AppCard",
        "AppButton",
        "MetricCard",
        "StatusBadge",
        "SidebarItem",
        "SectionHeader",
        "EmptyState",
        "InlineMessage",
        "InfoRow",
        "ConfirmActionDialog",
    ],
)
def test_qml_component_compiles_without_import_errors(qapp, component_name: str) -> None:
    engine = QQmlEngine()
    component = QQmlComponent(engine, QUrl(f"qrc:/qml/components/{component_name}.qml"))

    assert component.isReady(), [str(error) for error in component.errors()]
