# MR FARMBOY Manager — design da migração para QML / Qt Quick

Data: 2026-08-10
Status: aprovado autonomamente conforme autorização explícita do pedido

## 1. Resumo

O frontend será migrado de Qt Widgets para QML/Qt Quick por uma estratégia
incremental do tipo *strangler*: o backend Python e seus serviços permanecem a
fonte única das regras de negócio, uma bridge `QObject` testável é introduzida
entre esses serviços e a apresentação, e a interface QML evolui em paralelo à
UI Widgets até atingir paridade funcional. O entry point só muda para QML após
os testes da bridge, integração QML e jornada E2E estarem verdes. A UI Widgets
só é removida depois de build e smoke test do executável Windows.

A interface terá identidade de dashboard administrativo agrícola: superfícies
escuras em tons de floresta, acento verde vivo controlado, realces âmbar para
atenção, alta densidade informativa e hierarquia clara. O produto usará somente
dados reais encontrados pelos serviços existentes.

## 2. Estado atual relevante

- `src/mr_farmboy_manager/__main__.py` delega para `application.run()`.
- `src/mr_farmboy_manager/application.py` concentra a criação da janela Widgets,
  estado de UI, callbacks, timer, dialogs e ligação com os serviços.
- Descoberta, parsing, inspeção, configuração, backups, restore, delete e logging
  já estão separados em módulos Python e têm cobertura automatizada ampla.
- A suíte baseline possui 683 testes coletados: 674 passaram e 9 foram pulados.
- Não existem arquivos QML, módulo de recursos Qt ou configuração de packaging
  para recursos QML.
- O caminho de um slot individual, como `game_data/save_1`, é hoje aceito como
  diretório válido, mas não é normalizado para a raiz `game_data`; a descoberta
  retorna vazia porque procura slots dentro de `save_1`.
- `tools/build_windows.py` usa PyInstaller em modo `--windowed --onedir`, e
  `tools/smoke_windows_build.py` valida o artefato.

## 3. Objetivos

1. Substituir a UI Widgets por uma UI QML moderna, responsiva e acessível.
2. Preservar os serviços Python existentes e as garantias de segurança do
   filesystem, especialmente nas operações de backup, restore e delete.
3. Criar contratos Python/QML explícitos, pequenos e testáveis.
4. Entregar Dashboard, Saves, Backups, Configurações e Diagnóstico com estados de
   loading, vazio, pronto, erro e desabilitado.
5. Corrigir, com teste de regressão, o caso `game_data/save_1` sem ocultar do
   usuário a normalização realizada.
6. Preservar a jornada funcional existente e trocar o entry point apenas quando
   houver paridade comprovada.
7. Empacotar QML, recursos e plugins Qt no build Windows e validar o executável
   fora da árvore fonte.

## 4. Não objetivos

- Reescrever parser, descoberta, configuração ou operações de backup em QML ou
  JavaScript.
- Alterar o formato dos saves, manifests ou backups existentes.
- Introduzir banco de dados, telemetria, serviço remoto ou dependência paga.
- Criar métricas financeiras que o parser não fornece.
- Implementar light mode nesta migração; os tokens serão preparados para ele.
- Criar terminal, editor de saves ou visualizações pixel-perfect.
- Mudar versão ou criar tag antes de todos os gates finais.

## 5. Alternativas avaliadas

### 5.1 Reescrita direta sobre os serviços

Criaria `Main.qml` e ligaria seus eventos diretamente a um grande controller.
É a opção com menos arquivos iniciais, mas transfere para uma única mudança os
riscos de estado, dialogs, temporização, paridade e packaging. Foi rejeitada por
exigir a troca prematura do entry point e por dificultar testes por unidade.

### 5.2 QML embutido na janela Widgets

Usaria `QQuickWidget` para migrar regiões isoladas. Reduz o salto visual por
etapa, mas mantém duas hierarquias de UI, mistura layout Widgets com Qt Quick,
complica foco, estilos, renderização e packaging e não representa a arquitetura
final. Foi rejeitada.

### 5.3 Bridge Python + aplicação QML paralela

