"""Bootstrap mínimo do Qt Quick, com recursos QML embutidos."""

from __future__ import annotations

import sys

from PySide6.QtCore import QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from mr_farmboy_manager.presentation.app_controller import AppController

# Registra qrc:/qml antes que o engine resolva Main.qml.
from . import _qml_resources  # noqa: F401


def create_qml_application() -> QApplication:
    """Retorna a aplicação Widgets necessária para os adaptadores QFileDialog."""
    QQuickStyle.setStyle("Basic")
    existing = QApplication.instance()
    return existing if isinstance(existing, QApplication) else QApplication(sys.argv)


def create_controller() -> AppController:
    """Monta os ViewModels reais expostos ao frontend."""
    return AppController()


def create_engine(controller: AppController) -> QQmlApplicationEngine:
    """Carrega o shell após disponibilizar o controller ao contexto QML."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("appController", controller)
    engine.load(QUrl("qrc:/qml/Main.qml"))
    return engine


def run(*, start_event_loop: bool = True) -> int:
    """Inicializa a UI e sempre encerra o executor do controller."""
    application = create_qml_application()
    controller = create_controller()
    try:
        controller.initialize()
        engine = create_engine(controller)
        if not engine.rootObjects():
            return 1
        return application.exec() if start_event_loop else 0
    finally:
        controller.shutdown()


__all__ = ["create_controller", "create_engine", "create_qml_application", "run"]
