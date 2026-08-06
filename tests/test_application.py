"""Testes básicos para o MR FARMBOY Manager."""

import os
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel


@pytest.fixture(scope="session")
def qt_app() -> Any:
    """Cria uma instância global de QApplication para toda a suíte de testes.

    Isso garante que todos os testes de interface usem a mesma instância de QApplication,
    evitando múltiplas inicializações e tornando os testes independentes da ordem.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestPacote:
    """Testes relacionados ao pacote mr_farmboy_manager."""

    def test_importa_pacote(self) -> None:
        """Verifica que o pacote pode ser importado sem erros."""
        import mr_farmboy_manager

        assert mr_farmboy_manager is not None

    def test_verso_esta_correta(self) -> None:
        """Verifica que a versão do pacote é 0.1.0."""
        from mr_farmboy_manager import __version__

        assert __version__ == "0.1.0"


class TestInterface:
    """Testes relacionados à criação da interface gráfica."""

    def test_cria_aplicacao_retorna_qapplication(self, qt_app: Any) -> None:
        """Verifica que create_application() retorna uma QApplication válida."""
        from mr_farmboy_manager.application import create_application

        app = create_application()

        assert isinstance(app, QApplication)

    def test_reutiliza_aplicacao_existente(self, qt_app: Any) -> None:
        """Verifica que create_application() reutiliza instância existente."""
        from mr_farmboy_manager.application import create_application

        app1 = create_application()
        app2 = create_application()

        assert app1 is app2

    def test_cria_janela_principal_retorna_qmainwindow(self, qt_app: Any) -> None:
        """Verifica que create_main_window() retorna uma QMainWindow."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        assert isinstance(window, QMainWindow)

    def test_titulo_janela_correto(self, qt_app: Any) -> None:
        """Verifica que o título da janela está correto."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        assert window.windowTitle() == "MR FARMBOY Manager by yasu"

    def test_tamanho_janela_inicial(self, qt_app: Any) -> None:
        """Verifica que o tamanho inicial é 1000x650 pixels."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        width = window.width()
        height = window.height()

        assert width == 1000
        assert height == 650

    def test_contem_label_desenvolvimento(self, qt_app: Any) -> None:
        """Verifica que a janela contém o label 'Projeto em desenvolvimento'."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        labels = window.findChildren(QLabel)

        assert len(labels) >= 2

        labels_text = [label.text() for label in labels]

        assert "Projeto em desenvolvimento" in labels_text

    def test_contem_label_nenhum_save_encontrado(self, qt_app: Any) -> None:
        """Verifica que a janela contém o label 'Nenhum save encontrado'."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        labels = window.findChildren(QLabel)

        assert len(labels) >= 2

        labels_text = [label.text() for label in labels]

        assert "Nenhum save encontrado" in labels_text

    def test_criacao_janela_nao_inicia_event_loop(self, qt_app: Any) -> None:
        """Verifica que create_main_window() não inicia o event loop automaticamente."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        assert window is not None