Introduz uma camada de apresentação Python independente dos Widgets, monta uma
aplicação QML paralela, migra páginas em etapas e troca o entry point somente
após paridade. Exige mais disciplina e contratos explícitos, mas oferece melhor
isolamento, rollback, TDD e segurança. Esta é a alternativa escolhida.

## 6. Arquitetura escolhida

```text
QML / Qt Quick Controls 2
        │ properties, signals, slots e roles
        ▼
AppController + ViewModels + QAbstractListModels
        │ protocolos Python injetáveis
        ▼
Application Services existentes
        │
        ▼
Config / Saves / Parser / Backups / Logging
        │
        ▼
Filesystem
```

### 6.1 Estrutura alvo

```text
src/mr_farmboy_manager/
├── __main__.py
├── qml_application.py
├── presentation/
│   ├── app_controller.py
│   ├── operation_runner.py
│   ├── dashboard_view_model.py
│   ├── saves_view_model.py
│   ├── backups_view_model.py
│   ├── settings_view_model.py
│   ├── diagnostics_view_model.py
│   ├── save_slots_model.py
│   ├── backups_model.py
│   └── growth_states_model.py
├── qml/
│   ├── Main.qml
│   ├── qmldir
│   ├── Theme.qml
│   ├── components/
│   └── pages/
├── resources/
│   └── qml.qrc
└── application.py             # legado até o gate de remoção
```

Arquivos poderão ser agrupados quando a implementação demonstrar que duas
classes são pequenas e inseparáveis, mas as responsabilidades e interfaces
abaixo devem permanecer distintas.

### 6.2 Bootstrap QML

`qml_application.py` será responsável por:

1. criar ou reutilizar `QGuiApplication`;
2. configurar nome, organização, versão e logging como hoje;
3. resolver settings, diretório de backups, logs e root portátil;
4. construir serviços e ViewModels por injeção de dependência;
5. registrar ou injetar um único `AppController` como `appController`;
6. criar `QQmlApplicationEngine` e carregar `qrc:/qml/Main.qml`;
7. registrar falha de carregamento sem expor caminhos ou exceções sensíveis;
8. encerrar com código diferente de zero quando nenhum root object for criado;
9. fechar o executor de operações de modo ordenado ao sair.

Enquanto a migração estiver incompleta, esse bootstrap será chamável diretamente
por testes e por um ponto de preview, sem alterar `python -m mr_farmboy_manager`.

### 6.3 AppController

`AppController(QObject)` será o composition root exposto ao QML. Ele não conterá
regras de filesystem. Suas responsabilidades serão:

- expor os ViewModels de página como propriedades constantes;
- coordenar slot selecionado entre Saves, Dashboard e Backups;
- iniciar o carregamento inicial após o engine estar pronto;
- manter o timer de atualização automática de cinco minutos;
- impedir atualização automática durante uma mutação de backup;
- propagar estado global de configuração e mensagens transitórias;
- coordenar desligamento e descarte do executor.

Navegação, sidebar aberta/fechada e página ativa são estado puramente visual e
ficam no QML. O controller não conhece componentes nem índices de navegação.

### 6.4 ViewModels e models

Cada ViewModel é um `QObject` com propriedades imutáveis para o QML, signals de
mudança e slots de intenção. Listas usam `QAbstractListModel`; listas de dicionários
ou objetos Python não serão expostas como contrato público.

#### SavesViewModel

Propriedades principais:

- `state`: `idle | loading | empty | ready | error`;
- `slotsModel`;
- `selectedSlotId`;
- `selectedDetails` como `QObject` de leitura;
- `detailsState`;
- `statusMessage` e `errorMessage` sanitizadas;
- `canRefresh` e `canCreateBackup`.

Slots principais:

- `refresh()`;
- `selectSlot(slotId)`;
- `clearSelection()`.

`SaveSlotsModel` terá roles estáveis: `slotId`, `displayName`, `slotNumber`,
`recordCount`, `pathLabel` e `selected`. `pathLabel` é apresentação sanitizada;
o caminho operacional permanece somente no Python.

