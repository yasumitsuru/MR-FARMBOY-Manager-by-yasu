# Instrucoes operacionais

## Workflow Git obrigatorio

Antes de qualquer tarefa de desenvolvimento, execute `git status`,
`git fetch origin` e `git status -sb`. Confirme se a branch esta ahead,
behind, diverged ou sincronizada e, quando seguro, atualize-a antes de editar.

Depois de uma tarefa com alteracoes:

1. execute os testes relevantes e a suite completa quando aplicavel;
2. revise `git diff` e `git status`;
3. crie um commit claro e faca push para a branch remota correspondente;
4. execute `git fetch origin` e confirme que local e remoto apontam para o
   mesmo commit, normalmente com `## main...origin/main` sem ahead ou behind.

Preserve alteracoes do usuario. Nao use `git reset --hard`, checkout destrutivo
ou force push como procedimento normal.

## Regras de testes

- Testes automatizados nao podem depender de interacao humana nem deixar
  `QFileDialog` ou outra janela modal aberta.
- Centralize caminhos especificos da maquina em fixtures ou configuracao de
  testes; nao duplique strings absolutas.
- Trate saves reais e a instalacao real do jogo como somente leitura.
- Use `tmp_path` para qualquer arquivo que possa ser alterado, movido,
  renomeado ou removido.
- Nenhum teste deve modificar a instalacao real do jogo.
