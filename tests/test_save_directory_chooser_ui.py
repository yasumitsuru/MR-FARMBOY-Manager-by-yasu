"""Testes para o seletor de diretório de saves injetável."""

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


class TestSaveDirectoryChooserUI:
    """Testes do seletor de diretório de saves injetável."""

    def test_criacao_janela_nao_chama_chooser(self, qt_app: QApplication) -> None:
        """Teste 1: criação da janela não chama chooser."""
        from mr_farmboy_manager.application import create_main_window

        called = False

        def chooser() -> Path | None:
            nonlocal called
            called = True
            return None

        window = create_main_window(qt_app, save_directory_chooser=chooser)
        assert called is False

    def test_clique_chama_chooser_uma_vez(self, qt_app: QApplication) -> None:
        """Teste 2: clique chama chooser uma vez."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def chooser() -> Path | None:
            nonlocal call_count
            call_count += 1
            return Path("C:/Saves")

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        browse_save_path_button.click()
        QApplication.processEvents()

        assert call_count == 1

        window.close()

    def test_retorno_path_preenche_save_path_input(self, qt_app: QApplication) -> None:
        """Teste 3: retorno Path("C:/Saves") preenche save_path_input."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return Path("C:/Saves")

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        browse_save_path_button.click()
        QApplication.processEvents()

        # Path converte para o formato do sistema operacional
        assert save_path_input.text() == "C:\\Saves"

        window.close()

    def test_retorno_none_preserva_campo_vazio(self, qt_app: QApplication) -> None:
        """Teste 4: retorno None preserva campo vazio."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return None

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        initial_text = save_path_input.text()

        browse_save_path_button.click()
        QApplication.processEvents()

        assert save_path_input.text() == initial_text

        window.close()

    def test_retorno_none_preserva_texto_existente(self, qt_app: QApplication) -> None:
        """Teste 5: retorno None preserva texto existente."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return None

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        # Define texto manualmente
        save_path_input.setText("C:/MeusSaves/Existente")

        browse_save_path_button.click()
        QApplication.processEvents()

        assert save_path_input.text() == "C:/MeusSaves/Existente"

        window.close()

    def test_clique_nao_altera_game_install_path_input(self, qt_app: QApplication) -> None:
        """Teste 6: clique não altera game_install_path_input."""
        from mr_farmboy_manager.application import create_main_window

        def chooser() -> Path | None:
            return Path("C:/Saves")

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_save_path_button = window.findChild(QPushButton, "browse_save_path_button")
        assert browse_save_path_button is not None

        game_install_path_input = window.findChild(QLineEdit, "game_install_path_input")
        assert game_install_path_input is not None

        initial_text = game_install_path_input.text()

        browse_save_path_button.click()
        QApplication.processEvents()

        assert game_install_path_input.text() == initial_text

        window.close()



    def test_botao_de_instalacao_continua_sem_chamar_chooser(self, qt_app: QApplication) -> None:
        """Teste 8: botão de instalação continua sem chamar o chooser."""
        from mr_farmboy_manager.application import create_main_window

        called = False

        def chooser() -> Path | None:
            nonlocal called
            called = True
            return Path("C:/Saves")

        window = create_main_window(qt_app, save_directory_chooser=chooser)

        browse_game_install_button = window.findChild(QPushButton, "browse_game_install_button")
        assert browse_game_install_button is not None

        browse_game_install_button.click()
        QApplication.processEvents()

        assert called is False

        window.close()

    def test_botao_carregar_saves_continua_habilitado(self, qt_app: QApplication) -> None:
        """Teste 9: botão Carregar saves continua habilitado."""
        from mr_farmboy_manager.application import create_main_window

        window = create_main_window(qt_app)

        load_saves_button = window.findChild(QPushButton, "load_saves_button")
        assert load_saves_button is not None
        assert load_saves_button.isEnabled()

    def test_todos_parametros_anteriores_continuam_aceitos(self, qt_app: QApplication) -> None:
        """Teste 10: todos os parâmetros anteriores de create_main_window continuam aceitos."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlotSummary, build_save_slot_summaries

        # Teste com apenas app (parâmetro original)
        window1 = create_main_window(qt_app)
        assert isinstance(window1, QMainWindow)

        # Teste com loader (parâmetro original)
        def custom_loader() -> list[SaveSlotSummary]:
            return build_save_slot_summaries()

        window2 = create_main_window(qt_app, loader=custom_loader)
        assert isinstance(window2, QMainWindow)

        # Teste com on_slot_selected (parâmetro original)
        selected_slot: SaveSlotSummary | None = None

        def custom_on_selected(slot: SaveSlotSummary) -> None:
            nonlocal selected_slot
            selected_slot = slot

        window3 = create_main_window(qt_app, on_slot_selected=custom_on_selected)
        assert isinstance(window3, QMainWindow)

        # Teste com todos os parâmetros originais
        window4 = create_main_window(
            app=qt_app,
            loader=custom_loader,
            on_slot_selected=custom_on_selected,
        )
        assert isinstance(window4, QMainWindow)