Os detalhes expõem os valores reais de registros, plantados, regados,
fertilizados, maduros, colhíveis e mortos. Estados de crescimento usam um model
com roles `label`, `value`, `total` e `ratio`, onde `ratio` é derivado somente de
valores reais e vale zero quando o total é zero.

#### BackupsViewModel

Propriedades principais:

- `state`, `backupsModel`, `selectedBackupId`;
- `mutationState`: `idle | creating | restoring | deleting`;
- `canCreate`, `canRestore`, `canDelete`;
- `statusMessage`, `errorMessage` e identidade da confirmação pendente.

Slots principais:

- `refresh()` e `selectBackup(backupId)`;
- `createForSelectedSlot()`;
- `restoreSelected()`;
- `deleteSelected()`.

O QML apresenta a confirmação e só chama restore/delete após confirmação. O
ViewModel revalida a identidade selecionada e os pré-requisitos imediatamente
antes de delegar ao serviço; a confirmação visual nunca substitui a validação
do domínio.

`BackupsModel` terá roles `backupId`, `slotId`, `slotLabel`, `createdAtLabel`,
`sizeLabel`, `integrityLabel` e `selected`. O model não expõe um caminho mutável.

#### SettingsViewModel

Propriedades:

- `saveRoot`, `gameInstallRoot` e `backupRootLabel`;
- estados independentes `valid | invalid | unset`;
- mensagens sanitizadas e `hasUnsavedChanges`.

Slots:

- editar e validar os dois caminhos configuráveis;
- abrir os seletores nativos por dependências injetáveis;
- salvar configuração;
- restaurar os valores persistidos.

O diretório de backup continua derivado da configuração/runtime atual e será
mostrado como somente leitura, salvo se o backend já suportar configuração
explícita sem reduzir garantias de segurança.

#### DashboardViewModel

É somente leitura e deriva seus valores do estado já carregado:

- quantidade de slots;
- slot selecionado;
- quantidade de backups do slot e total;
- data do último backup, quando existir;
- última atualização bem-sucedida;
- estado de configuração;
- métricas agrícolas do slot selecionado.

Nenhum número padrão será usado para simular dados ausentes. A ausência será
mostrada como `—`, `Não disponível` ou um empty state.

#### DiagnosticsViewModel

Expõe caminho legível do arquivo/diretório de logs, disponibilidade dos logs,
últimos eventos sanitizados e texto de diagnóstico copiável. Oferece slots para
atualizar eventos, abrir a pasta via Python e copiar o diagnóstico pelo clipboard
da aplicação. Não registra cliques ou hovers.

### 6.5 Execução assíncrona e ordenação

Leitura e parsing não devem bloquear a thread de renderização. Um
`OperationRunner` Python, substituível por fake nos testes, executará chamadas de
serviço fora da thread principal e entregará resultados ao ViewModel por queued
signals. A implementação terá uma única fila de trabalho para impedir concorrência
entre refresh, create, restore e delete sobre os mesmos dados.

Cada solicitação recebe um identificador monotônico. Resultados de refresh ou
detalhes que já não correspondam à seleção/configuração atual são descartados.
Durante restore/delete, refresh manual e automático ficam desabilitados. O runner
nunca cancela uma mutação já iniciada e sempre volta o estado visual a `idle`, com
resultado explícito, inclusive diante de exceção.

Testes unitários usam um runner determinístico que só conclui quando instruído.
Isso permite provar loading, ordenação, descarte de resposta obsoleta e erro sem
temporização real.

### 6.6 Fluxo de dados

```text
evento QML
  → slot de intenção no ViewModel
  → validação de estado/pré-condição
  → OperationRunner
  → serviço Python existente
  → resultado imutável/sanitizado
  → atualização de model/properties na thread da UI
  → signals notify
  → bindings QML redesenham o estado
```

QML não recebe objetos `Path`, exceções, callables nem DTOs internos do domínio.
Conversão para roles e propriedades acontece na camada de apresentação.

## 7. Tratamento de erros

- Serviços continuam responsáveis por validação operacional e mensagens seguras.
- ViewModels convertem falhas conhecidas em estado `error` ou status de operação.
- Exceções inesperadas são logadas com contexto técnico, mas o QML recebe mensagem
  genérica sanitizada.
