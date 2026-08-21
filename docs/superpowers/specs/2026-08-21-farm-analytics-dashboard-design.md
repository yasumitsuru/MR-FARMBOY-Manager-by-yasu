# MR FARMBOY Manager — design do analytics e dashboard gerencial

Data: 2026-08-21

Status: aprovado autonomamente conforme autorização explícita do pedido

Evidência normativa: `docs/reverse-engineering/save-schema.md`

## 1. Resultado de produto

O aplicativo passará de uma visão técnica de saves para um console gerencial de
leitura. A pergunta principal é: **como está a fazenda agora, quais limites
operacionais exigem atenção e quais dados o jogo realmente sustenta?**

A resposta será construída em uma cadeia auditável:

```text
par estável de saves
        ↓ parser sintático seguro
registros allowlisted + catálogo confirmado
        ↓
FarmSnapshot imutável + proveniência
        ↓ analytics puro
FarmAnalytics + FarmAlert
        ↓ models/ViewModels Qt
QML (apresentação e navegação)
```

No snapshot real auditado, o topo prioriza carteira, custo nominal diário,
colheitas disponíveis e capacidade animal. Receita/dia e saldo/dia não serão
inventados; a UI explica discretamente por que estão indisponíveis.

## 2. Objetivos

1. Interpretar o schema real com tipos explícitos e compatibilidade conservadora.
2. Produzir um snapshot lógico consistente a partir do mesmo par de arquivos.
3. Centralizar fórmulas, confiança e alertas em Python testável.
4. Mostrar cultivos, estoque, animais, trabalhadores, infraestrutura e economia
   somente quando sustentados por evidência.
5. Diferenciar zero, ausência, desconhecido e falha de leitura.
6. Tornar a proveniência consultável na UI sem expor caminhos sensíveis.
7. Corrigir estruturalmente os overlaps conhecidos em Saves e Dashboard.
8. Preservar segurança de filesystem, desempenho, acessibilidade e LGPL.

## 3. Não objetivos

- Editar, normalizar ou regravar saves.
- Executar o jogo ou carregar recursos diretamente na instalação durante uso.
- Simular produção, consumo ou vendas que não foram persistidos.
- Calcular receita/dia, lucro/dia, cobertura, demanda ideal de workers ou
  “excesso” sem referência confirmada.
- Expor registros brutos, caminhos locais ou mega-dicionários ao QML.
- Criar gráficos decorativos ou adicionar Qt Charts/dependência externa.
- Alterar versão, criar `v0.2.0` ou publicar release nesta rodada.

## 4. Decisões de brainstorming

### 4.1 Alternativa A — schema allowlisted e snapshot tipado

O parser existente continua responsável apenas por Godot TRES. Um adaptador
reconhece assinaturas/cenas confirmadas e cria tipos imutáveis. Analytics puro
consome esses tipos e produz medidas com proveniência.

Vantagens: falha fechada, compatibilidade explícita, testes pequenos, ausência
não vira zero, QML simples e custo de atualização previsível. Esta é a opção
escolhida.

### 4.2 Alternativa B — árvore genérica de variantes e mega-dicionários

Preservaria todo o save em uma árvore genérica e faria consultas dinâmicas.
Foi rejeitada porque mistura sintaxe com semântica, torna typo/ID desconhecido
silencioso, aumenta memória e expõe contratos frágeis à apresentação.

### 4.3 Alternativa C — agregação no QML

Exporia registros e usaria JavaScript/bindings para somas, filtros e alertas.
Foi rejeitada por repetir trabalho no render thread, dificultar TDD e colocar
regra gerencial na camada visual.

### 4.4 Revisão da decisão

A alternativa A adiciona mais tipos e models, mas esses contratos representam
diferenças essenciais: fonte, unidade, disponibilidade e confiança. Para evitar
cerimônia excessiva, proveniência é compartilhada por medida/seção e listas Qt
usam roles estáveis; não haverá um `QObject` por registro bruto de cultivo.

## 5. Fontes e política de confiança

### 5.1 Fontes em runtime

- `player_data.tres`: modo, opções e advancements.
- `island_main_data.tres`: inventários, crops, prédios, buffs e reservas.
- catálogo embutido no aplicativo: somente mappings e regras confirmados pela
  auditoria da versão do jogo.

