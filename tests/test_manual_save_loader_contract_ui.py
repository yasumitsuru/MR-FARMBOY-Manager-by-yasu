"""Testes para o contrato do carregador manual de saves."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestManualSaveLoaderContract:
    """Testes do contrato do carregador manual de saves."""

    def test_create_main_window_accepts_manual_save_loader(
        self, qt_app: QApplication
    ) -> None:
        """Teste que create_main_window aceita manual_save_loader."""
        from mr_farmboy_manager.application import (
            create_main_window,
            ManualSaveLoader,
        )

        loader: ManualSaveLoader = lambda: []

        window = create_main_window(qt_app, manual_save_loader=loader)

        assert isinstance(window, QMainWindow)

    def test_creation_does_not_call_loader(
        self, qt_app: QApplication
    ) -> None:
        """Teste que criação da janela não chama o loader."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def loader() -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        assert call_count == 0

    def test_load_saves_button_is_enabled(
        self, qt_app: QApplication
    ) -> None:
        """Teste que load_saves_button está habilitado."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None
        assert button.isEnabled()