- Erros de página são apresentados dentro da região afetada, com ação de tentar
  novamente quando segura; mensagens globais curtas podem usar uma snackbar.
- Erro de restore/delete nunca remove seleção automaticamente se o registro ainda
  existir.
- Falha de carregamento QML encerra o bootstrap com erro e registra um único evento
  útil.

## 8. Estrutura QML

```text
qml/
├── Main.qml
├── Theme.qml
├── components/
│   ├── AppShell.qml
│   ├── AppCard.qml
│   ├── MetricCard.qml
│   ├── StatusBadge.qml
│   ├── SidebarItem.qml
│   ├── SectionHeader.qml
│   ├── AppButton.qml
│   ├── EmptyState.qml
│   ├── InlineMessage.qml
│   ├── InfoRow.qml
│   └── ConfirmActionDialog.qml
└── pages/
    ├── DashboardPage.qml
    ├── SavesPage.qml
    ├── BackupsPage.qml
    ├── SettingsPage.qml
    └── DiagnosticsPage.qml
```

`AppButton` será um componente parametrizado por variante (`primary`,
`secondary`, `danger`) para não duplicar três implementações. Outros componentes
só serão extraídos quando tiverem uso real em mais de uma página ou quando
isolarem comportamento complexo.

## 9. Design system

`Theme.qml` será singleton e centralizará todos os tokens. Valores iniciais:

### 9.1 Cores dark-first

| Token | Valor | Uso |
|---|---:|---|
| `background` | `#0B1410` | fundo da aplicação |
| `sidebar` | `#0F1C16` | navegação |
| `surface` | `#14231C` | cards e painéis |
| `surfaceRaised` | `#1A2D24` | hover e painéis elevados |
| `surfaceMuted` | `#20362B` | campos e separadores suaves |
| `accent` | `#86C96F` | ação principal e seleção |
| `accentStrong` | `#63AD56` | pressed e foco forte |
| `success` | `#59C58B` | válido e sucesso |
| `warning` | `#E5B95C` | atenção e maturação |
| `error` | `#ED776D` | falha e ação destrutiva |
| `textPrimary` | `#F2F6F3` | texto principal |
| `textSecondary` | `#A9BBB0` | metadados |
| `textMuted` | `#74877C` | informação terciária |
| `border` | `#294337` | contorno discreto |

Tokens equivalentes de light mode serão agrupados na mesma API de tema, mas não
serão selecionáveis nesta entrega.

### 9.2 Espaçamento, forma e tipografia

- escala de espaço: 4, 8, 12, 16, 20, 24, 32 e 40 px;
- raios: 8 px para controles, 12 px para cards e 16 px para painéis principais;
- bordas de 1 px apenas onde separam informação ou comunicam estado;
- fonte principal: `Segoe UI` no Windows com fallback para a fonte do sistema;
- tamanhos: 12 para metadados, 14 para corpo, 16 para títulos de card, 22 para
  títulos de página e 28 para métricas principais;
- pesos 400, 600 e 700; caixa alta restrita a labels curtos e badges;
- altura mínima de 36 px para controles e 40 px para ações principais.

## 10. Shell e navegação

`Main.qml` cria uma `ApplicationWindow` mínima de 960 × 640 e inicial de
1366 × 768. `AppShell` contém:

- sidebar com marca tipográfica MR FARMBOY, cinco destinos e status compacto;
- topbar com título/contexto da página, última atualização e ação relevante;
- área de conteúdo em `StackLayout`, preservando estado de cada página;
- snackbar para feedback transitório não crítico.

Breakpoints:

- a partir de 1200 px: sidebar de 232 px com ícone e texto;
- de 900 a 1199 px: rail de 80 px com ícone, tooltip e seleção clara;
- abaixo de 900 px: sidebar em drawer sobreposto, fechada após navegação;
- grids de métricas usam 4, 2 ou 1 coluna conforme largura disponível;
- páginas usam `ScrollView` quando a altura for insuficiente, sem scrolls
  aninhados desnecessários.

Os layouts estruturais usarão `QtQuick.Layouts`, anchors e tamanhos implícitos.
Coordenadas absolutas serão limitadas a detalhes decorativos internos.

