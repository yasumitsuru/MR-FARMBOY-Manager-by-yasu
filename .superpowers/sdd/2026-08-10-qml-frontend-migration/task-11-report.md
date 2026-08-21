# Task 11 — integração QML e entrypoints

## RED/GREEN

- RED: os novos contratos apontaram o console script para o runner Widgets legado; a
  assertiva de estado QML também confirmou que o componente raiz expõe a mensagem,
  não um `text` próprio.
- GREEN: bindings QML (ação para Python e `notify` para UI), E2E temporário,
  logging, E2E legado e a suíte QML passam com `QT_QPA_PLATFORM=offscreen`.

## Arquitetura

- `qml_application.run()` agora preserva a configuração portátil de
  `MR_FARMBOY_RUNTIME_ROOT` (settings INI, `backups/` e `logs/`) do bootstrap
  legado e injeta esses limites no `AppController`.
- O engine é criado e validado antes de `controller.initialize()`; `shutdown()`
  do runner é garantido no `finally`, inclusive em erro de carga ou saída.
- Os entrypoints console, `python -m` e Windows chamam
  `mr_farmboy_manager.qml_application:run`; `application.py` foi preservado.

## Segurança e E2E

- O novo E2E cria `game_data/save_1`, runtime, backups e logs exclusivamente em
  `tmp_path`; ele verifica inspeção, backup, alteração controlada, restauração,
  deleção, refresh e ausência de caminho temporário no log.
- Nenhum diálogo modal ou loop Qt real é iniciado nos testes do bootstrap.
- Os eventos novos (`qml.engine`, `qml.load`, `qml.controller` e shutdown) não
  registram caminhos ou conteúdo de save.

## Verificação e sincronização

- RED direcionado: falhou como esperado nos entrypoints Widgets antes do patch.
- GREEN: suíte QML, E2E novo/legado, logging, `compileall` e `git diff --check`.
- Commit e sincronização `HEAD == origin/main` são confirmados no recibo final da
  tarefa, após o único commit exigido.

## Concerns

- O pytest emite o warning preexistente de cache (`.pytest_cache`); não afeta os
  772 testes aprovados.

## Fix round 1

- RED confirmou que o bootstrap QML não expunha nem usava o root de backup
  legado; GREEN usa `default_backup_root()` fora do runtime portátil.
- O E2E agora sobe engine QML e `AppController` reais com runner manual,
  settings/backups/logs injetados em `tmp_path`, confirma restore/delete pelo
  diálogo QML e verifica shutdown.
- O isolamento captura recursivamente a área externa à árvore da execução
  (tipo, metadados e hash), além de validar em wrappers que cada fronteira
  mutável recebe somente caminhos dentro de `tmp_path`.

## Fix round 2

- A jornada usa cliques reais em `saveSlotsList`, `backupsList` e
  `refreshSavesButton`; não chama slots equivalentes diretamente.
- A recomputação real do dashboard permaneceu ativa; o controller agora mantém
  o DTO de detalhes carregado para projetar o dashboard sem confundir o
  ViewModel QML com o DTO de domínio.

## Fix round 3

- Finding: `SavesViewModel.selectSlot` emitia `selectedSummaryChanged` antes de
  iniciar o novo request de detalhes. Um subscriber síncrono podia então ver
  `detailsState="ready"` e `_loaded_details` do slot anterior durante a troca.
- Teste adicionado: `tests/presentation/test_saves_view_model.py::test_new_selection_signal_never_exposes_previous_loaded_details`.
- RED executado: `PYTHONPATH=src; QT_QPA_PLATFORM=offscreen; pytest -q --basetemp '.pytest-round13' tests/presentation/test_saves_view_model.py::test_new_selection_signal_never_exposes_previous_loaded_details`.
  Falhou como esperado: observou `('ready', SaveSlotDetails(...))` em vez de
  `('loading', None)`.
- GREEN isolado: o mesmo comando retornou `1 passed` após inverter a ordem.
- A tentativa focada maior foi `PYTHONPATH=src; QT_QPA_PLATFORM=offscreen; pytest -q --basetemp '.pytest-round13' tests/presentation/test_saves_view_model.py tests/presentation/test_app_controller.py tests/test_qml_e2e.py`;
  o pytest encontrou `PermissionError` ao limpar `.pytest-round13`.
- `python -m compileall -q src tests` e `git diff --check` foram executados com
  sucesso antes do commit `ff81f00`. Não houve full suite executada pelo
  implementador nesta rodada; o gate fica para o controlador com basetemp seguro.

## Fix round 4

- Causa confirmada: `_request_details()` mudava `detailsState` para `loading` e
  limpava o modelo visível, mas preservava `_loaded_details` do slot anterior até
  o worker terminar. A correção mínima invalida esse DTO antes do submit e antes
  do `selectedSummaryChanged` síncrono de `selectSlot`.
- RED, com `PYTHONPATH=src` e `QT_QPA_PLATFORM=offscreen`:
  `python -m pytest -q tests/presentation/test_saves_view_model.py::test_new_selection_signal_never_exposes_previous_loaded_details` retornou
  `1 failed`, observando `('loading', SaveSlotDetails(...))` em vez de
  `('loading', None)`.
- GREEN isolado: o mesmo comando retornou `1 passed`. No mutation check, remover
  somente a invalidação fez o teste retornar `1 failed`; após restaurá-la, o
  comando retornou novamente `1 passed`.
- Direcionado exigido:
  `python -m pytest -q tests/presentation/test_saves_view_model.py tests/presentation/test_app_controller.py tests/test_qml_e2e.py`
  retornou `16 passed`.
- Presentation/QML relacionado:
  `python -m pytest -q tests/presentation tests/qml tests/test_qml_e2e.py`
  retornou `96 passed`.
- Suíte completa offscreen: `python -m pytest -q` retornou
  `774 passed, 9 skipped` em `12.19s` (783 itens coletados).
- `python -m compileall -q src tests` e `git diff --check` concluíram com código
  zero e sem saída. Todos os testes usaram o Temp padrão seguro do pytest fora
  do sandbox; nenhum diretório `.pytest-round*` foi criado ou reutilizado.
