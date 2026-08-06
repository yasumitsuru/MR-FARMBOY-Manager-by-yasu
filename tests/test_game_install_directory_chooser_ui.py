"""Testes para o seletor de diretório de instalação injetável."""

import pytest
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLineEdit,
    QPushButton,
)


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestGameInstallDirectoryChooserUI:
    """Testes do seletor de diretório de instalação injetável."""

    def test_criacao_janela_nao_chama_chooser(self, qt_app: QApplication) -> None:
        """Teste 1: criação da janela não chama chooser."""
        from mr_farmboy_manager.application import create_main_window

        called = False

        def chooser() -> Path | None:
            nonlocal called
            called = True
            return None

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)
        assert called is False

    def test_clique_chama_chooser_uma_vez(self, qt_app: QApplication) -> None:
        """Teste 2: clique chama chooser exatamente uma vez."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def chooser() -> Path | None:
            nonlocal call_count
            call_count += 1
            return Path("C:/Games/MR FARMBOY")

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        browse_game_install_button.click()
        QApplication.processEvents()

        assert call_count == 1

        window.close()

    def test_retorno_path_preenche_game_install_path_input(self, qt_app: QApplication) -> None:
        """Teste 3: retorno Path("C:/Games/MR FARMBOY") preenche game_install_path_input."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return Path("C:/Games/MR FARMBOY")

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")
        assert game_install_path_input is not None

        browse_game_install_button.click()
        QApplication.processEvents()

        # Path converte para o formato do sistema operacional
        assert game_install_path_input.text() == "C:\\Games\\MR FARMBOY"

        window.close()

    def test_retorno_none_preserva_campo_vazio(self, qt_app: QApplication) -> None:
        """Teste 4: retorno None preserva campo vazio."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return None

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")
        assert game_install_path_input is not None

        initial_text = game_install_path_input.text()

        browse_game_install_button.click()
        QApplication.processEvents()

        assert game_install_path_input.text() == initial_text

        window.close()

    def test_retorno_none_preserva_texto_ja_existente(self, qt_app: QApplication) -> None:
        """Teste 5: retorno None preserva texto já existente."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return None

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")
        assert game_install_path_input is not None

        # Define texto manualmente
        game_install_path_input.setText("C:/MeusJogos/Existente")

        browse_game_install_button.click()
        QApplication.processEvents()

        assert game_install_path_input.text() == "C:/MeusJogos/Existente"

        window.close()

    def test_clique_nao_altera_save_path_input(self, qt_app: QApplication) -> None:
        """Teste 6: clique não altera save_path_input."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return Path("C:/Games/MR FARMBOY")

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        initial_text = save_path_input.text()

        browse_game_install_button.click()
        QApplication.processEvents()

        assert save_path_input.text() == initial_text

        window.close()

    def test_botao_saves_nao_chama_game_install_directory_chooser(self, qt_app: QApplication) -> None:
        """Teste 7: botão dos saves não chama game_install_directory_chooser."""
        from mr_farmboy_manager.application import create_main_window

        called = False

        def chooser() -> Path | None:
            nonlocal called
            called = True
            return Path("C:/Games/MR FARMBOY")

        window = create_main_window(qt_app, game_install_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        browse_save_path_button.click()
        QApplication.processEvents()

        assert called is False

        window.close()

    def test_absencia_de_chooser_nao_causa_erro(self, qt_app: QApplication) -> None:
        """Teste 8: ausência de chooser não causa erro."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        # Clique sem chooser injetado não deve causar erro
        browse_game_install_button.click()
        QApplication.processEvents()

        window.close()

    def test_botao_load_saves_continua_habilitado(self, qt_app: QApplication) -> None:
        """Teste 9: botão load_saves_button continua habilitado."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        load_saves_button = window.findChild(QPushButton, "load_saves_button")
        assert load_saves_button is not None
        assert load_saves_button.isEnabled()
