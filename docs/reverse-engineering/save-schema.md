# MR FARMBOY — esquema de save e evidências para analytics

Data da auditoria: 2026-08-21

Escopo observado: slot `save_1`, MR FARMBOY para Godot 4.6.2

Objetivo: documentar somente dados que possam sustentar analytics de leitura

## 1. Regras de evidência

Esta documentação separa três níveis:

- **CONFIRMADO**: nome, tipo e significado possuem evidência inequívoca no save,
  em enum ou na lógica instalada do jogo.
- **INFERIDO**: a hipótese é sustentada por mais de uma evidência, mas não foi
  observada diretamente como regra completa. A confiança acompanha o campo.
- **DESCONHECIDO**: o save e os arquivos auditados não permitem provar o valor
  ou a semântica. `0` nunca representa este estado.

Uma métrica derivada não é um campo persistido. Ela deve informar seus inputs,
fórmula e condições. Um valor derivado de inputs confirmados pode ter confiança
alta, mas continua identificado como derivado na apresentação.

## 2. Método e integridade da auditoria

Os originais foram abertos somente para listagem, leitura e hash. A análise que
exigia extração ou scripts foi feita em uma cópia controlada ignorada pelo Git.
Nenhum save completo, caminho com nome de usuário ou arquivo proprietário do
jogo é incluído no repositório.

Fontes:

- `%APPDATA%\Godot\app_userdata\MR FARMBOY\game_data\save_1`;
- `<instalação do jogo>\MrFarmBoy.pck`;
- cópia de auditoria local `build/farm-analytics-audit-20260821-01`.

Integridade observada:

| Artefato | Tamanho | SHA-256 | Resultado |
|---|---:|---|---|
| `island_main_data.tres` | 2.472.478 B | `0A4433AA4348EDDAEFD646038645FEC55FC686DFE01BCB88FF44B5EF9B42C1BA` | igual ao backup e à cópia |
| `island_main_backup_data.tres` | 2.472.478 B | `0A4433AA4348EDDAEFD646038645FEC55FC686DFE01BCB88FF44B5EF9B42C1BA` | igual ao principal |
| `player_data.tres` | 7.413 B | `DA8D1FB98BA643DCE68F4914D3FC00257863BA0B1B1DEAF3ED579942C91EA9C0` | igual ao backup e à cópia |
| `player_backup_data.tres` | 7.413 B | `DA8D1FB98BA643DCE68F4914D3FC00257863BA0B1B1DEAF3ED579942C91EA9C0` | igual ao principal |
| `MrFarmBoy.pck` | 151.516.800 B | `AFC6916307C85061938EDC020B71AAE8C79C0E26F8DA0CD43397D811079A17C8` | somente leitura |

Os hashes dos quatro saves originais foram repetidos ao fim da investigação e
permaneceram iguais. Escritas nos dados reais e na instalação: **0**.

O PCK possui cabeçalho `GDPC`, formato de pacote 3, versão de engine 4.6.2,
2.840 entradas e offsets válidos. Scripts selecionados eram tokens GDScript
`GDSCe` v101 comprimidos com Zstandard. A reconstrução foi usada para localizar
enums e fórmulas; nenhum arquivo extraído foi escrito de volta na instalação.

## 3. Estrutura lógica observada

```text
save_1/
├── player_data.tres
├── player_backup_data.tres
├── island_main_data.tres
└── island_main_backup_data.tres
```

`player_data.tres` contém um recurso de progresso global. O arquivo de ilha
contém 3.636 sub-recursos heterogêneos, identificados principalmente por
`scene_file_path` e pela assinatura das propriedades. O parser deve reconhecer
apenas assinaturas allowlisted; não deve transformar qualquer recurso em um
mega-dicionário de domínio.

Para obter um snapshot lógico consistente, os dois arquivos principais devem
ser lidos pelo mecanismo de leitura estável já usado pelo aplicativo: metadados
antes, bytes, metadados depois e rejeição/retry se houver mudança. Os agregados
devem nascer do mesmo par estável.

