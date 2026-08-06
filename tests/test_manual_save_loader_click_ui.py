"""Testes para a conexão do clique do botão de carregar saves."""

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QLineEdit


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestManualSaveLoaderClick:
    """Testes da conexão do clique do botão de carregar saves."""

    def test_creation_does_not_call_manual_save_loader(
        self, qt_app: QApplication
    ) -> None:
        """Teste 1: criação da janela não chama manual_save_loader."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def loader(path: str) -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        assert call_count == 0
        window.close()

    def test_one_click_calls_loader_exactly_once(
        self, qt_app: QApplication
    ) -> None:
        """Teste 2: um clique chama o loader exatamente uma vez."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def loader(path: str) -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None

        button.click()
        QApplication.processEvents()

        assert call_count == 1
        window.close()

    def test_two_clicks_call_loader_exactly_twice(
        self, qt_app: QApplication
    ) -> None:
        """Teste 3: dois cliques chamam o loader exatamente duas vezes."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def loader(path: str) -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None

        button.click()
        QApplication.processEvents()

        button.click()
        QApplication.processEvents()

        assert call_count == 2
        window.close()

    def test_exact_text_of_save_path_input_is_sent(
        self, qt_app: QApplication
    ) -> None:
        """Teste 4: o texto exato de save_path_input é enviado."""
        from mr_farmboy_manager.application import create_main_window

        sent_paths: list[str] = []

        def loader(path: str) -> list:
            sent_paths.append(path)
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        save_path_input.setText("/caminho/destino/save")
        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None

        button.click()
        QApplication.processEvents()

        assert sent_paths == ["/caminho/destino/save"]
        window.close()

    def test_text_with_spaces_is_sent_without_strip(
        self, qt_app: QApplication
    ) -> None:
        """Teste 5: texto com espaços é enviado sem strip."""
        from mr_farmboy_manager.application import create_main_window

        sent_paths: list[str] = []

        def loader(path: str) -> list:
            sent_paths.append(path)
            return []

        window = create_main_window(qt_app, manual_save_loader=loader)

        save_path_input = window.findChild(QLineEdit, "save_path_input")
        assert save_path_input is not None

        save_path_input.setText("  caminho com espaços  ")
        button = window.findChild(QPushButton, "load_saves_button")
        assert button is not None

        button.click()
        QApplication.processEvents()

        assert sent_paths == ["  caminho com espaços  "]
        window.close()
