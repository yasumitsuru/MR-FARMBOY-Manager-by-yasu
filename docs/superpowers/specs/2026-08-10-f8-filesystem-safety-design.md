# F8 — Segurança de filesystem

## Objetivo

Fechar os seis achados confirmados no commit `e48459c` sem ampliar o escopo funcional do gerenciador. Saves e instalação reais continuam estritamente somente leitura; toda escrita e remoção automatizada em testes usa `tmp_path`.

## Invariantes

- Uma entrada externa nunca pode causar leitura ou coleção diagnóstica sem teto.
- Uma identidade de arquivo ou diretório validada deve permanecer a identidade usada na publicação, rollback ou remoção.
- Uma remoção recursiva só pode alcançar o inventário congelado da própria transação.
- Divergência, reparse point, crescimento, swap ou conteúdo inesperado causa falha fechada e mensagem pública sanitizada.
- Restore mantém a semântica transacional: ou publica o backup integralmente, ou preserva/restaura o slot original; resíduos seguros são reportados como cleanup pendente.
- Criação de backup mantém IDs exclusivos e nunca sobrescreve destino existente.

## Arquitetura

Os limites de recursos ficam nas fronteiras de leitura e parsing. As operações destrutivas e de publicação reutilizam primitives ancoradas por handle no Windows e falham fechado quando a plataforma não oferece a mesma garantia. O módulo `backups.py` mantém os DTOs e mensagens atuais; as mudanças internas tornam inventários obrigatórios e evitam voltar do objeto validado para um pathname solto.

## Fluxos e erros

Leituras acima do teto retornam os erros tipados já usados pelo chamador. Avisos TRES preservam os primeiros itens e acrescentam um único marcador de truncamento. Em corridas de filesystem, nenhum substituto é movido ou removido; a operação retorna falha sanitizada ou `cleanup_pending`, conforme a árvore validada ainda possa ser preservada com segurança.

## Prova

Cada achado recebe primeiro um teste de regressão que falha no código vulnerável. Os testes exercitam o boundary real com árvores em `tmp_path`, incluindo controles legítimos. Após cada correção: teste focado, suíte do módulo, revisão independente, suíte completa, `git diff --check`, commit e push sincronizado.