## 4. Matriz de cobertura gerencial

| Métrica | Status | Origem | Decisão de UI |
|---|---|---|---|
| Carteira por moeda | CONFIRMADO | `IslandInventory.inventory` + `itemID` | mostrar |
| Receita atual/dia | DESCONHECIDO | nenhum fluxo ou histórico temporal confirmado | indisponível/omitir |
| Despesa nominal/dia | DERIVADO, confiança alta | regras de upkeep + estado salvo + modo | mostrar com proveniência |
| Saldo financeiro/dia | DESCONHECIDO | receita/dia ausente | indisponível/omitir |
| Ganhos acumulados | CONFIRMADO | advancement `EARNED` | pode mostrar como acumulado; nunca como receita/dia |
| Cultivos por tipo | CONFIRMADO | registros de crop + `scene_file_path` + enum | mostrar |
| Flags agrícolas | CONFIRMADO | propriedades booleanas por registro | mostrar |
| Semântica dos estados 0..3 | CONFIRMADO com ressalva no estado 0 | fórmula em `base_crop_crop.gdc` | mostrar labels honestos |
| Produção agrícola/dia | DESCONHECIDO | agenda/taxa efetiva não persistida | indisponível |
| Animais por tipo | CONFIRMADO | inventários de Coop/Barn + `itemID` | mostrar |
| Capacidade animal | DERIVADO, confiança alta | prédios, upgrades e `slot_limit` | mostrar |
| Consumo de ração/dia | DESCONHECIDO | não há taxa agregável no snapshot | indisponível |
| Gatilho de reposição de ração | CONFIRMADO | `feed_animal`: `food < 48` | alertar |
| Recursos/estoque atual | CONFIRMADO | inventário direto e inventários por prédio | mostrar por origem |
| Capacidade de armazéns/mercados | DERIVADO, confiança alta | prédios, upgrades e `slot_limit` | mostrar |
| Produção/consumo de recursos | DESCONHECIDO | ausência de fluxo temporal persistido | indisponível |
| Trabalhadores por classe | CONFIRMADO | inventários de House + advancement `HIRED` | mostrar |
| Capacidade de trabalhadores | DERIVADO, confiança alta | House + upgrades + `slot_limit` | mostrar |
| Trabalhadores necessários/déficit | DESCONHECIDO | não existe demanda-alvo persistida | não inventar |
| Infraestrutura por tipo | CONFIRMADO | `scene_file_path` | mostrar |
| Reserva de armazém | CONFIRMADO | `minimum_set` + inventário do próprio armazém | mostrar como disponibilidade, não excesso |
| Cobertura em dias | DESCONHECIDO | consumo líquido confiável ausente | não calcular |

## 5. Campos confirmados