## 11. Páginas

### 11.1 Dashboard

Topo com estado da configuração e última atualização. A primeira faixa contém
cards reais de slots encontrados, backups, último backup e slot ativo. Quando há
slot selecionado, uma segunda faixa mostra as métricas agrícolas e um painel de
distribuição de crescimento com barras proporcionais. Sem seleção, exibe uma
ação clara para abrir Saves; sem configuração, direciona para Configurações.

### 11.2 Saves

Em telas largas, usa master/detail: lista de slots à esquerda e detalhes à direita.
Em telas estreitas, lista e detalhes se empilham. A lista mostra nome, número e
contagem real, com seleção, hover e foco distintos. O detalhe é organizado em:

1. Resumo — registros, plantados e regados;
2. Produção — fertilizados, maduros, colhíveis e mortos;
3. Crescimento — barras e valores por estado;
4. contexto do slot e ação de criar backup.

Loading usa skeletons discretos; vazio e erro ocupam o painel, não o rodapé.

### 11.3 Backups

Lista/tabela responsiva com slot, data, tamanho, integridade e seleção. Em telas
menores cada registro vira card. A barra de ações oferece criar, restaurar e
excluir; restore e delete exigem diálogo contendo slot, backup e consequência.
Delete usa variante vermelha. Durante mutação, a identidade do alvo permanece
visível e controles conflitantes ficam desabilitados.

### 11.4 Configurações

Dois cards editáveis para raiz dos saves e instalação do jogo, e um card somente
leitura para backups. Cada campo possui badge `Válido`, `Inválido` ou `Não
configurado`, explicação curta e seletor nativo. Salvar só habilita com alteração;
um caminho inválido não substitui silenciosamente o último caminho operacional.

Quando um slot individual for normalizado, a UI mostra mensagem informativa com
a raiz adotada antes de persistir o valor normalizado.

### 11.5 Diagnóstico

Mostra localização do log, estado da configuração e os eventos recentes já
sanitizados. Ações: atualizar, copiar diagnóstico e abrir pasta de logs. O painel
é uma ferramenta de suporte, não um terminal; eventos têm horário, nível e resumo
com quebra de linha e seleção de texto quando útil.

## 12. Normalização da raiz dos saves

A correção será feita antes de a nova tela de configurações depender do contrato.
Uma função pura retornará o caminho efetivo e metadados de normalização.

Regras:

1. Um diretório que contém filhos reconhecíveis `save_<n>` é tratado como raiz.
2. Se o caminho informado tem basename `save_<n>` e corresponde a um slot
   reconhecível, seu pai é avaliado como raiz.
3. A normalização para o pai só ocorre quando o pai passa a descoberta estrutural
   de raiz e contém o próprio slot informado.
4. Diretório apenas existente, mas sem estrutura reconhecível, continua inválido
   para carga de saves; não sobe diretórios arbitrariamente.
5. O resultado diferencia `valid`, `normalized` e `invalid` e inclui mensagem
   segura para a UI.
6. Quando normalizado, settings persiste a raiz efetiva, nunca o slot individual.

O teste de regressão usa `tmp_path/game_data/save_1`; nenhum save real é alterado.

## 13. Dialogs, confirmações e integração com desktop

Seletores de diretório permanecem no Python atrás de callables injetáveis. Isso
mantém dialogs nativos e permite que testes substituam qualquer `QFileDialog`.
Confirmações de restore/delete são QML porque fazem parte do fluxo visual, mas a
ação Python exige um segundo slot explícito e revalida o alvo. Abrir pasta de logs
usa `QDesktopServices`; copiar diagnóstico usa o clipboard da aplicação.

Nenhum teste automatizado abre janela modal real.

## 14. Acessibilidade e interação

- Contraste mínimo será verificado nos tokens e estados.
- Todo botão tem label acessível, tooltip quando só houver ícone e área clicável
  mínima de 36 × 36 px.
- Ordem de tab segue sidebar → topbar → conteúdo → ações da página.
- Foco por teclado usa contorno de `accent`; hover não é o único indicador.
- Disabled reduz contraste, remove ação e preserva legibilidade.
- Badges combinam cor, texto e quando necessário ícone; não dependem só de cor.
- Animações de 120–180 ms serão usadas apenas em hover, seleção, drawer e troca
  de estado. `Behavior` não anima métricas na carga inicial.

