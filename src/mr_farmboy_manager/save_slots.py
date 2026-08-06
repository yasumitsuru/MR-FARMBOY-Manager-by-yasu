"""Módulo de localização de slots de save.

Responsável por:
- Resolver o caminho base dos saves usando APPDATA
- Descobrir diretórios save_<número> na pasta game_data
- Inventariar arquivos .tres dentro dos slots
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SaveSlot:
    """Representa um slot de save válido.

    Attributes:
        number: Número do slot (ex: 1 para save_1).
        path: Caminho absoluto do diretório do slot.
    """

    number: int
    path: Path

    @property
    def name(self) -> str:
        """Retorna o nome do diretório do slot."""
        return self.path.name


def resolve_game_data_path(
    appdata_path: Path | str | None = None,
) -> Path | None:
    """Resolve o caminho base dos saves.

    Args:
        appdata_path: Caminho de APPDATA para injeção. Se None, usa os.getenv("APPDATA").

    Returns:
        Path apontando para %APPDATA%\\Godot\\app_userdata\\MR FARMBOY\\game_data,
        ou None se APPDATA não existir.
    """
    if appdata_path is None:
        appdata = os.getenv("APPDATA")
        if appdata is None:
            return None
        appdata_path = Path(appdata)
    else:
        appdata_path = Path(appdata_path)

    base_path = appdata_path / "Godot" / "app_userdata" / "MR FARMBOY" / "game_data"
    return base_path


def discover_save_slots(base_path: Path | None = None) -> list[SaveSlot]:
    """Descobre slots de save (save_<número>) na pasta game_data.

    Args:
        base_path: Caminho base para busca. Se None, usa resolve_game_data_path().

    Returns:
        Lista ordenada numericamente de SaveSlot.
        Retorna lista vazia se nenhum slot for encontrado.
    """
    if base_path is None:
        base_path = resolve_game_data_path()
        if base_path is None:
            return []

    if not base_path.exists() or not base_path.is_dir():
        return []

    slots: list[SaveSlot] = []

    for item in base_path.iterdir():
        if not item.is_dir():
            continue

        # Filtra apenas save_<número> (ex: save_1, save_2, não save_backup)
        name = item.name
        if not name.startswith("save_"):
            continue

        number_part = name[5:]  # Remove "save_"

        # Verifica se é número inteiro válido
        try:
            number = int(number_part)
            slots.append(SaveSlot(number=number, path=item))
        except ValueError:
            continue

    # Ordena numericamente (save_2 antes de save_10)
    slots.sort(key=lambda s: s.number)

    return slots


def inventory_tres_files(slot_path: Path) -> int:
    """Conta arquivos .tres recursivamente dentro de um slot.

    Args:
        slot_path: Caminho do slot save_<número>.

    Returns:
        Número total de arquivos com extensão .tres (case-insensitive).
    """
    if not slot_path.exists() or not slot_path.is_dir():
        return 0

    count = 0

    for path in slot_path.rglob("*"):
        if path.is_file():
            # Case-insensitive check
            if path.suffix.lower() == ".tres":
                count += 1

    return count