| Campo | Fonte | Tipo | Significado | Confiança | Exemplo observado | Uso |
|---|---|---|---|---|---|---|
| `time` | player | float | tempo interno persistido | CONFIRMADO | `13802.039...` | contexto, não taxa |
| `gameMode` | player | int | modo de jogo selecionado | CONFIRMADO | `2` | economia |
| `cozy_option_1` | player | bool | opção Cozy persistida | CONFIRMADO | `true` | contexto |
| `cozy_option_2` | player | bool | desativa cobrança de upkeep quando `true` | CONFIRMADO | `false` | economia |
| `island_id` | player | enum/int | ilha ativa | CONFIRMADO | `3` | contexto |
| `current_tutorial` | player | int | etapa interna de tutorial | CONFIRMADO | `10` | diagnóstico |
| `advancements_data` | player | dict aninhado | acumuladores por `AdvDataID` e `itemID` | CONFIRMADO | grupos 0..14 | cruzamento |
| `scene_file_path` | island resource | string | tipo de cena que originou o registro | CONFIRMADO | `.../House.tscn` | discriminação |
| `node_name` | island resource | string | identidade local do nó salvo | CONFIRMADO | `House` | diagnóstico, não label público |
| `inventory` | recursos diversos | `Dictionary[int,int]` ou dict | quantidade por `itemID` no dono do recurso | CONFIRMADO | `{57: 5164089}` | estoque/capacidade |
| `food` | Coop/Barn | `Dictionary[int,int]` | ração armazenada no prédio | CONFIRMADO | `{11: 57}` | alertas |
| `minimum_set` | Warehouse | int | reserva subtraída antes de liberar item a workers; `-1` desabilita | CONFIRMADO | `999` | disponibilidade |
| `unlocks` | prédio | `Array[bool]` | upgrades de capacidade ativados | CONFIRMADO | `[true,false]` | capacidade |
| `active_buffs` | prédios únicos | `Array[buffID]` | buffs ativos | CONFIRMADO | `[2,5]` | upkeep/diagnóstico |
| `current_growth_state` | crop | int | quarto de progresso de crescimento, limitado a 0..3 | CONFIRMADO | `0..3` | cultivos |
| `is_planted` | crop | bool | flag persistida de plantio | CONFIRMADO | `true` | cultivos |
| `is_watered` | crop | bool | flag persistida de rega | CONFIRMADO | `true` | cultivos |
| `is_fertilized` | crop | bool | flag persistida de fertilização | CONFIRMADO | `false` | cultivos |
| `is_matured` | crop | bool | flag histórica/persistida de maturação | CONFIRMADO | `true` | não usar como prontidão atual |
| `is_harvestable` | crop | bool | prontidão atual para colheita | CONFIRMADO | `true` | KPI/alerta |
| `is_dead` | crop | bool | flag persistida de morte | CONFIRMADO | `false` | cultivos |

### 5.1 Dicionários tipados

O formato real usa, entre outros:

```godot
Dictionary[int, int]({
    57: 5164089,
    58: 130946,
})
```

Na baseline, esse wrapper chega ao parser como `OPAQUE`, embora dicionários não
tipados sejam suportados. O suporte deve ser adicionado de forma restrita e
testada, preservando tipos de chave/valor e rejeitando wrappers inesperados.
Fixtures devem ser mínimas; o save real não deve ser commitado.

## 6. Enums e mapeamentos necessários

### 6.1 Grupos de advancement (`AdvDataID`)

| ID | Nome confirmado |
|---:|---|
| 0 | UNLOCKS |
| 1 | GATHERED |
| 2 | SOLD |
| 3 | FED |
| 4 | BUILT |
| 5 | HIRED |
| 6 | UPGRADE |
| 7 | PLANTED |
| 8 | ANIMAL |
| 9 | BOUGHT |
| 10 | CARRIED |
| 11 | EARNED |
| 12 | FORGED |
| 13 | CROP_FIELD |
| 14 | NEGATIVE |

`SOLD` registra quantidades acumuladas, não receita monetária. `EARNED` registra
moeda acumulada por ID. Nenhum deles fornece janela de tempo adequada para
`/dia`.

### 6.2 IDs essenciais de item

| IDs | Categoria e nomes confirmados |
|---|---|
| 1, 2 | WOOD, STONE |
| 3..28 | cultivos/árvores base: WHEAT, TOMATO_GREEN, CARROT, TURNIP, CORN, PUMPKIN, CABBAGE, ORANGE_PEPPER, GREEN_PEPPER, WATERMELON, PARSNIP, CUCUMBER, CHILI_PEPPER, RED_PEPPER, GRAPES, STRAWBERRY, GARLIC, LEAK, ONION, SUNFLOWER, RADDISH, POTATO, APPLE, CHERRY, PEAR, PEACH |
| 29..32 | EGG, MANURE, WOOL, MILK |
| 47..50 | CHICKEN, PIG, SHEEP, COW |
| 51..56 | FARMER, GATHERER, CARRIER, RANCHER, FORESTER, MINER |
| 57..59 | COPPER, SILVER, GOLD |
| 268 | CHILI_PEPPER_GREEN |
| 296 | CORN_RED |
| 300 | CORN_WHITE |
| 308 | RADISH_GREEN |
| 320 | RYE |
| 324 | BARLEY |
| 328 | PINTO_BEANS |
| 340, 342 | DUCK, GOOSE |
| 341, 343 | BABY_DUCK, BABY_GOOSE |
| 344..346 | DUCK_EGG, GOOSE_EGG, WILD_EGG |
| 348 | RANCHER_2 |

