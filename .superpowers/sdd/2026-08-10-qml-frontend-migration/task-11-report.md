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