O PCK não será aberto a cada refresh do aplicativo. As descobertas estáveis
necessárias serão codificadas em um catálogo pequeno, com referência à versão
auditada e testes. Um save incompatível não ativa regras aproximadas.

### 5.2 Estados de evidência

```python
class EvidenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
```

`DERIVED` exige inputs confirmados, fórmula documentada e condições satisfeitas.
`INFERRED` nunca recebe a mesma apresentação de um fato confirmado. `UNKNOWN`
não carrega valor numérico.

```python
@dataclass(frozen=True, slots=True)
class Provenance:
    status: EvidenceStatus
    source_id: str
    reason: str
    confidence: float | None = None
```

`source_id` é estável e sanitizado, como `island.inventory.wallet` ou
`rules.crop.growth-quarter`; não contém caminho absoluto.

## 6. Parsing e compatibilidade

### 6.1 Dicionários tipados

O parser aceitará wrappers `Dictionary[K, V](...)` já usados pelo jogo, sem
avaliar código e sem fazer fallback textual amplo. Tipos permitidos nessa fase:
`int`, enums qualificados e variantes já suportadas pelo parser. A estrutura
resultante continua `GodotVariantKind.DICTIONARY`.

Casos obrigatórios:

- dict tipado válido;
- dict vazio;
- zero real;
- chave/valor inválido;
- wrapper truncado;
- tipo genérico desconhecido;
- conteúdo posterior malicioso/textual não avaliado.

### 6.2 Compatibilidade semântica

O adaptador usa `scene_file_path` e conjunto mínimo de propriedades. Campos
extras são ignorados com segurança; campo necessário ausente torna somente a
seção correspondente indisponível. IDs desconhecidos são preservados com label
seguro. Um arquivo sintaticamente válido não é automaticamente semanticamente
compatível.

## 7. Modelo de domínio

Os nomes abaixo são normativos quanto à responsabilidade; podem sofrer pequeno
ajuste mecânico no plano se evitarem colisão com classes existentes.

```python
@dataclass(frozen=True, slots=True)
class MoneyBalance:
    copper: int | None
    silver: int | None
    gold: int | None

@dataclass(frozen=True, slots=True)
class CropTypeSnapshot:
    crop_id: str
    label: str
    total: int
    planted: int
    watered: int
    fertilized: int
    matured_flag: int
    harvestable: int
    dead: int
    growth_states: tuple[int, int, int, int]

@dataclass(frozen=True, slots=True)
class StockEntry:
    item_id: int
    label: str
    quantity: int
    origin: str
    mapping_status: EvidenceStatus

@dataclass(frozen=True, slots=True)
class CapacitySnapshot:
    occupied: int
    capacity: int

    @property
    def open_slots(self) -> int: ...

@dataclass(frozen=True, slots=True)
class FeederSnapshot:
    building_id: str
    building_kind: str  # coop | barn
    food_item_id: int | None
    food_label: str | None
    amount: int | None
    source_id: str

@dataclass(frozen=True, slots=True)
class WarehouseSnapshot:
    building_id: str
    slots: tuple[StockEntry, ...]
    slot_capacity: int
    minimum_set: int
    source_id: str

@dataclass(frozen=True, slots=True)
class MarketSnapshot:
    building_id: str
    slots: tuple[StockEntry, ...]
    slot_capacity: int
    source_id: str

@dataclass(frozen=True, slots=True)
class ActiveBuffSnapshot:
    building_id: str
    building_kind: str
    buff_id: int
    label: str
    upkeep_amount: int | None
    upkeep_currency: str | None
    provenance: Provenance

@dataclass(frozen=True, slots=True)
class AnimalTypeSnapshot:
    item_id: int
    label: str
    count: int
    building_kind: str

@dataclass(frozen=True, slots=True)
class WorkerTypeSnapshot:
    item_id: int
    label: str
    count: int

@dataclass(frozen=True, slots=True)
class InfrastructureTypeSnapshot:
    kind: str
    label: str
    count: int
    active_unlocks: int
    available_unlocks: int

@dataclass(frozen=True, slots=True)
class FarmSnapshot:
    slot_id: str
    captured_at: datetime
    save_fingerprint: str
    game_mode: int | None
    cozy_option_2: bool | None
    wallet: MoneyBalance | None
    crops: tuple[CropTypeSnapshot, ...]
    stock: tuple[StockEntry, ...]
    animals: tuple[AnimalTypeSnapshot, ...]
    animal_capacity: CapacitySnapshot | None
    workers: tuple[WorkerTypeSnapshot, ...]
    worker_capacity: CapacitySnapshot | None
    infrastructure: tuple[InfrastructureTypeSnapshot, ...]
    feeders: tuple[FeederSnapshot, ...]
    warehouses: tuple[WarehouseSnapshot, ...]
    markets: tuple[MarketSnapshot, ...]
    active_buffs: tuple[ActiveBuffSnapshot, ...]
    provenance: tuple[tuple[str, Provenance], ...]
    unavailable_reasons: tuple[tuple[str, str], ...]
```

