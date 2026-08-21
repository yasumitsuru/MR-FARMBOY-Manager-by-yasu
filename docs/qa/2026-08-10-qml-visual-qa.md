# QA visual QML — 10/08/2026

## Fixture e escopo

A verificação usou dados determinísticos das fixtures QML, sem acessar saves reais
nem a instalação do jogo. A janela foi validada em modo desktop com as páginas
Visão do cultivo, Saves, Backups, Configurações e Diagnósticos prontas para uso.

## Matriz de tamanhos

| Página | 1280×720 | 1366×768 | 1600×900 | 1920×1080 |
| --- | --- | --- | --- | --- |
| Visão do cultivo | pronto | pronto | pronto | pronto |
| Saves | pronto | pronto | pronto | pronto |
| Backups | pronto | pronto | pronto | pronto |
| Configurações | pronto | pronto | pronto | pronto |
| Diagnósticos | pronto | pronto | pronto | pronto |

Em cada tamanho foram observadas as geometrias nomeadas, a largura do conteúdo
rolável e a ausência de valores negativos ou não finitos. Não foram usados
snapshots de pixel.

## Estados amostrados

- Estados pronto, erro e entrada inválida foram exercitados com as fixtures.
- O diálogo de exclusão foi aberto em 1280×720; foco por Tab e rolagem foram
  confirmados sem diálogo modal pendente.
- Nenhum save real, diretório de save ou instalação do jogo foi lido ou alterado.

## Defeitos e correções

1. Os cabeçalhos de Dashboard e Saves aceitavam ações filhas sem as tratar como
   propriedade padrão, e o espaço da ação não contribuía para sua geometria.
   `SectionHeader` agora usa a ação padrão, mede seus filhos e expõe pontos
   estáveis para garantir que título e ação não se sobreponham.
2. A confirmação de exclusão tinha aparência de contorno e baixo contraste.
   A variante `danger` agora é coral sólido, com texto escuro e estados hover/
   pressionado definidos centralmente no tema; o contorno de foco permanece.
3. Diagnósticos repetia a mesma falha no conteúdo e no status, além de pintar
   sucesso como erro. O conteúdo vazio é neutro, a falha aparece uma vez no
   status e atualizações com eventos usam a cor de sucesso.
