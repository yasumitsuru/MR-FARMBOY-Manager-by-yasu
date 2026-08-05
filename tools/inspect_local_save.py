#!/usr/bin/env python3
"""Ferramenta de linha de comando para inspeção sanitizada de saves locais.

Esta ferramenta permite inspecionar um arquivo de save real sem:
- Modificar o original
- Gravar o caminho no repositório
- Revelar conteúdo sensível
- Usar rede

Uso:
    python inspect_local_save.py <caminho_do_save> [--output <destino_fora_do_repo>]

Nota importante:
    - O caminho do arquivo de entrada nunca é incluído no relatório
    - O diretório de saída NÃO deve estar dentro do repositório Git
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


# Adiciona o diretório src ao path para imports
SCRIPT_DIR = Path(__file__).parent.parent.resolve()


def is_path_outside_repository(output_path: Path) -> bool:
    """Verifica se um caminho está fora do diretório do repositório Git.

    Usa is_relative_to() (Python 3.9+) para comparação segura.
    Retorna False se dentro do repositório, True se fora.
    """
    try:
        resolved_output = output_path.resolve()
        return not resolved_output.is_relative_to(SCRIPT_DIR)
    except AttributeError:
        # Fallback para versões mais antigas do Python
        str_output = str(resolved_output)
        str_script = str(SCRIPT_DIR)
        return not (str_output.startswith(str_script + os.sep) or str_output == str_script)


def main() -> int:
    """Executa a ferramenta CLI com sanitização de caminhos.

    Retorna 0 em caso de sucesso, diferente de zero em caso de erro.
    Nunca grava caminho no repositório nem revela informações sensíveis.
    """
    import argparse
    from mr_farmboy_manager.save_discovery import (
        discover_save_structure,
        format_sanitized_report,
    )

    parser = argparse.ArgumentParser(
        description='Inspeção sanitizada local de saves do MR FARMBOY',
        epilog='O arquivo original NÃO será modificado.'
    )

    parser.add_argument(
        "save_path",
        help=r"Caminho local do save a ser inspecionado"
    )

    parser.add_argument(
        "--output", "-o",
        help="Caminho para salvar o relatório (deve estar fora do repositório Git)",
        default=None
    )

    args = parser.parse_args()

    # Verifica se é arquivo válido
    save_path = Path(args.save_path)

    if not save_path.exists():
        print("Erro: Caminho selecionado não existe.", file=sys.stderr)
        return 1

    if not save_path.is_file():
        print("Erro: Caminho aponta para um diretório, não para um arquivo.", file=sys.stderr)
        return 1

    try:
        # Importa módulo de descoberta após verificar argumentos
        from mr_farmboy_manager.save_discovery import (
            discover_save_structure,
            format_sanitized_report,
        )

        # Executa descoberta estrutural
        result = discover_save_structure(str(save_path))

        if not result.success:
            report = format_sanitized_report(result)
            print(report, file=sys.stderr)
            return 1

        # Formata relatório sanitizado
        report = format_sanitized_report(result)

        # Escreve no console ou arquivo
        output_file = args.output

        if output_file:
            output_path = Path(output_file)

            # Verifica se saída está dentro do repositório Git
            if not is_path_outside_repository(output_path):
                print("Erro: O destino deve estar fora do repositório Git.")
                return 1

            try:
                output_path.write_text(report, encoding='utf-8')
                print("Relatório salvo com sucesso.")
            except PermissionError:
                print("Erro: Sem permissão para escrever no diretório de saída.", file=sys.stderr)
                return 1
            except OSError:
                print("Erro ao salvar relatório.", file=sys.stderr)
                return 1
        else:
            print(report)

        return 0

    except ImportError:
        print("Erro: Não foi possível carregar o módulo de descoberta.", file=sys.stderr)
        return 2
    except Exception:
        print("Erro: Não foi possível processar o arquivo selecionado.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())