As coleções são tuplas ordenadas deterministicamente. `save_fingerprint` é um
identificador derivado dos bytes/metadados já lidos; não contém o save nem será
usado para autenticação.

Os dois conjuntos chave/valor também são tuplas ordenadas, com helpers de lookup
somente leitura. `frozen=True` isoladamente não basta: o construtor copia todas
as coleções recebidas antes de convertê-las, de modo que uma mutação posterior
na entrada não altere o snapshot compartilhado.

`CapacitySnapshot` aceita somente `0 <= occupied <= capacity`. Valor negativo
ou ocupação acima da capacidade não é normalizado nem truncado: o adaptador
omite a capacidade, registra razão em `unavailable_reasons` e marca o snapshot
como parcial. Identidades de prédio são ordinais determinísticos sanitizados do
snapshot (`coop-01`, por exemplo), nunca `node_name` ou caminho operacional.

### 7.1 Origem de estoque

Estoque não será somado indiscriminadamente:

- `wallet/direct`: `IslandInventory`;
- `warehouse`: item e prédio de origem;
- `market`: item à venda, inclusive zero persistido;
- `feed`: ração do criadouro;
- `building_occupancy`: animais/workers, não estoque geral.

Uma visão consolidada só soma origens semanticamente compatíveis e explicita a
operação. Por padrão, Recursos mostra inventário direto e depósitos em grupos.

## 8. Analytics

```python
@dataclass(frozen=True, slots=True)
class MetricValue:
    metric_id: str
    label: str
    value: int | float | None
    unit: str
    availability: str  # available | unavailable
    provenance: Provenance
    explanation: str = ""

@dataclass(frozen=True, slots=True)
class FarmAlert:
    alert_id: str
    severity: str  # info | warning | critical
    title: str
    detail: str
    reason: str
    source_id: str

@dataclass(frozen=True, slots=True)
class FarmAnalytics:
    kpis: tuple[MetricValue, ...]
    alerts: tuple[FarmAlert, ...]
    crop_totals: CropTotals | None
    nominal_upkeep: EconomyBreakdown | None
    unavailable_metrics: tuple[MetricValue, ...]
```

O serviço `build_farm_analytics(snapshot)` é puro, determinístico e não conhece
Qt, filesystem ou locale.

### 8.1 Métricas implementadas

| ID | Unidade | Inputs | Fórmula/condição |
|---|---|---|---|
| `wallet.copper/silver/gold` | moeda | `IslandInventory` | valor direto; ausência permanece indisponível |
| `crops.harvestable` | lotes | flags crop | soma de `is_harvestable=true` |
| `crops.growth_state.N` | lotes/% | estado de cada crop | contagem e `count / total` quando total > 0 |
| `animals.capacity` | animais | Coop/Barn e unlocks | ocupação e `2 + 2*unlocks` por prédio |
| `workers.capacity` | workers | House e unlocks | ocupação e `2 + 2*unlocks` por prédio |
| `feeders.below_restock` | prédios | `food`, regra 48 | count(amount < 48); feeder ausente é tratado separadamente |
| `warehouse.worker_available` | unidades | stock e `minimum_set` | stock se -1; senão `max(stock-minimum, 0)` |
| `economy.nominal_upkeep` | moeda/dia | modo, workers, animals, slots, buffs | fórmula do schema, somente com todos os inputs aplicáveis |

