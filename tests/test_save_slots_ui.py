"""Testes para a interface de slots de save."""

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow, QLabel, QGroupBox, QVBoxLayout


@pytest.fixture(scope="session")
def qt_app() -> QApplication:
    """Cria uma instância global de QApplication para toda a suíte de testes."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSaveSlotsUI:
    """Testes da interface de slots de save."""

    def test_janela_criada_com_loader_vazio(self, qt_app: QApplication) -> None:
        """Teste que janela é criada com loader vazio."""
        from mr_farmboy_manager.application import create_main_window

        def empty_loader() -> list:
            return []

        window = create_main_window(qt_app, loader=empty_loader)
        assert isinstance(window, QMainWindow)

    def test_loader_chamado_exatamente_uma_vez(self, qt_app: QApplication) -> None:
        """Teste que loader é chamado exatamente uma vez."""
        from mr_farmboy_manager.application import create_main_window

        call_count = 0

        def counting_loader() -> list:
            nonlocal call_count
            call_count += 1
            return []

        window = create_main_window(qt_app, loader=counting_loader)
        assert call_count == 1

    def test_estado_vazio_exibido(self, qt_app: QApplication) -> None:
        """Teste que estado vazio é exibido."""
        from mr_farmboy_manager.application import create_main_window

        def empty_loader() -> list:
            return []

        window = create_main_window(qt_app, loader=empty_loader)
        labels = window.findChildren(QLabel)

        texts = [label.text() for label in labels]
        assert "Nenhum save encontrado" in texts

    def test_save_1_exibido(self, qt_app: QApplication) -> None:
        """Teste que save_1 é exibido."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot = SaveSlot(number=1, path=Path("save_1"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)
        labels = window.findChildren(QLabel)

        # Filtra apenas labels que não são o "Projeto em desenvolvimento" nem "Nenhum save encontrado" e não estão vazios
        texts = [label.text() for label in labels if "Projeto em desenvolvimento" not in label.text() and "Nenhum save encontrado" not in label.text() and label.text().strip()]
        assert "save_1" in texts[0]

    def test_numero_do_slot_exibido(self, qt_app: QApplication) -> None:
        """Teste que número do slot é exibido."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot = SaveSlot(number=5, path=Path("save_5"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)
        labels = window.findChildren(QLabel)

        texts = [label.text() for label in labels if "Projeto em desenvolvimento" not in label.text() and "Nenhum save encontrado" not in label.text() and label.text().strip()]
        assert "Slot 5" in texts[0]

    def test_contagem_de_tres_exibida(self, qt_app: QApplication) -> None:
        """Teste que contagem de .tres é exibida."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot = SaveSlot(number=1, path=Path("save_1"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)
        labels = window.findChildren(QLabel)

        texts = [label.text() for label in labels if "Projeto em desenvolvimento" not in label.text() and "Nenhum save encontrado" not in label.text() and label.text().strip()]
        assert "4 arquivos .tres" in texts[0]

    def test_multiplos_resumos_mantem_ordem(self, qt_app: QApplication) -> None:
        """Teste que múltiplos resumos mantêm a ordem recebida."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot_1 = SaveSlot(number=3, path=Path("save_3"))
        slot_2 = SaveSlot(number=1, path=Path("save_1"))
        slot_3 = SaveSlot(number=2, path=Path("save_2"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot_1, "tres_file_count": 4})(),
                type("SaveSlotSummary", (), {"slot": slot_2, "tres_file_count": 4})(),
                type("SaveSlotSummary", (), {"slot": slot_3, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)
        labels = window.findChildren(QLabel)

        # Filtra apenas labels que não são o "Projeto em desenvolvimento" nem "Nenhum save encontrado" e não estão vazios
        texts = [label.text() for label in labels if "Projeto em desenvolvimento" not in label.text() and "Nenhum save encontrado" not in label.text() and label.text().strip()]

        assert "save_3" in texts[0]
        assert "save_1" in texts[1]
        assert "save_2" in texts[2]

    def test_estado_vazio_nao_aparece_com_resumos(self, qt_app: QApplication) -> None:
        """Teste que estado vazio não aparece quando existem resumos."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot = SaveSlot(number=1, path=Path("save_1"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)

        # Busca o label pelo objectName
        empty_label = window.findChild(QLabel, "empty_save_slots_label")
        assert empty_label is not None
        assert empty_label.isHidden()

    def test_widgets_tem_object_names(self, qt_app: QApplication) -> None:
        """Teste que widgets possuem os objectName definidos."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import SaveSlot

        slot = SaveSlot(number=1, path=Path("save_1"))

        def loader() -> list:
            return [
                type("SaveSlotSummary", (), {"slot": slot, "tres_file_count": 4})(),
            ]

        window = create_main_window(qt_app, loader=loader)

        group = window.findChild(QGroupBox, "save_slots_group")
        assert group is not None

    def test_loader_injetado_impede_uso_do_loader_padrao(self, qt_app: QApplication, monkeypatch) -> None:
        """Teste que loader injetado impede uso do loader padrão."""
        from mr_farmboy_manager.application import create_main_window
        from mr_farmboy_manager.save_slots import build_save_slot_summaries

        call_count = 0

        def failing_loader() -> list:
            return []

        def make_failing() -> None:
            nonlocal call_count
            original = build_save_slot_summaries
            def counting(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return original(*args, **kwargs)
            monkeypatch.setattr("mr_farmboy_manager.application.build_save_slot_summaries", counting)

        make_failing()

        def loader() -> list:
            return []

        window = create_main_window(qt_app, loader=loader)
        assert call_count == 0
