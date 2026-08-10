"""Fixtures isoladas para o shell QML."""

from __future__ import annotations

import pytest
from PySide6.QtQml import QQmlApplicationEngine

from .fakes import FakeController


@pytest.fixture
def fake_controller() -> FakeController:
    return FakeController()


@pytest.fixture
def qml_shell(qapp, fake_controller: FakeController):
    from mr_farmboy_manager.qml_application import create_engine

    engine = create_engine(fake_controller)
    assert engine.rootObjects(), "O shell QML deve carregar durante a fixture."
    yield engine.rootObjects()[0]
    engine.deleteLater()