Receita/dia, saldo/dia, produção/dia, consumo/dia, cobertura e necessidade de
workers são `MetricValue(value=None, availability="unavailable")`, com razão
curta. Não são emitidos como KPIs numéricos.

### 8.2 Regras de alerta

1. `animals.capacity.full` — warning quando `occupied == capacity > 0`; detalhe
   inclui ambos os valores.
2. `feeders.restock.threshold` — warning quando pelo menos um feeder confirmado
   tem `amount < 48`; detalhe agrega total e separa Coop/Barn.
3. `warehouse.reserved.stock` — info quando `worker_available == 0` devido à
   reserva; agrega slots, sem chamar de déficit.
4. Nenhuma regra usa limiar arbitrário de “baixo”, “excesso” ou dias.

Se `occupied > capacity`, valores negativos ou capacidade estruturalmente
impossível forem encontrados, a seção fica parcial/indisponível e recebe uma
razão sanitizada. Esse caso não é convertido no alerta normal de capacidade
cheia.

Não haverá alerta crítico no snapshot auditado. Severidade não será usada para
dramatizar capacidade cheia quando nenhuma perda/risco crítico foi confirmada.

## 9. Camada Qt de apresentação

### 9.1 Models

Criar models pequenos sobre as tuplas do snapshot/analytics:

- `MetricsModel`: `metricId`, `label`, `valueLabel`, `unitLabel`,
  `availability`, `evidenceLabel`, `explanation`;
- `FarmAlertsModel`: `alertId`, `severity`, `title`, `detail`, `reason`, `source`;
- `CropsModel`: `cropId`, `label`, `total`, `planted`, `maturedFlag`,
  `harvestable`, `dead`, `state0..state3`;
- `StockModel`: `itemId`, `label`, `quantityLabel`, `originLabel`,
  `mappingStatus`;
- `AnimalsModel`: `itemId`, `label`, `count`, `buildingKind`;
- `WorkersModel`: `itemId`, `label`, `count`;
- `InfrastructureModel`: `kind`, `label`, `count`, `capacityLabel` quando houver;
- `EconomyBreakdownModel`: `componentId`, `label`, `amountLabel`, `currency`.

Valores são formatados no Python/formatters existentes. QML não interpreta
`None`, não calcula percentuais e não localiza números manualmente.

### 9.2 DashboardViewModel

O `DashboardViewModel` deixa de derivar somente os detalhes agrícolas mínimos e
passa a expor:

- `state`: `idle | loading | ready | partial | unavailable | error`;
- `selectedSlotLabel`, `lastUpdatedLabel`, `snapshotEvidenceLabel`;
- `kpisModel`, `alertsModel`, `growthStatesModel`;
- models de preview para crops, recursos, animais, workers e economia;
- contagens/resumos de capacidade;
- `unavailableSummary` e `hasUnavailableMetrics`;
- slots `refresh()` e navegação por intenção, sem filesystem no QML.

`partial` significa que seções independentes válidas serão mostradas enquanto a
razão de cada seção ausente permanece disponível. Um erro do catálogo de crops
não apaga carteira confirmada.

### 9.3 SavesViewModel

O carregamento de detalhes constrói uma única vez `FarmSnapshot` e
`FarmAnalytics`; Saves e Dashboard compartilham o mesmo resultado imutável. Não
há segunda leitura concorrente para popular cards. Refresh invalida o par de
forma atômica após sucesso.

## 10. Arquitetura visual

### 10.1 Direção

A interface continua dark-first e agrícola, preservando a paleta de floresta já
reconhecível no produto. A assinatura visual será um **livro de campo
operacional**: faixas densas de informação, números monoespaçados e um filete
vertical curto que codifica seção/evidência. Não será um conjunto de cards
gigantes genéricos.

Tokens base existentes continuam:

- fundo `#0B1410`;
- sidebar `#0F1C16`;
- superfícies `#14231C`, `#1A2D24`, `#20362B`;
- acento `#86C96F`;
- âmbar para atenção, vermelho somente para erro real;
- Segoe UI para texto e Cascadia Mono para números/IDs.

