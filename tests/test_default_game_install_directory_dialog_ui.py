"""Testes para fallback do diálogo padrão da pasta de instalação."""

from __future__ import annotations

import pytest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestDefaultGameInstallDirectoryDialog:
    """Testes do fallback QFileDialog da pasta de instalação."""

    def test_fallback_abre_dialogo_e_preenche_campo(
        self, qt_app: QApplication
    ) -> None:
        """Teste 1: fallback abre diálogo e preenche campo."""
        from mr_farmboy_manager.application import create_main_window

        with patch(
            "mr_farmboy_manager.application.QFileDialog.getExistingDirectory",
            return_value="S:/MR FARMBOY/game-install",
        ) as mock_dialog:
            window = create_main_window(qt_app)

            browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
            game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")

            assert browse_game_install_button is not None
            assert game_install_path_input is not None

            browse_game_install_button.click()
            qt_app.processEvents()

            # Diálogo chamado exatamente uma vez
            assert mock_dialog.call_count == 1

            # Campo preenchido com o caminho retornado
            assert game_install_path_input.text() == "S:/MR FARMBOY/game-install"

            window.close()

    def test_cancelar_preserva_texto(
        self, qt_app: QApplication
    ) -> None:
        """Teste 2: cancelar preserva texto."""
        from mr_farmboy_manager.application import create_main_window

        initial_text = "S:/instalacao/anterior"

        with patch(
            "mr_farmboy_manager.application.QFileDialog.getExistingDirectory",
            return_value="",
        ) as mock_dialog:
            window = create_main_window(qt_app)

            browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
            game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")

            assert browse_game_install_button is not None
            assert game_install_path_input is not None

            # Define texto manualmente antes do clique
            game_install_path_input.setText(initial_text)

            browse_game_install_button.click()
            qt_app.processEvents()

            # Diálogo chamado exatamente uma vez
            assert mock_dialog.call_count == 1

            # Campo preserva o texto original
            assert game_install_path_input.text() == initial_text

            window.close()

    def test_chooser_injetado_tem_prioridade(
        self, qt_app: QApplication
    ) -> None:
        """Teste 3: chooser injetado tem prioridade."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0
        def chooser() -> Path | None:
            nonlocal call_count
            call_count += 1
            return Path("S:/via-chooser-instalacao")

        with patch(
            "mr_farmboy_manager.application.QFileDialog.getExistingDirectory",
            return_value="S:/via-qfiledialog",
        ) as mock_dialog:
            window = create_main_window(qt_app, game_install_directory_chooser=chooser)

            browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
            game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")

            assert browse_game_install_button is not None
            assert game_install_path_input is not None

            browse_game_install_button.click()
            qt_app.processEvents()

            # Chooser injetado chamado exatamente uma vez
            assert call_count == 1

            # QFileDialog NÃO foi chamado
            assert mock_dialog.call_count == 0

            # Campo preenchido pelo chooser injetado (com escape de barra)
            assert game_install_path_input.text() == "S:\\via-chooser-instalacao"

            window.close()