## 15. Estratégia incremental

1. Corrigir e testar a normalização da raiz.
2. Criar contratos de apresentação, runner e models sem QML.
3. Adicionar recursos, tema, componentes e shell QML carregável.
4. Migrar Dashboard e Saves.
5. Migrar Backups e suas confirmações.
6. Migrar Configurações e Diagnóstico.
7. Completar integração bidirecional e jornada E2E QML.
8. Trocar o entry point para QML.
9. Atualizar PyInstaller, construir e executar smoke do artefato.
10. Fazer inspeção visual nos quatro tamanhos alvo e polir.
11. Remover Widgets e testes exclusivamente estruturais da UI antiga, preservando
    todos os contratos comportamentais válidos.
12. Executar revisão final, gates e somente então decidir a nova versão.

Cada etapa lógica produz teste RED, implementação mínima, GREEN, revisão, suíte
completa, commit próprio, push e confirmação de sincronização.

## 16. Estratégia de testes

### 16.1 Unidade da bridge

- Properties notificam apenas quando o valor realmente muda.
- Slots rejeitam ações inválidas e não chamam serviços.
- Models expõem roles, ordem, seleção e reset corretos.
- Refresh preserva seleção existente e remove seleção desaparecida.
- Resposta obsoleta não sobrescreve configuração/seleção nova.
- Configuração válida, inválida, ausente e normalizada tem estado explícito.
- Create, restore e delete cobrem sucesso, recusa, falha e exceção sanitizada.
- Timer chama refresh a cada 300.000 ms e não duplica carregamentos.

### 16.2 Integração QML

Com `QT_QPA_PLATFORM=offscreen` e filesystem temporário:

- `QQmlApplicationEngine` cria o root object de `Main.qml`;
- cada página crítica é instanciada;
- bindings essenciais refletem alterações Python → QML;
- ações essenciais chegam QML → Python;
- loading, empty, ready, error, disabled e selected são alcançáveis;
- sidebar e páginas carregam nas larguras 960, 1280, 1366, 1600 e 1920;
- nenhum teste abre `QFileDialog` ou `QMessageBox` real.

Testes QML usarão `objectName` apenas para pontos estáveis de integração, não para
replicar toda a árvore visual.

### 16.3 E2E

A jornada existente será portada para o bootstrap QML com adaptadores fake ou
slots do controller:

```text
configurar raiz temporária
→ carregar slots
→ selecionar
→ verificar detalhes
→ criar backup temporário
→ listar
→ restaurar com confirmação controlada
→ excluir com confirmação controlada
→ refresh
→ verificar diagnóstico/log sanitizado
```

Todas as mutações usam `tmp_path`; saves e instalação reais permanecem somente
leitura e não são necessários para os testes automatizados.

### 16.4 Visual e smoke

Capturas serão inspecionadas em 1280 × 720, 1366 × 768, 1600 × 900 e
1920 × 1080, cobrindo páginas prontas, vazias e com erro. A validação procura
clipping, overflow, truncamento, foco, contraste, densidade, scroll e proporção.
O smoke do executável usa um runtime root e dados temporários fora da fonte.

## 17. Recursos e packaging

QML e recursos próprios serão declarados em `qml.qrc` e compilados para um módulo
Python importável no bootstrap. O engine carregará a URL `qrc:/qml/Main.qml`,
eliminando dependência do diretório de trabalho e caminhos absolutos.

O build PyInstaller deverá:

- importar o módulo de recursos gerado;
- incluir bindings `QtQml`, `QtQuick` e `QtQuickControls2` usados pelo bootstrap;
- coletar os plugins QML necessários identificados pelo build real;
- manter o root portátil já suportado;
- produzir artefato `onedir` fora da árvore fonte;
- falhar se `Main.qml` não criar root object.

O smoke validará inicialização do engine e jornada com dados temporários. Nenhum
recurso será procurado no checkout durante a execução empacotada.

## 18. Licenciamento