Adicionar tokens semânticos para `confirmed`, `derived`, `unknown`, `warning`,
`sectionRailWidth`, densidade de tabela e breakpoints. Cor nunca será o único
meio de comunicar estado.

### 10.2 Hierarquia de navegação

As páginas existentes continuam. A área gerencial ganha páginas relacionadas,
acessíveis pela Dashboard e agrupadas na navegação:

```text
Visão geral
Cultivos
Recursos
Pessoas e animais
Infraestrutura e economia
Saves
Backups
Configurações
Diagnóstico
```

Se a largura mínima tornar nove itens pouco legíveis, itens gerenciais podem
usar um grupo expansível ou navegação interna estável, sem esconder Saves,
Backups ou Configurações.

## 11. Dashboard — composição

### 11.1 Topbar

- título `Visão da fazenda`;
- slot ativo e timestamp do snapshot;
- estado de configuração em uma linha própria/flow layout;
- ação Atualizar com tamanho implícito e sem posição absoluta.

### 11.2 KPIs

Faixa responsiva com quatro células compactas:

1. Carteira: cobre em destaque, prata e ouro como linhas secundárias;
2. Custo nominal/dia: cobre e condição do modo, badge `Derivado`;
3. Prontos para colher: `is_harvestable`, não `matured`;
4. Capacidade animal: `52 / 52` no exemplo auditado.

Receita/dia e saldo/dia ficam fora desta faixa. Um bloco discreto “Dados não
registrados pelo save” explica a ausência, em vez de mostrar `0`.

### 11.3 Alertas

Lista curta e ordenada por severidade, com título, detalhe e botão/ação de
navegação para a seção relevante. `reason` e `source` ficam acessíveis por
expansão ou tooltip teclado/mouse.

### 11.4 Resumos operacionais

- Economia: decomposição do custo e acumulados claramente rotulados;
- Cultivos: top tipos, total/plantados/colhíveis/mortos e link para tabela;
- Estágios de crescimento: quatro faixas semânticas, com ressalva no estágio 0;
- Recursos: inventário direto por categoria e reservas de armazém;
- Pessoas e animais: contagens por tipo e ocupação/capacidade;
- Infraestrutura: quantidade de prédios, slots usados e upgrades.

Tabelas completas vivem nas páginas relacionadas; a Dashboard mostra previews
de no máximo 5–8 linhas para manter prioridade e desempenho.

## 12. Páginas relacionadas

### 12.1 Cultivos

Tabela ordenável por colhíveis/total/nome:

```text
Cultivo | Total | Plantados | Flag maturou | Colhíveis | Mortos | Estágios
```

“Flag maturou” possui tooltip explicando que pode permanecer após colheita.
Produção e consumo não aparecem como colunas vazias. IDs sem mapping usam label
seguro e badge desconhecido.

### 12.2 Recursos

Filtros por origem: Inventário direto, Armazéns, Mercados e Ração. Colunas:

```text
Recurso | Quantidade | Origem | Reserva | Disponível a workers
```

Reserva/disponibilidade só existe para Warehouse. Uma chave ausente não produz
linha zero; zero persistido pode aparecer com indicação explícita.

### 12.3 Pessoas e animais

Duas seções, cada uma com totais e capacidade confirmada. Workers mostram classe
e quantidade, além da capacidade global 184/190. Não mostram “necessários”.
Animais mostram tipo, quantidade, prédio e capacidade 52/52; ração abaixo do
gatilho aparece associada ao grupo de prédios, não como consumo/dia.

### 12.4 Infraestrutura e economia

- contagem e upgrades por tipo de prédio;
- slots de Warehouse 33/38 e Market 33/36 no exemplo real;
- breakdown auditável do upkeep;
- buffs ativos e custo associado quando confirmado;
- acumulados `EARNED` separados da carteira;
- lista curta de métricas indisponíveis com motivo.

## 13. Estados e texto honesto

- `0`: valor real persistido/calculado.
- `—`: medida não disponível naquela linha.
- `Indisponível`: seção/medida não fornecida pelo schema.
- `Não reconhecido`: ID ou assinatura preservada sem mapping.
- `Parcial`: parte do snapshot é válida, com razão local.