IDs desconhecidos devem continuar exibidos como identidade segura (`Item 999`,
por exemplo), com status de mapping desconhecido. Não devem ser descartados nem
receber um nome aproximado.

## 7. Cultivos

### 7.1 Fórmula confirmada dos estados

O script `base_crop_crop.gdc` define:

```text
total_growth_minutes = harvestTime_days * 1440
state = clamp(int(elapsed_growth / (total_growth_minutes / 4)), 0, 3)
```

Ao entrar no estado 3, o jogo define `is_matured = true` e
`is_harvestable = true`. Ao colher, o jogo retorna ao estado 0 e limpa
`is_planted`, `is_watered` e `is_harvestable`, mas não limpa `is_matured`.
Um novo plantio limpa `is_matured`.

Labels sustentáveis:

| Estado | Semântica confirmada | Ressalva |
|---:|---|---|
| 0 | 0% a menos de 25% do ciclo cronometrado | também contém lote resetado/não plantado após colheita |
| 1 | 25% a menos de 50% | requer leitura conjunta das flags |
| 2 | 50% a menos de 75% | requer leitura conjunta das flags |
| 3 | 75% ou mais; marca colhível | `is_harvestable` é a fonte de prontidão atual |

Portanto, a UI usará **Estágios de crescimento**, nunca “Trilho de
crescimento”. O KPI operacional usa `is_harvestable`, não `is_matured`.

### 7.2 Evidência observada

| Medida | Valor |
|---|---:|
| registros agrícolas | 2.578 |
| plantados | 2.453 |
| regados | 2.452 |
| fertilizados | 0 |
| flag `matured` | 1.087 |
| colhíveis | 962 |
| mortos | 0 |
| estado 0 | 665 |
| estado 1 | 418 |
| estado 2 | 533 |
| estado 3 | 962 |

No estado 0, 125 registros preservam `is_matured=true`; isso prova que
“maduros” e “colhíveis agora” não são sinônimos.

Contagem por tipo/cena observada:

| Cultivo | Registros |
|---|---:|
| Turnip | 286 |
| Radish green | 230 |
| Orange pepper | 170 |
| Onion | 165 |
| Garlic | 159 |
| Pumpkin | 153 |
| Wheat | 146 |
| Green pepper | 140 |
| Barley | 135 |
| Parsnip | 115 |
| Leek | 114 |
| Rye | 100 |
| Corn red | 98 |
| Chili green | 90 |
| Pinto beans | 80 |
| Strawberry | 77 |
| Grapes | 70 |
| Carrot | 66 |
| Corn white | 64 |
| Tomato green | 63 |
| Cucumber | 56 |
| Peach tree | 1 |

O advancement `CROP_FIELD` soma 2.577 e coincide com todos os registros exceto
a árvore de pêssego, reforçando o mapping sem transformar a árvore em lavoura.

## 8. Economia e estoques

### 8.1 Carteira atual confirmada

Fonte: inventário cujo `node_name` é `IslandInventory`.

| Moeda | itemID | Valor observado |
|---|---:|---:|
| Cobre | 57 | 5.164.089 |
| Prata | 58 | 130.946 |
| Ouro | 59 | 412 |

`EARNED` contém acumulados diferentes (cobre 11.219.528, prata 166.150, ouro
485). Eles representam ganhos históricos, não a carteira e não uma taxa.

Ausência de chave não significa quantidade zero. O save preserva algumas
chaves com zero e omite outras; o contrato deve manter `None/unavailable` para
ausência e `0` apenas para zero persistido.

