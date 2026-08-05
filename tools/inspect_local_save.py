#!/usr/bin/env python3
"""Ferramenta de linha de comando para inspeção sanitizada de saves locais.

Esta ferramenta permite inspecionar um arquivo de save real sem:
- Modificar o original
- Gravar o caminho no repositório
- Revelar conteúdo sensível
- Usar rede

Uso:
    python inspect_local_save.py <caminho_do_save> [--output <destino_fora_do_repo>]

Exemplo:
    python inspect_local_save.py "./save.dat"

Nota importante:
    - O caminho do arquivo de entrada nunca é incluído no relatório
    - O diretório de saída NÃO deve estar dentro do repositório Git
"""

from __future__ import annotations

import sys
from pathlib import Path


# Adiciona o diretório src ao path para imports
SCRIPT_DIR = Path(__file__).parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def is_path_outside_repository(path: Path) -> bool:
    """Verifica se um caminho está fora do diretório do repositório Git."""
    repo_root = SCRIPT_DIR.resolve()
    target_path = path.resolve()
    return not str(target_path).startswith(str(repo_root))


def main() -> int:
    """Executa a ferramenta CLI com sanitização de caminhos."""
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
        # Importa módulo de descoberta
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
        output_path = args.output

        if output_path:
            output_file = Path(output_path)

            try:
                resolved_save = str(save_path.resolve())
                resolved_output = str(output_file.resolve())

                save_parts = Path(resolved_save).parts
                output_parts = Path(resolved_output).parts

                # Verifica se saída está dentro do repositório
                if not is_path_outside_repository(output_file):
                    print("Aviso: O diretório de saída deve estar fora do repositório Git.", file=sys.stderr)

                output_file.write_text(report, encoding='utf-8')
                print(f"Relatório salvo em: {output_path}", file=sys.stderr)

            except PermissionError:
                print("Erro: Sem permissão para escrever no diretório de saída.", file=sys.stderr)
                return 1
            except OSError as e:
                print(f"Erro ao salvar relatório: {e}", file=sys.stderr)
                return 1
        else:
            print(report)

        return 0

    except Exception as e:
        print("Erro: Não foi possível processar o arquivo selecionado.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