Labels técnicos não vazam sem contexto. `Estado 0..3` passa a “0–<25% / reset”,
“25–<50%”, “50–<75%”, “≥75% / colhível”, acompanhados por descrição acessível.

## 14. Responsividade e correções estruturais

Breakpoints de composição:

- `compact`: 960–1199 px — sidebar compacta; KPIs 2 colunas; tabelas com scroll
  horizontal controlado; headers empilham ação após texto;
- `regular`: 1200–1599 px — KPIs 4 colunas; resumos em 2 colunas;
- `wide`: 1600+ px — conteúdo com largura máxima legível e resumos 3 colunas.

Altura é tratada por `ScrollView`; nenhum conteúdo gerencial depende de altura
fixa. A dimensão mínima 960x640 é gate obrigatório.

### 14.1 Bug Saves / Atualizar

`SectionHeader` não aceitará um item de ação solto dentro do mesmo `RowLayout`
sem medição. O componente terá região textual com `Layout.fillWidth`, largura
mínima e wrap, e região de ações com `implicitWidth/implicitHeight`. Em compact,
um `ColumnLayout`/estado de layout coloca as ações abaixo. O `implicitHeight` do
header inclui título, subtítulo e ações; a seção seguinte respeita o tamanho.

### 14.2 Bug Configuração ativa

O badge deixa de competir com o próximo bloco na linha do título. O header usa
o mesmo contrato responsivo e o badge participa do fluxo, podendo quebrar para
linha própria. Nenhum `y`, largura negativa ou anchor conflitante será usado.

### 14.3 Invariantes de layout

- filhos gerenciados por Layout não recebem anchors conflitantes;
- texto multilinha define wrap e altura implícita;
- actions possuem largura implícita e nunca cobrem texto;
- conteúdo seguinte começa após `header.y + header.height`;
- scrollbars e tabelas permanecem alcançáveis por teclado;
- labels elidem apenas quando tooltip/nome acessível preserva o conteúdo.

## 15. Acessibilidade

- foco visível e ordem coerente;
- `Accessible.name/description` para KPI, badge de evidência e alerts;
- contraste mínimo preservado; não depender apenas de verde/âmbar;
- targets com altura adequada no mínimo suportado;
- números lidos com label/unidade, não apenas glifo de moeda;
- reduced motion implícito: sem animações essenciais ou contínuas.

## 16. Performance e concorrência

- parsing e analytics continuam no runner Python, fora do render thread;
- uma leitura estável produz todos os models da seleção;
- agregação é O(n) sobre os 3.636 registros e ocorre uma vez por refresh;
- QML recebe previews e models, nunca a lista bruta;
- model reset é único por snapshot; bindings não recalculam somas;
- seleção/refresh antigo não substitui resultado mais novo;
- memória é limitada a registros tipados necessários e agregados.

Meta local: analytics de um save do porte auditado não deve introduzir atraso
perceptível além do parsing atual. Um teste de desempenho rígido por tempo não é
gate em CI; a estrutura O(n) e a ausência de loops QML são gates de revisão.

## 17. Segurança e privacidade

- operações reais de save permanecem somente leitura nesta funcionalidade;
- testes mutáveis usam `tmp_path` e fixtures sintéticas;
- o domínio não contém `Path` público nem conteúdo bruto de arquivos;
- erros QML são sanitizados; logs técnicos existentes continuam limitados;
- nenhuma ação de analytics restaura, renomeia, deleta ou salva;
- parser não usa `eval`, import dinâmico ou execução de recursos Godot;
- fingerprints não são enviados nem persistidos externamente.

## 18. Licenciamento

A implementação usa Python, PySide6 e módulos QML já presentes sob a estratégia
LGPL do projeto. Não adiciona Qt Charts, módulo GPL-only, biblioteca de charts,
fonte proprietária ou asset do jogo. Visualizações simples são compostas por
Layouts, Rectangles, Labels, Repeaters e ListViews já empacotados.

## 19. Estratégia de testes

### 19.1 Parser — TDD

- RED com `Dictionary[int,int]` mínimo realista;
- dict vazio, zero, ID desconhecido, truncamento e tipo inesperado;
- nenhum arquivo real ou absoluto em fixture;
- regressão integral do parser existente.

