"""Bootstrap mínimo do Qt Quick, com recursos QML embutidos."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from mr_farmboy_manager.presentation.app_controller import AppController
from mr_farmboy_manager.application import (
    create_application,
    runtime_root_from_environment,
)
from mr_farmboy_manager.diagnostics import configure_logging
from mr_farmboy_manager.settings import QtSettingsStore, SettingsStore

# Registra qrc:/qml antes que o engine resolva Main.qml.
from . import _qml_resources  # noqa: F401


LOGGER = logging.getLogger(__name__)


def create_qml_application() -> QApplication:
    """Retorna a aplicação Widgets necessária para os adaptadores QFileDialog."""
    QQuickStyle.setStyle("Basic")
    return create_application()


def create_controller(
    *,
    settings_store: SettingsStore | None = None,
    backup_root: Path | str | None = None,
    log_path: Path | str | None = None,
) -> AppController:
    """Monta os ViewModels reais expostos ao frontend."""
    return AppController(
        settings_store=settings_store,
        backup_root=backup_root,
        log_path=log_path,
    )


def create_engine(controller: AppController) -> QQmlApplicationEngine:
    """Carrega o shell após disponibilizar o controller ao contexto QML."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("appController", controller)
    engine.load(QUrl("qrc:/qml/Main.qml"))
    return engine


def run(*, start_event_loop: bool = True) -> int:
    """Inicializa a UI e sempre encerra o executor do controller."""
    application = create_qml_application()
    runtime_root = runtime_root_from_environment()
    log_path = configure_logging(runtime_root / "logs" if runtime_root is not None else None)
    if runtime_root is None:
        settings_store = QtSettingsStore()
        backup_root = None
    else:
        settings_store = QtSettingsStore(
            QSettings(str(runtime_root / "settings.ini"), QSettings.Format.IniFormat)
        )
        backup_root = runtime_root / "backups"
    controller = create_controller(
        settings_store=settings_store,
        backup_root=backup_root,
        log_path=log_path,
    )
    exit_code = 1
    try:
        LOGGER.info("qml.engine.started")
        engine = create_engine(controller)
        if not engine.rootObjects():
            LOGGER.error("qml.load.failed")
            return 1
        LOGGER.info("qml.load.completed")
        controller.initialize()
        LOGGER.info("qml.controller.initialized")
        exit_code = application.exec() if start_event_loop else 0
        return exit_code
    finally:
        controller.shutdown()
        LOGGER.info("qml.application.shutdown exit_code=%d", exit_code)


__all__ = ["create_controller", "create_engine", "create_qml_application", "run"]
