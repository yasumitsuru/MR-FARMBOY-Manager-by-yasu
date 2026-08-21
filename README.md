# MR FARMBOY Manager by yasu

Gerenciador desktop independente para localizar saves do MR FARMBOY, consultar
detalhes sanitizados e manter backups locais com operações confirmadas.

## Status

**MVP 0.1.0 utilizável no Windows.**

O MVP inclui:

- descoberta de slots `save_<n>`;
- leitura de progresso do jogador e cultivos em arquivos Godot `.tres`;
- configuração persistente das pastas de saves e do jogo;
- atualização ao configurar a pasta, manual e automática a cada cinco minutos;
- criação, listagem, restauração e exclusão de backups;
- backup preventivo antes de toda restauração;
- mensagens sanitizadas e logging operacional rotativo;
- executável Windows que não exige instalação manual do Python.

Dados financeiros e inventário detalhado continuam indisponíveis enquanto o schema
correspondente do jogo não estiver confirmado.

## Instalação no Windows

1. Baixe e extraia o pacote completo da release. Não separe o `.exe` da pasta
   `_internal`.
2. Execute `MR-FARMBOY-Manager.exe`.
3. Em **Pasta dos saves**, selecione a pasta `game_data` do jogo.
4. Selecione um slot para consultar detalhes ou criar um backup.

O executável é distribuído em formato `onedir` e não requer Python instalado.
O MVP usa um ícone genérico; nenhum ícone ou recurso extraído do jogo é distribuído.

## Localização dos dados

No Windows, a pasta padrão dos saves é:

```text
%APPDATA%\Godot\app_userdata\MR FARMBOY\game_data
```

Backups e logs ficam na pasta local privada da aplicação, normalmente:

```text
%LOCALAPPDATA%\yasu\MR FARMBOY Manager\backups
%LOCALAPPDATA%\yasu\MR FARMBOY Manager\logs
```

Os caminhos configurados são persistidos pelo `QSettings` do Qt.

## Segurança e privacidade

- A inspeção trata saves e instalação do jogo como somente leitura.
- Arquivos externos têm limites de tamanho, parsing e quantidade de avisos.
- Links simbólicos, junctions/reparse points e mudanças concorrentes são rejeitados nas
  operações sensíveis.
- Criar um backup grava somente no diretório privado de backups.
- Restaurar substitui o slot ativo apenas após confirmação e criação de backup
  preventivo.
- Excluir exige confirmação e atua somente sobre um backup íntegro e identificado.
- Logs não armazenam o conteúdo integral dos saves.
- Saves e recursos extraídos do jogo não devem ser enviados ao repositório.

## Desenvolvimento

Pré-requisito: Python 3.12 ou superior.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[dev]"
python -m mr_farmboy_manager
pytest -q
```

Com `uv`, o ambiente travado pode ser reproduzido com:

```powershell
uv sync --extra dev --locked
```

## Build e smoke test Windows

```powershell
.venv\Scripts\python.exe -m tools.build_windows
.venv\Scripts\python.exe -m tools.smoke_windows_build
```

O build é gravado em:

```text
dist\MR-FARMBOY-Manager\MR-FARMBOY-Manager.exe
```

O smoke test inicia o executável com `APPDATA`, `LOCALAPPDATA`, configuração, logs e
backups isolados em um diretório temporário.

## Cobertura do frontend QML

A interface Qt Quick substitui integralmente o frontend Qt Widgets removido. A matriz
abaixo preserva a cobertura dos comportamentos que anteriormente eram exercitados
pela UI legada.

| Comportamento | Cobertura ativa |
| --- | --- |
| Configuração, validação e persistência de pastas | `tests/presentation/test_settings_view_model.py::{test_normalized_slot_is_displayed_and_persisted_as_root,test_invalid_path_cannot_replace_persisted_operational_settings,test_valid_game_path_is_persisted_and_signal_uses_effective_values,test_reload_discards_dirty_draft_and_revalidates_persisted_values}`; `tests/qml/test_settings_diagnostics_pages.py::test_normalized_path_feedback_is_visible` |
| Atualização automática de cinco minutos | `tests/presentation/test_app_controller.py::test_controller_timer_skips_active_mutation` |
| Listagem, seleção e detalhes de saves | `tests/presentation/test_saves_view_model.py::{test_refresh_moves_loading_to_ready_and_preserves_selection,test_details_exposes_optional_metrics_and_zero_growth_total,test_new_selection_signal_never_exposes_previous_loaded_details}`; `tests/qml/test_dashboard_saves_pages.py::test_selected_details_and_narrow_layout_remain_available` |
| Criação e listagem de backups | `tests/presentation/test_backups_view_model.py::{test_create_uses_selected_slot_and_enqueues_one_refresh,test_discovery_error_exposes_only_public_message}`; `tests/qml/test_backups_page.py::test_create_and_restore_controls_reach_their_safe_python_boundaries` |
| Restauração de backup com confirmação | `tests/presentation/test_backups_view_model.py::{test_restore_requires_matching_confirmation,test_restore_uses_confirmation_snapshot_after_selection_changes}`; `tests/qml/test_backups_page.py::test_dialog_uses_immutable_backup_identity_and_cancel_does_not_mutate` |
| Exclusão de backup com confirmação | `tests/presentation/test_backups_view_model.py::{test_delete_runs_confirmed_service,test_delete_uses_confirmation_snapshot_after_selection_changes}`; `tests/qml/test_backups_page.py::test_delete_confirmation_keeps_copied_values_and_uses_danger_variant` |
| Restauração das configurações no início | `tests/presentation/test_app_controller.py::test_initialize_applies_settings_refreshes_pages_and_shutdown_runner`; `tests/presentation/test_settings_view_model.py::test_reload_discards_dirty_draft_and_revalidates_persisted_values` |
| Escolha de diretório e cancelamento | `tests/presentation/test_settings_view_model.py::test_chooser_cancellation_is_neutral_and_injected_choice_is_validated`; `tests/qml/test_settings_diagnostics_pages.py::test_dirty_settings_enable_save_and_cancelled_chooser_is_neutral` |
| Confirmações modais e jornada integrada | `tests/test_qml_e2e.py::test_complete_qml_journey_only_mutates_tmp_path`; `tests/qml/test_backups_page.py::test_rejecting_dialog_cancels_once_and_releases_python_lock` |

## Sobre o jogo

[MR FARMBOY](https://store.steampowered.com/app/2795090/MR_FARMBOY/) é
desenvolvido e publicado por mrdboy.

Este projeto não é oficial nem afiliado aos desenvolvedores ou publicadores do jogo.
MR FARMBOY e seus recursos pertencem aos respectivos proprietários.

## Licença

O projeto ainda não possui uma licença de redistribuição definida. Na ausência de uma
licença explícita, permanecem reservados os direitos aplicáveis ao código.
