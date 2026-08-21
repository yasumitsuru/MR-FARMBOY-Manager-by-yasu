"""Contrato mínimo bidirecional entre o shell QML e o controller."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from PySide6.QtCore import QObject, QMetaObject, Qt


@dataclass
class QmlRuntime:
    root: QObject
    controller: object
    application: object

    def click(self, object_name: str) -> None:
        button = self.find(object_name)
        assert QMetaObject.invokeMethod(button, "click", Qt.ConnectionType.DirectConnection)

    def find(self, object_name: str) -> QObject:
        found = self.root.findChild(QObject, object_name)
        assert found is not None, f"Ponto estável ausente: {object_name}"
        return found

    def process_events(self) -> None:
        self.application.processEvents()


@pytest.fixture
def qml_runtime(qapp, fake_controller) -> QmlRuntime:
    from mr_farmboy_manager.qml_application import create_engine

    engine = create_engine(fake_controller)
    assert engine.rootObjects()
    runtime = QmlRuntime(engine.rootObjects()[0], fake_controller, qapp)
    yield runtime
    engine.deleteLater()


def test_qml_action_and_python_notify_are_bidirectional(qml_runtime: QmlRuntime) -> None:
    qml_runtime.find("appShell").setProperty("currentIndex", 1)
    qml_runtime.click("refreshSavesButton")
    assert qml_runtime.controller.saves.refresh_calls == 1

    qml_runtime.controller.saves.set_fixture_state("error")
    qml_runtime.process_events()
    assert qml_runtime.find("savesErrorMessage").property("message") == "Não foi possível carregar os saves."