### 19.2 Domínio/analytics — TDD

- fixture → parser → adapter → snapshot;
- carteira com ausência versus zero;
- crops por tipo, flags e estado;
- `matured_flag != harvestable` após reset;
- capacidades 0, parcial, cheia e inválida;
- isolamento contra mutação das listas/mappings usados para construir snapshot;
- upkeep com modo elegível, Cozy desativando cobrança e input ausente;
- reservas `-1`, abaixo, igual e acima;
- IDs conhecidos/desconhecidos;
- ordenação determinística e snapshot imutável.

### 19.3 Alertas — TDD

Para cada regra: dispara, não dispara, boundary exato, severity, ID, razão e
fonte. Strings longas não são o contrato; significado e valores são.

### 19.4 ViewModels/models

- roles estáveis e formatação localizada;
- `None` vira `—/Indisponível`, nunca `0`;
- estado ready/partial/unavailable/error;
- refresh atômico e resultado antigo descartado;
- previews limitados e models completos acessíveis nas páginas.

### 19.5 QML e E2E

- todas as páginas carregam offscreen;
- cards condicionais, alerts e listas conectados a models reais/fakes tipados;
- ausência não vira zero;
- teste integrado `fixture → parser → analytics → ViewModel → QML`;
- Saves, Backups, Configurações e Diagnóstico permanecem funcionais;
- nenhuma janela modal em teste automatizado.

## 20. QA de layout e visual

Resoluções obrigatórias:

| Resolução | Perfil |
|---|---|
| 960x640 | mínimo/compact |
| 1280x720 | regular baixo |
| 1366x768 | regular comum |
| 1600x900 | wide |
| 1920x1080 | wide grande |

Para cada resolução: Dashboard, Saves e ao menos uma página de tabela. Verificar
header, ação Atualizar, badge Configuração ativa, sidebar, KPIs, alertas, scroll,
elide, foco, clipping e interseção geométrica.

Testes estruturais de QML localizarão os itens por `objectName` e provarão:

```text
action não intersecta title/subtitle
header não intersecta conteúdo seguinte
badge não intersecta seção seguinte
cards não compartilham geometria positiva
conteúdo permanece dentro do viewport ou do ScrollView
```

Não haverá assertions pixel-perfect. Screenshots de QA serão guardados sob
`build/` e o relatório versionado em `docs/qa/` registrará achados, correções e
resultado por resolução.

## 21. Build e smoke

Após suíte completa:

1. gerar recursos QML conforme workflow existente;
2. executar PyInstaller isolado sem reaproveitar cache bloqueado;
3. usar dados temporários no smoke funcional;
4. confirmar abertura, Dashboard, Saves, seleção, analytics, Backups,
   Configurações e Diagnóstico;
5. registrar artefato e resultados;
6. não criar tag/release.

## 22. Critérios de aceite

- schema persistente e matriz de confiança revisados;
- parser entende dicionários tipados reais sem ampliar execução de sintaxe;
- snapshot consistente, imutável e com proveniência;
- analytics e alerts cobertos por TDD;
- carteira, crops por tipo, animais, recursos, workers e infraestrutura úteis;
- custo nominal/dia diferenciado de receita/saldo indisponíveis;
- nenhuma métrica ausente convertida em zero;
- nenhuma classificação arbitrária de déficit, superávit ou excesso;
- “Trilho de crescimento” removido e semântica real explicada;
- overlaps de Atualizar e Configuração ativa eliminados por layout;
- QA verde em 960, 1280, 1366, 1600 e 1920;
- suíte, QML/E2E, build e smoke verdes;
- dados reais e instalação com zero escritas;
- branch e remoto sincronizados, arquivos locais protegidos não staged;
- zero subagentes ativos;
- versão continua preparada como 0.2.0, sem tag ou release.

## 23. Limites assumidos conscientemente

O produto responderá melhor “quanto existe, o que está pronto e quais limites
confirmados estão cheios/abaixo do gatilho”. Ele não responderá “quanto vou
produzir/lucrar amanhã” porque o save auditado não fornece fluxos temporais
suficientes. Essa lacuna é uma conclusão da auditoria, não uma falha a esconder.
