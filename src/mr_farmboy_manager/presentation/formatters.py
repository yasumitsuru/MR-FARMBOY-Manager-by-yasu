"""Formatações estáveis e sem caminhos privados para a camada QML."""

from __future__ import annotations

from datetime import UTC, datetime


def format_size_label(size_bytes: int) -> str:
    """Retorna tamanho binário conciso para exibição."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    return f"{size_bytes / 1024:.1f}".replace(".", ",") + " KiB"


def format_created_at_label(value: datetime) -> str:
    """Retorna instante normalizado em UTC, sem dados locais do usuário."""
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