Módulos previstos: PySide6, Qt Core, Qt GUI, Qt QML, Qt Quick, Qt Quick Layouts e
Qt Quick Controls 2. Eles permanecem no ecossistema Qt/PySide6 compatível com o
regime LGPLv3 já adotado pelo projeto. Não há dependência GPL-only, pacote de
ícones externo ou asset proprietário planejado. Ícones vetoriais eventualmente
necessários serão originais do projeto e armazenados como recursos próprios.

Qualquer módulo Qt além dessa lista exige verificação de licença antes da adoção.

## 19. Segurança e privacidade

- QML nunca recebe capacidade genérica de filesystem.
- Operações mutáveis continuam nos serviços existentes e preservam suas checagens
  contra traversal, reparse points, swaps, inconsistência e falha parcial.
- Caminhos exibidos e erros seguem sanitização existente; logs técnicos não entram
  em snackbar ou mensagens de página.
- Restore e delete exigem seleção consistente, confirmação e revalidação no
  momento da chamada.
- O runner serializa mutações e não amplia o alvo ao receber estado obsoleto.
- Testes e smoke escrevem apenas em diretórios temporários controlados.
- O save real e a instalação real do jogo são tratados como somente leitura.

## 20. Logging

Serão adicionados somente eventos de valor operacional:

- engine QML iniciado;
- controller e ViewModels inicializados;
- falha de carregamento QML;
- falha inesperada de integração;
- descarte de resultado obsoleto quando relevante para diagnóstico.

Eventos existentes de domínio e backup permanecem como estão. Cliques, hover,
navegação comum e mudanças puramente visuais não serão registrados.

## 21. Gates de entry point e remoção

### Troca do entry point

`python -m mr_farmboy_manager` só passa a abrir QML quando:

- bootstrap e páginas críticas carregam em offscreen;
- bridge bidirecional está coberta;
- jornada configurar → saves → detalhes → backup → restore → delete → diagnóstico
  está verde com filesystem temporário;
- suíte completa está verde.

### Remoção dos Widgets

`application.py` e testes exclusivamente estruturais de Widgets só são removidos
quando, além dos gates acima:

- build PyInstaller QML está verde;
- executável abre sem usar arquivos do checkout;
- smoke da jornada está verde;
- inspeção visual nos quatro tamanhos está aprovada;
- não há regressão comportamental válida escondida em teste Widgets.

## 22. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| `application.py` mistura estado e widgets | extrair contratos de apresentação antes de migrar páginas |
| UI congelar durante parsing | runner serial fora da thread de renderização |
| resposta assíncrona obsoleta | IDs monotônicos e validação de seleção/configuração |
| concorrência com restore/delete | fila única e bloqueio de refresh durante mutação |
| recurso QML ausente no executável | qrc compilado, build fora da fonte e smoke obrigatório |
| dialogs bloquearem testes | choosers injetáveis e confirmações controláveis |
| regressão de segurança | não reimplementar serviços; usar `tmp_path` em toda mutação |
| UI genérica ou excessivamente espaçosa | tokens próprios, densidade de dashboard e inspeção visual |
| remoção precoce dos Widgets | gates explícitos de paridade, build e smoke |

## 23. Critérios de aceitação

A migração está concluída quando:

1. `python -m mr_farmboy_manager` abre a UI QML.
2. Dashboard, Saves, Backups, Configurações e Diagnóstico usam somente dados reais.
3. Seleção, refresh, detalhes, create, restore, delete e configuração têm paridade.
4. `game_data/save_1` é normalizado com feedback e teste de regressão.
5. Estados loading, empty, ready, error, disabled, selected, hover, pressed e foco
   estão presentes onde aplicáveis.
6. A UI é utilizável nos quatro tamanhos alvo sem clipping ou overflow relevante.
7. Testes unitários, integração QML, E2E, suíte completa, build e smoke passam.
8. O executável usa recursos empacotados, não a árvore fonte.
9. Widgets legados foram removidos somente depois dos gates.
10. HEAD local e `origin/main` apontam para o mesmo commit, a worktree contém no
    máximo arquivos preexistentes preservados e não há subagentes ativos.