### 8.2 Despesa nominal diária derivada

O modo persistido é 2, com `cozy_option_2=false`. `npcs_map.gdc` cobra os três
acumuladores de upkeep uma vez por `time_tick_day`; quando
`cozy_option_2=true`, não cobra.

Fórmula nominal de cobre para o snapshot auditado:

```text
workers               = 184 * 10                         = 1.840
adult animals         = 52 * 1                          =    52
warehouse item slots  = 33 distinct inventory keys * 1 =    33
market item slots     = 33 distinct inventory keys * 1 =    33
blacksmith buffs      = tier 2.000 + tier 2.000         = 4.000
---------------------------------------------------------------
copper nominal/day                                         5.958
silver nominal/day (no active Inn buffs)                       0
gold nominal/day (no active Church buffs)                       0
```

Nome de UI: **Custo nominal/dia**, status **DERIVADO — confiança alta**. Ele é
um cálculo estático das regras e do snapshot, não uma transação observada. A UI
deve expor a decomposição e a condição `cozy_option_2=false`.

Buffs 69 e 79 do Horse Stable estão ativos, mas o script correspondente não
atribui upkeep. Buffs 2 e 5 do Blacksmith pertencem ao tier de 2.000 cobre.

Receita/dia e saldo/dia permanecem desconhecidos. Não dividir `EARNED` por
tempo/dias e não converter `SOLD` em dinheiro sem histórico de transações.

## 9. Animais, trabalhadores e capacidade

### 9.1 Animais

Não existem cenas individuais persistidas em `/characters/animals/`. A fonte
correta são os inventários de Coop e Barn, que o jogo usa para instanciar os
animais.

| Tipo | Quantidade |
|---|---:|
| Chicken | 8 |
| Duck | 8 |
| Goose | 8 |
| Pig | 12 |
| Sheep | 8 |
| Cow | 8 |
| Total | 52 |

Capacidade confirmada por regra: base 2, mais 2 por unlock verdadeiro.

| Prédio | Ocupação | Capacidade | Estado derivado |
|---|---:|---:|---|
| 6 Coops | 24 | 24 | cheio |
| 7 Barns | 28 | 28 | cheio |
| Total | 52 | 52 | cheio |

“Cheio” usa um limite explícito e não é sinônimo de “excesso”.

### 9.2 Ração

Ração persistida total: 210 de Green Pepper e 167 de Corn White. O método
`feed_animal` registra necessidade de reposição quando a quantidade do feeder é
menor que 48. O snapshot tem 8 de 13 criadouros abaixo desse gatilho: 6 Barns e
2 Coops. Valores podem passar de 50 por entregas; 50 não deve ser apresentado
como capacidade rígida.

Não há base suficiente para consumo/dia ou dias de cobertura.

### 9.3 Trabalhadores

Fonte: inventários de House. O advancement `HIRED` repete exatamente as mesmas
contagens e `TOTAL_HIRED=184`, fornecendo confirmação cruzada.

| Classe | Quantidade |
|---|---:|
| Farmer | 70 |
| Gatherer | 55 |
| Carrier | 27 |
| Rancher | 13 |
| Rancher 2 | 11 |
| Forester | 4 |
| Miner | 4 |
| Total | 184 |

As 46 Houses possuem 49 unlocks verdadeiros. Capacidade:
`46 * 2 + 49 * 2 = 190`; ocupação 184; vagas 6. “Vagas” é capacidade livre,
não prova necessidade, ociosidade ou déficit de trabalhadores.

## 10. Infraestrutura, mercados e armazéns

Contagens observadas:

| Tipo | Quantidade |
|---|---:|
| House | 46 |
| Warehouse | 14 |
| Market | 13 |
| Bridge | 7 |
| Barn | 7 |
| Coop | 6 |
| Merchant, Royal, Blacksmith, Inn, Church, Horse Stable | 1 cada |

