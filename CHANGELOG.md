# Changelog

Todas as alterações relevantes deste projeto serão registradas neste arquivo.

## [0.1.0] - 2026-08-10

Primeira release MVP utilizável do MR FARMBOY Manager.

### Adicionado

- descoberta e seleção de slots de save;
- leitura sanitizada de progresso do jogador e cultivos em arquivos Godot `.tres`;
- configuração persistente das pastas de saves e do jogo;
- criação, listagem, restauração e exclusão confirmada de backups;
- atualização manual, após mudança de configuração e automática a cada cinco minutos;
- logging operacional rotativo sem conteúdo integral dos saves;
- build Windows `onedir` com PyInstaller, executável sem Python instalado;
- testes integrados da jornada completa e da primeira execução isolada.

### Segurança

- limites rígidos de leitura e parsing para arquivos externos;
- leitura vinculada a descritores e validação contra links/reparse points;
- publicação, restauração e limpeza de backups protegidas contra trocas de caminho;
- backup preventivo obrigatório antes da restauração;
- mensagens de erro públicas sanitizadas.

### Limitações conhecidas

- dados financeiros e inventário detalhado permanecem indisponíveis enquanto o schema
  correspondente do jogo não estiver confirmado;
- o executável usa o ícone genérico do empacotador; nenhum recurso extraído do jogo é
  distribuído.
