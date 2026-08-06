"""Testes para o módulo save_slots - Tarefa 3.1."""

import os
from pathlib import Path

import pytest

from mr_farmboy_manager.save_slots import (
    SaveSlot,
    resolve_game_data_path,
    discover_save_slots,
    inventory_tres_files,
)


class TestSaveSlot:
    """Testes da dataclass SaveSlot."""

    def test_save_slot_is_frozen(self):
        """Teste que SaveSlot é imutável."""
        slot = SaveSlot(number=1, path=Path("save_1"))

        with pytest.raises(AttributeError):
            slot.number = 2

    def test_save_slot_name_property(self):
        """Teste que o nome do slot é extraído corretamente."""
        slot = SaveSlot(number=5, path=Path("save_5"))
        assert slot.name == "save_5"


class TestResolveGameDataPath:
    """Testes de resolução do caminho game_data."""

    def test_resolve_game_data_path_with_appdata(self, tmp_path):
        """Teste que resolve_game_data_path() usa appdata_path corretamente."""
        appdata_dir = tmp_path / "appdata"
        appdata_dir.mkdir()

        result = resolve_game_data_path(appdata_path=appdata_dir)

        expected = appdata_dir / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        assert result == expected

    def test_resolve_game_data_path_without_appdata(self, tmp_path):
        """Teste que resolve_game_data_path() retorna None quando appdata_path é None e APPDATA não existe."""
        # Remove APPDATA do ambiente
        import os
        original_appdata = os.environ.get("APPDATA")
        if original_appdata is not None:
            del os.environ["APPDATA"]

        try:
            result = resolve_game_data_path()
            assert result is None
        finally:
            # Restaura APPDATA
            if original_appdata is not None:
                os.environ["APPDATA"] = original_appdata




class TestDiscoverSaveSlots:
    """Testes de descoberta de slots."""

    def test_discover_save_slots_finds_single_slot(self, tmp_path):
        """Teste que discover_save_slots() encontra um slot válido."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slot
        (game_data_dir / "save_1").mkdir()

        slots = discover_save_slots(base_path=game_data_dir)

        assert len(slots) == 1
        assert slots[0].number == 1
        assert slots[0].path.name == "save_1"

    def test_discover_save_slots_finds_multiple_slots(self, tmp_path):
        """Teste que discover_save_slots() encontra múltiplos slots."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slots
        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_2").mkdir()
        (game_data_dir / "save_3").mkdir()

        slots = discover_save_slots(base_path=game_data_dir)

        assert len(slots) == 3
        assert slots[0].number == 1
        assert slots[1].number == 2
        assert slots[2].number == 3

    def test_discover_save_slots_orders_numerically(self, tmp_path):
        """Teste que discover_save_slots() ordena numericamente (save_2 antes de save_10)."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slots com números variados
        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_2").mkdir()
        (game_data_dir / "save_10").mkdir()
        (game_data_dir / "save_3").mkdir()

        slots = discover_save_slots(base_path=game_data_dir)

        assert len(slots) == 4
        assert slots[0].number == 1
        assert slots[1].number == 2
        assert slots[2].number == 3
        assert slots[3].number == 10

    def test_discover_save_slots_ignores_invalid_names(self, tmp_path):
        """Teste que discover_save_slots() ignora nomes inválidos."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        # Cria slots válidos e inválidos
        (game_data_dir / "save_1").mkdir()
        (game_data_dir / "save_backup").mkdir()  # Deve ser ignorado
        (game_data_dir / "save_x").mkdir()  # Deve ser ignorado
        (game_data_dir / "save_abc").mkdir()  # Deve ser ignorado
        (game_data_dir / "save_10").mkdir()  # Válido

        slots = discover_save_slots(base_path=game_data_dir)

        assert len(slots) == 2
        assert slots[0].number == 1
        assert slots[1].number == 10

    def test_discover_save_slots_returns_empty_when_no_slots(self, tmp_path):
        """Teste que discover_save_slots() retorna lista vazia quando nenhum slot existe."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slots = discover_save_slots(base_path=game_data_dir)

        assert len(slots) == 0

    def test_discover_save_slots_returns_empty_when_game_data_does_not_exist(self, tmp_path):
        """Teste que discover_save_slots() retorna lista vazia quando game_data não existe."""
        slots = discover_save_slots(base_path=tmp_path)

        assert len(slots) == 0


class TestInventoryTresFiles:
    """Testes de inventário de arquivos .tres."""

    def test_inventory_tres_files_counts_tres_in_slot(self, tmp_path):
        """Teste que inventory_tres_files() conta arquivos .tres no slot."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        # Cria arquivos .tres
        (slot_dir / "plantas.tres").touch()
        (slot_dir / "estoque.json").touch()  # Não deve ser contado
        (slot_dir / "dados.TRES").touch()  # Case-insensitive

        count = inventory_tres_files(slot_dir)

        assert count == 2

    def test_inventory_tres_files_counts_recursive(self, tmp_path):
        """Teste que inventory_tres_files() conta recursivamente em subpastas."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        subpasta = slot_dir / "subpasta"
        subpasta.mkdir()

        # Cria arquivos em subpastas
        (slot_dir / "root.tres").touch()
        (subpasta / "nested.tres").touch()
        deep_dir = subpasta / "mais_nivel" / "deep.tres"
        deep_dir.parent.mkdir(parents=True, exist_ok=True)
        deep_dir.touch()

        count = inventory_tres_files(slot_dir)

        assert count == 3

    def test_inventory_tres_files_returns_zero_when_no_tres(self, tmp_path):
        """Teste que inventory_tres_files() retorna 0 quando não há arquivos .tres."""
        game_data_dir = tmp_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
        game_data_dir.mkdir(parents=True)

        slot_dir = game_data_dir / "save_1"
        slot_dir.mkdir()

        # Cria apenas arquivos não .tres
        (slot_dir / "dados.json").touch()
        (slot_dir / "config.dat").touch()

        count = inventory_tres_files(slot_dir)

        assert count == 0

    def test_inventory_tres_files_returns_zero_when_slot_does_not_exist(self, tmp_path):
        """Teste que inventory_tres_files() retorna 0 quando o slot não existe."""
        count = inventory_tres_files(Path("/nonexistent/path"))

        assert count == 0
