# F8 Filesystem Safety Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar os seis achados de segurança F8 mantendo compatibilidade e falha fechada.

**Architecture:** Limites são impostos antes e durante leitura/parsing. Publicação e remoção deixam de resolver novamente pathnames após validação e passam a usar identidade ancorada e inventário exato.

**Tech Stack:** Python 3.13, pytest, pathlib/os, ctypes Win32, PySide6 apenas nos consumidores existentes.

## Global Constraints

- Saves e instalação reais são somente leitura.
- Testes mutantes usam exclusivamente `tmp_path`.
- Nenhum teste abre modal ou exige interação.
- `locais.txt` não pode ser tocado, adicionado ou removido.
- Cada tarefa termina em teste focado, revisão, suíte completa, commit, push e sincronização.

---

### Task 1: Limitar avisos TRES

**Files:**
- Modify: `src/mr_farmboy_manager/godot_tres.py`
- Test: `tests/test_godot_tres.py`

**Interfaces:**
- Consumes: `parse_godot_tres_structure(text)` e `parse_godot_tres_document(text)`.
- Produces: as mesmas assinaturas, preservando no máximo o teto de avisos mais um marcador de truncamento.

- [ ] Escrever testes com mais linhas inválidas que o teto e um controle abaixo do teto.
- [ ] Executar os testes e confirmar excesso de avisos no código atual.
- [ ] Implementar helper interno que coleta os primeiros avisos e conta excedentes.
- [ ] Executar testes focados e de consumidores.
- [ ] Revisar, executar suíte completa e commit `fix(parser): limitar avisos de arquivos tres`.

### Task 2: Limitar leituras de saves

**Files:**
- Modify: `src/mr_farmboy_manager/save_snapshot.py`
- Modify: `src/mr_farmboy_manager/save_discovery.py`
- Modify: `src/mr_farmboy_manager/save_loader.py`
- Modify: `src/mr_farmboy_manager/save_inspector.py`
- Test: `tests/test_save_snapshot.py`
- Test: `tests/test_save_discovery.py`
- Test: `tests/test_save_loader.py`
- Test: `tests/test_save_inspector.py`

**Interfaces:**
- Consumes: caminhos locais e o teto público de bytes.
- Produces: conteúdo/snapshot somente se tamanho e crescimento permanecerem dentro do teto; APIs públicas atuais permanecem compatíveis.

- [ ] Escrever testes de arquivo acima do teto e crescimento concorrente, mais controle no limite.
- [ ] Confirmar que ao menos uma rota vulnerável lê antes de recusar.
- [ ] Implementar leitura/cópia incremental limitada e propagar erro tipado/sanitizado.
- [ ] Executar testes focados das quatro rotas.
- [ ] Revisar, executar suíte completa e commit `fix(saves): limitar leituras de arquivos externos`.

### Task 3: Congelar inventários de cleanup do restore

**Files:**
- Modify: `src/mr_farmboy_manager/backups.py`
- Test: `tests/test_backup_restore.py`

**Interfaces:**
- Consumes: inventários de staging e rollback já produzidos pela transação.
- Produces: cleanup somente quando o inventário atual é idêntico; divergência retorna cleanup pendente sem remover a árvore.

- [ ] Escrever regressões para arquivo extra no rollback e no staging.
- [ ] Confirmar que o arquivo extra é removido no código atual.
- [ ] Tornar `expected_entries` obrigatório nos dois chamadores e manter o inventário atualizado após publicação.
- [ ] Executar testes de restore e delete relacionados.
- [ ] Revisar, executar suíte completa e commit `fix(restore): exigir inventario no cleanup`.

### Task 4: Ancorar publicação e rollback do restore

**Files:**
- Modify: `src/mr_farmboy_manager/backups.py`
- Test: `tests/test_backup_restore.py`

**Interfaces:**
- Consumes: raiz, slot ativo, staging e rollback validados.
- Produces: commit/rollback por identidade ancorada no Windows; fallback não garantido falha fechado.

- [ ] Escrever regressões de swap do slot, staging e raiz imediatamente antes do commit.
- [ ] Confirmar que o pathname substituto é movido no código atual.
- [ ] Extrair primitive de rename relativo a handle e usá-la em commit e rollback.
- [ ] Provar que controles legítimos e rollback após falha continuam íntegros.
- [ ] Revisar, executar suíte completa e commit `fix(restore): ancorar publicacao por identidade`.

### Task 5: Ancorar publicação do backup

**Files:**
- Modify: `src/mr_farmboy_manager/backups.py`
- Test: `tests/test_backups.py`
- Test: `tests/test_backup_create.py`

**Interfaces:**
- Consumes: raiz validada, diretório reservado vazio, payload e manifesto em staging.
- Produces: nomes publicados relativamente ao handle do destino reservado, sem sobrescrita.

- [ ] Escrever regressões de swap do destino e da raiz após reserva.
- [ ] Confirmar publicação no substituto com o código atual.
- [ ] Publicar payload/manifeste por handles ancorados e verificar inventário vazio.
- [ ] Executar testes de criação e descoberta.
- [ ] Revisar, executar suíte completa e commit `fix(backups): ancorar publicacao no destino reservado`.

### Task 6: Remover cleanup de backup baseado em pathname

**Files:**
- Modify: `src/mr_farmboy_manager/backups.py`
- Test: `tests/test_backup_create.py`
- Test: `tests/test_backup_delete.py`

**Interfaces:**
- Consumes: estado e inventário conhecidos de staging/destino parcial.
- Produces: quarentena/remoção da identidade exata ou falha fechada com resíduo preservado.

- [ ] Escrever regressões de swap e entrada extra antes dos dois cleanups de erro.
- [ ] Confirmar que o substituto é removido no código atual.
- [ ] Reutilizar a primitive segura de quarentena/remoção e eliminar `rmtree` desacoplado.
- [ ] Executar testes de criação, delete e restore.
- [ ] Revisar, executar suíte completa e commit `fix(backups): tornar cleanup resistente a swaps`.

### Task 7: Fechamento F8

**Files:**
- Modify: `README.md` apenas se o comportamento público de limite/cleanup precisar ser documentado.

**Interfaces:**
- Consumes: seis correções aprovadas.
- Produces: suíte integral verde e revalidação estática dos seis caminhos fonte-destino.

- [ ] Executar todos os testes F8 e a suíte completa.
- [ ] Executar `git diff --check`, auditar status e confirmar ausência de acesso mutante a paths reais.
- [ ] Repassar cada achado no código atual e registrar o fechamento.
- [ ] Fazer o commit documental apenas se houver mudança pública e sincronizar `main` com `origin/main`.