Armazéns: 33 de 38 slots de item ocupados. Mercados: 33 de 36. Slot é uma chave
distinta de inventário; uma chave persistida com valor zero continua ocupando o
slot conforme a lógica do jogo.

Todos os 14 armazéns têm `minimum_set` ativo. Entre os 33 slots, 23 estão no ou
abaixo do valor de reserva e, por isso, liberam zero para workers; 10 estão acima
da reserva. Isso é **disponibilidade operacional**, não falta, excesso ou
capacidade de armazenamento.

Os registros ambientais (435 árvores, 433 pedras, 25 ninhos e 62 outros) são
nós salvos do mundo. Não representam estoque ou produção e não entram nos cards
de recursos.

## 11. Métricas e alertas permitidos

| Nome | Unidade | Inputs | Fórmula/condição | Interpretação |
|---|---|---|---|---|
| `harvestable_count` | lotes | crop flags | `count(is_harvestable is true)` | colheita disponível agora |
| `capacity_usage` | razão | ocupação/capacidade | `occupied / capacity`, se `0 <= occupied <= capacity` e capacity > 0 | ocupação de limite confirmado |
| `worker_open_slots` | vagas | capacity, occupied | `capacity - occupied`, somente quando `0 <= occupied <= capacity` | capacidade livre; não demanda |
| `worker_available_stock` | unidades | stock, minimum | `stock` se minimum=-1; senão `max(stock-minimum,0)` | liberação a workers |
| `nominal_daily_upkeep` | moeda/dia | modo, conteúdo e buffs | soma documentada, somente se regra/mode conhecidos | custo nominal do snapshot |

Alertas permitidos no snapshot real:

- `warning`: **Capacidade animal cheia** — 52/52, motivo e fonte explícitos;
- `warning`: **Reposição de ração pendente** — 8/13 abaixo de 48;
- `info`: **Reservas protegendo estoque** — 23 slots não liberam unidades a
  workers;
- nenhum alerta de receita negativa, déficit produtivo, “excesso” ou cobertura.

Cada alerta deve conter `severity`, `title`, `detail`, `reason`, `source` e uma
identidade estável para testes.

Capacidade ou ocupação negativa e `occupied > capacity` indicam schema
incompatível/corrompido ou regra não reconhecida. Nesses casos a capacidade fica
indisponível/parcial com razão sanitizada e **não** dispara o alerta normal de
“capacidade cheia”.

## 12. Limites e desconhecidos

- Receita por dia, despesas transacionais históricas e lucro líquido por dia.
- Produção e consumo por dia para culturas, animais, recursos e workers.
- Demanda/necessidade ideal de workers por classe.
- Capacidade máxima em unidades para inventários de ilha e armazéns.
- Cobertura em dias e superávit/déficit de fluxo.
- Idade individual, saúde ou produtividade dos animais; o save auditado agrega
  os animais por prédio.
- Valor econômico de estoque sem política confirmada de preço/contexto.
- Atributos que só existam em runtime e não façam parte do par estável de saves.

Quando um desses valores aparecer no jogo ou em outra versão do schema, ele só
deve entrar no domínio depois de nova evidência, fixture e teste de compatibilidade.

## 13. Requisitos para o parser e o domínio

1. O parser sintático reconhece o formato, não o significado gerencial.
2. Um adaptador allowlisted converte somente cenas/propriedades conhecidas em
   tipos imutáveis.
3. Toda quantidade opcional preserva `None`; zero persistido permanece zero.
4. IDs conhecidos usam catálogo versionado; IDs desconhecidos continuam no
   snapshot com label seguro e confiança desconhecida.
5. O snapshot carrega proveniência por grupo/medida, não caminhos sensíveis.
6. Analytics não lê filesystem e não conhece QML.
7. QML recebe ViewModels/list models prontos; não agrega milhares de registros.
8. Falha parcial deve produzir seção indisponível com razão sanitizada, sem
   invalidar dados independentes confirmados.
