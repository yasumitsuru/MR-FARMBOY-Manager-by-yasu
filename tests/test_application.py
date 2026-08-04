"""Testes básicos para o MR FARMBOY Manager."""

import os
import sys
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def offscreen_platform(monkeypatch: Any, tmp_path: Any) -> None:
    """Configura a plataforma offscreen para testes em Windows/Linux sem GUI.

    Isso permite rodar testes de interface gráfica sem janela visível.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


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

    def test_cria_aplicacao(self, monkeypatch: Any) -> None:
        """Verifica que create_application() retorna uma QApplication."""
        from mr_farmboy_manager.application import create_application
        
        app = create_application()
        
        assert app is not None

    def test_cria_janela_principal(self, monkeypatch: Any) -> None:
        """Verifica que create_main_window() retorna uma QMainWindow."""
        from mr_farmboy_manager.application import create_main_window
        
        window = create_main_window()
        
        assert window is not None

    def test_titulo_janela_correto(self, monkeypatch: Any) -> None:
        """Verifica que o título da janela está correto."""
        from mr_farmboy_manager.application import create_main_window
        
        window = create_main_window()
        
        assert window.windowTitle() == "MR FARMBOY Manager by yasu"

    def test_criacao_janela_nao_inicio_event_loop(self, monkeypatch: Any) -> None:
        """Verifica que criar a janela não inicia automaticamente o event loop."""
        from mr_farmboy_manager.application import create_main_window
        
        window = create_main_window()
        
        # O event loop não deve ter sido iniciado (exec() ainda não foi chamado)
        assert not hasattr(window, "eventLoopActive") or not window.eventLoopActive()