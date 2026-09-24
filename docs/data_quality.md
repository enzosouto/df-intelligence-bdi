# Qualidade dos dados

Este documento descreve o que é verificado, onde, e — principalmente — quais
problemas reais foram encontrados nas fontes e como o projeto lida com cada um.

Nenhum problema listado aqui é hipotético. Todos apareceram durante a
construção do pipeline.

---

## 1. Onde a verificação acontece

| Estágio | Ferramenta | Quando falha |
|---|---|---|
| Antes da ingestão | `python -m ingestion.validate_sources` | Fonte fora do ar ou com contrato alterado |
| Durante a ingestão | `meta.data_quality_check` | Registra achado; `ERROR` derruba o pipeline no CI |
| Após a transformação | `dbt build` (105 testes) | Teste falho interrompe o build |
| Sobre o código | `pytest` (40 testes) | Regressão em regra de parsing ou de atribuição |

---

## 2. Problemas reais encontrados nas fontes

### 2.1 O portal de dados abertos do DF perdeu a API

`https://dados.df.gov.br/api/3/action/*` responde 404. O portal migrou de CKAN
para uma SPA sobre Liferay 7.4 sem API pública documentada, embora praticamente
toda a documentação na internet ainda aponte para os endpoints CKAN.

**Tratamento:** fonte marcada como `REJEITADA` em
[`data_sources.md`](./data_sources.md). O projeto não raspa a SPA — quebraria no
primeiro deploy do portal e violaria o princípio de não inventar endpoint.

### 2.2 A SSP-DF publica o mesmo link para anos diferentes

Na página de dados por Região Administrativa, 34 pares (RA, ano) apontam para um
arquivo que pertence a outro ano. Consequência: **a SSP-DF não publica o balanço
de 2024 para 15 das 35 RAs** — os links desse ano existem, mas levam a arquivos
de outros anos.

**Tratamento:**

* O ano e a RA são lidos de **dentro** da planilha (célula do cabeçalho e nome
  da aba), nunca do link. Link trocado vira download redundante, não dado
  errado.
* A lacuna é medida e publicada: `mart_data_coverage.security_missing_years`,
  o insight `COVERAGE_2024_GAP` e a página *Fontes & Qualidade*.
* Na interface, os meses ausentes aparecem como **quebra na linha**, nunca como
  zero.

### 2.3 Arquivos da SSP-DF discordam entre si

1.325 chaves (RA × ano × mês × natureza), cerca de 1,9% do total, têm valores
diferentes entre o agregado histórico e o arquivo anual específico. É
republicação da SSP, não erro de leitura.

**Tratamento:** regra determinística — **o arquivo anual específico vence o
agregado histórico**, porque é o que a SSP mantém e revisa. Os conflitos ficam
registrados em `meta.data_quality_check` sob
`security.value_conflicts_between_files`, com limiar de alerta em 2%.

### 2.4 A mesma natureza criminal mudou de eixo ao longo dos anos

`ROUBO EM RESIDÊNCIA` estava em "OUTROS CRIMES" até 2015 e passou para "C.C.P. —
Crimes Contra o Patrimônio" a partir de 2016. `TENTATIVA DE LATROCÍNIO` aparece
com e sem acento conforme o ano.

**Tratamento:** o grão é a **natureza**, não o eixo. O seed
`dbt/seeds/security_nature_map.csv` colapsa as variações de grafia numa chave
estável e fixa a categoria canônica. O eixo original fica preservado em
`axis_source` para auditoria. Se a série de cada categoria usasse o eixo bruto,
ela saltaria por mudança de rótulo, não por mudança de realidade.

**Teste:** `assert_security_natures_are_mapped.sql` falha o pipeline se a SSP
publicar uma natureza que o projeto não conhece — assim um tipo criminal novo é
notado, não silenciado.

### 2.5 O CNES preenche coordenada com o centro de Brasília

274 estabelecimentos compartilham exatamente duas coordenadas — 232 deles em
`(-15.78, -47.93)`, o centro genérico da cidade. Não são endereços; são valor
padrão.

**Impacto se ignorado:** esses registros se empilhavam na RA onde a coordenada
falsa cai. Cruzeiro, com ~25 mil habitantes, aparecia com **99,1
estabelecimentos por 10 mil habitantes** — um artefato puro. Depois da
correção: **9,7**.

**Tratamento:** coordenadas compartilhadas por 20 ou mais estabelecimentos são
detectadas **pelos próprios dados** (contagem, não lista fixa) e tratadas como
ausentes. Esses registros passam para a inferência por bairro.

**Teste de regressão:**
`test_health_facilities_are_never_dumped_into_a_single_region` falha se uma
única RA concentrar mais de 65% da rede.

### 2.6 31% dos registros do CNES não têm coordenada

**Tratamento — sem adivinhação.** Para cada bairro, olhamos onde caíram os
estabelecimentos **daquele bairro** que têm coordenada válida. O bairro herda
essa RA apenas se houver evidência suficiente: pelo menos 3 estabelecimentos
geolocalizados e 80% de concordância entre eles.

Resultado atual: 1.414 por coordenada, 895 por bairro, 151 sem região. Os 151
**não são distribuídos** entre as RAs — aparecem como `region_id` nulo em
`/api/health` e são contados como `UNRESOLVED`.

### 2.7 A esfera administrativa do CNES não separa público de privado

`descricao_esfera_administrativa` informa quem **gerencia** o estabelecimento no
SUS. No DF vale `ESTADUAL` para 2.407 dos 2.460 registros — inclusive para
consultórios odontológicos particulares.

**Impacto se ignorado:** 98% da rede seria classificada como pública.

**Tratamento:** o setor vem do primeiro dígito da **natureza jurídica** (tabela
CONCLA/IBGE): `1` administração pública, `2` entidades empresariais, `3`
entidades sem fins lucrativos, `4` pessoas físicas. Resultado atual: 2.336
privados, 88 públicos, 36 sem fins lucrativos — compatível com a realidade.

### 2.8 Os booleanos de serviço do CNES são quase todos falsos

`estabelecimento_possui_atendimento_ambulatorial` é verdadeiro em apenas 21 de
2.460 registros. Usá-los para agrupar a rede jogava 2.400 estabelecimentos em
"OUTROS".

**Tratamento:** o agrupamento sai da **descrição oficial do tipo de unidade**,
obtida da própria API (`/cnes/tipounidades`), e não de uma lista de códigos
digitada à mão.

### 2.9 O IBGE não publica duas RAs no Censo 2022

Arapoanga e Água Quente retornam `"..."` (não disponível). O IBGE conta a
população delas dentro das RAs de origem.

**Verificação que confirma a interpretação:** a soma das 33 RAs publicadas é
**2.817.381**, exatamente o total do DF no Censo 2022. Nada foi perdido nem
contado duas vezes.

**Tratamento:** população fica `NULL` (nunca zero), a ausência é publicada em
`mart_data_coverage` e o mapa mostra essas RAs hachuradas.

### 2.10 Em 2010 o IBGE reconhecia 19 subdistritos, não 35

**Impacto se ignorado:** Ceilândia apareceria com queda de 28,7% entre os
Censos. Não é perda populacional — é o Sol Nascente/Pôr do Sol (101.866
habitantes) tendo sido separado dela. O mesmo vale para Taguatinga, Sobradinho,
Cruzeiro e outras.

**Tratamento:** ver `int_region_lineage`. A RA de origem de cada RA nova é
inferida pela fronteira compartilhada mais longa com uma RA que existia em 2010,
calculada geodesicamente. **É heurística, e está rotulada como tal.** Seu único
efeito é *excluir* RAs da métrica de crescimento — ela nunca cria um número.

Resultado: 12 das 35 RAs têm crescimento publicado. As outras 23 mostram os dois
Censos lado a lado com a explicação do porquê da ausência de comparação.

### 2.11 O ano corrente da SSP traz zeros nos meses que não aconteceram

**Tratamento:** no arquivo do ano corrente, a série é truncada no último mês com
qualquer ocorrência registrada. Efeito colateral aceito e documentado: um mês
realmente zerado no fim do ano corrente, numa RA muito pequena, seria
descartado.

**Teste:** `assert_no_future_security_months.sql`.

### 2.12 A cota gratuita do Open-Meteo não cobre 35 pontos × 8 anos

A primeira execução recebeu `429 Too Many Requests` na metade.

**Tratamento:** a grade do ERA5 é mais grossa que uma RA. As RAs são agrupadas
em células de 0,1° (22 células para 35 RAs) e cada célula é consultada uma vez.
RAs na mesma célula recebem série idêntica — que é o que a fonte tem a dizer —
e `regions_sharing_cell` declara isso na API e na interface.

### 2.13 O esquema do Educacenso muda de ano para ano

Nos arquivos da SEEDF (`data.se.df.gov.br`), a mesma informação troca de nome:
`CO_RA` → `RA`, `CO_ENTIDADE` → `Código INEP`, `ESC_EF_TOTAL` (até 2019) →
`MAT_EF_TOTAL` → `Ensino fundamental - TOTAL` (2025), `NU_LATITUDE` →
`LATITUDE` (2019). O arquivo de 2025 ainda traz uma **linha-banner acima do
cabeçalho** ("EXTRAÍDO DO MICRODADOS DE MATRÍCULAS PUBLICADO").

**Tratamento:** toda coluna é localizada pelo nome normalizado (sem acento,
maiúsculo, `/` como espaço), com lista de apelidos por campo. O cabeçalho é a
primeira linha que contém a coluna de ano. O ano vem de `NU_ANO_CENSO`, nunca
do nome do recurso no CKAN. Coluna obrigatória ausente derruba a ingestão com a
lista do que sumiu.

### 2.14 Milhar dentro de CSV separado por vírgula

Em 2025, `BAS = "2,657"` para o Colégio Militar: são 2.657 matrículas, não
2,657. Em 2014, o marcador de nulo é o texto `NUL.L`.

**Tratamento:** `parse_count` aceita só inteiro puro ou milhar bem formado
(`\d{1,3}([.,]\d{3})+`). Qualquer outra coisa (`12.5`, `1,2`) **levanta
erro** — adivinhar entre decimal e milhar foi o que fez `12.0` virar `120` no
parser da SSP (2.3). `NUL.L` e vazio viram `NULL`.

### 2.15 Os códigos de RA 34 e 35 da SEEDF estão invertidos

Pela numeração oficial, RA XXXIV é Arapoanga e RA XXXV é Água Quente. Na
SEEDF, as mesmas escolas aparecem sempre sob o mesmo código, mas:

| Escola (INEP) | Coordenada | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| EC 01 DO ARAPOANGA (53047028) | −15,640 / −47,636 | 35 ARAPOANGA | 35 ARAPOANGA | 35 **AGUA QUENTE** |
| EC DE AGUA QUENTE (53020154) | −15,947 / −48,228 | — | 34 AGUA QUENTE | 34 **ARAPOANGA** |

O código está invertido em todos os anos; o nome passou a vir invertido em 2025.

**Tratamento:** a RA de cada escola vem da **coordenada**, por
point-in-polygon contra a malha oficial (a mesma técnica da saúde). A
coordenada mais recente do código INEP vale para todos os anos — o arquivo de
2025 não traz coordenada. Sem coordenada, a RA declarada só é aceita se código
**e** nome apontam para a mesma RA; senão a escola fica `UNRESOLVED`. Teste de
regressão com as duas escolas acima:
`assert_education_ra_34_35_follow_coordinates`.

Efeito colateral útil: como a escola é um ponto, a série por RA fica em
**território constante** (malha de 2025), inclusive para anos anteriores à
criação de Sol Nascente, Arniqueira, Arapoanga e Água Quente — o oposto da
população por RA (2.10).

### 2.16 O arquivo de matrículas de 2023 está incompleto

| Ano | Escolas no arquivo | Matrículas | Creche |
|---|---|---|---|
| 2022 | 1.154 | 619.635 | 32.972 |
| **2023** | **600** | **385.801** | **177** |
| 2025 | 1.332 | 620.297 | 42.582 |

O cadastro de escolas de 2023 tem 1.264 unidades. Somado ingenuamente, o
arquivo fabricaria uma queda de 38% nas matrículas do DF.

**Tratamento:** sem exceção escrita à mão. `mart_education_coverage` mede,
para todo ano e rede, a fração das escolas do cadastro presentes no arquivo de
matrículas. Abaixo de 95%, as matrículas do ano saem nulas e a linha do gráfico
quebra. O número de escolas continua publicado, porque o cadastro é completo.

### 2.17 2024 não publica o total de matrículas

O arquivo de 2024 tem 63 colunas: as etapas estão lá, a coluna de total não.

**Tratamento:** o total fica `NULL`. A soma das etapas **não** o substitui,
porque a identidade `creche + pré + fundamental + médio + profissional + EJA +
especial exclusiva = total` só fecha exatamente em 2023 e 2025; de 2014 a 2022
as etapas somam entre 99,6% e 99,96% do total. Essa folga medida virou teste
(`assert_education_stages_reconcile_with_total`).

### 2.18 O ensino médio "cai" 11% em 2025 por reclassificação

`EM` passa de 100.541 (2024) para 89.098 (2025), enquanto o Ensino Médio
Integrado sobe de 3.928 para 15.917. Médio + integrado: 104.469 → 105.015.

**Tratamento:** o indicador publicado é `high_school_all` (médio + integrado).
Teste de integração verifica que a série não varia mais de 5% entre 2024 e
2025.

### 2.19 O INEP não entrega os microdados para fora

`download.inep.gov.br` responde com cadeia TLS incompleta e reset de conexão a
partir dos runners do GitHub. A SEEDF republica o mesmo Censo Escolar recortado
para o DF, com a RA — por isso é a fonte usada.

---

## 3. Testes do dbt

105 testes no total. Os que carregam mais informação:

### 3.1 Reconciliação com o total oficial do IBGE

`assert_population_sums_match_df_total.sql`

A soma da população das RAs tem que bater **exatamente** com o total publicado
pelo IBGE para o mesmo Censo (2010: 2.570.160; 2022: 2.817.381). É o teste mais
valioso do projeto: valida de uma vez o mapeamento RA↔subdistrito, a ingestão e
a ausência de duplicata.

### 3.2 Plausibilidade das medidas geográficas

`assert_region_measures_are_plausible.sql`

Área entre 0,5 e 2.000 km², centroide dentro do retângulo do DF, população entre
0 e 1 milhão, e **soma das áreas entre 5.000 e 6.500 km²** (o DF tem ~5.760).
Rede de segurança contra o erro clássico de trocar latitude por longitude ou ler
área em m² como km².

### 3.3 Consistência das chaves de região

`assert_region_keys_are_consistent.sql`

Falha se um subdistrito IBGE for usado por mais de uma RA, se uma RA da malha do
GDF não tiver mapeamento, ou se o mapeamento apontar para RA inexistente.

### 3.4 Unicidade do grão

`assert_security_grain_is_unique.sql` e `assert_weather_grain_is_unique.sql`

Duplicata no fato significaria dupla contagem em todos os agregados acima.

### 3.5 Testes genéricos

| Tipo | Onde |
|---|---|
| `unique` | `dim_region.region_id`, `region_number`, `region_name`, `ibge_subdistrict_id`; `fct_health_facility.cnes_code`; `mart_insights.insight_id` |
| `not_null` | todas as chaves e medidas de todos os fatos |
| `relationships` | `fct_*.region_id → dim_region`; `fct_security_monthly.nature_key → dim_category`; `mart_insights.source_id → dim_source` |
| `accepted_values` | `metric_type`, `sector`, `service_group`, `region_assignment`, `season`, `reference_month`, `reference_year` dos Censos, `status` do pipeline |

---

## 4. Testes de código (`pytest`)

40 testes. Alguns exemplos do que eles impedem:

* **`test_count_parsing`** — encontrou um bug real: uma célula lida como `12.0`
  virava `120`, porque a limpeza de separador de milhar pt-BR removia o ponto
  decimal. Hoje números do Excel são usados como estão e a limpeza só vale para
  texto.
* **`test_subtotal_rows_are_discarded`** — as planilhas da SSP contêm linhas
  `1.TOTAL C.V.L.I.` e `TOTAL CRIMES (CVLI + CCP)`. Somá-las dobraria a
  contagem.
* **`test_future_months_of_current_year_are_dropped`** — garante a truncagem
  descrita em 2.11.
* **`test_sidra_missing_markers_become_null_not_zero`** — `...`, `-` e `X` do
  SIDRA viram `NULL`, não zero.
* **`test_placeholder_coordinate_is_treated_as_missing_not_located`** —
  regressão do problema 2.5.
* **`test_growth_is_only_published_when_comparable`** — percorre todas as RAs e
  falha se alguma não comparável publicar variação populacional.
* **`test_insights_never_claim_causation`** — varre o texto de todos os insights
  procurando "causou", "provocou", "por causa de", "resultou em". Regra
  editorial verificada por máquina.

---

## 5. Limitações que nenhum teste resolve

Estas são propriedades das fontes, não defeitos do pipeline. Estão declaradas
na API (`caveat` em `/api/sources` e `/api/insights`) e na interface.

| Limitação | Consequência para a leitura |
|---|---|
| Dados de segurança são registros policiais | Não medem o crime, medem o **registro** do crime. Subnotificação existe e varia entre regiões e naturezas. |
| CVLI é o menos subnotificado | Envolve morte e perícia — por isso é o indicador de segurança mais confiável para comparar regiões. |
| Taxas usam população residente | RAs com muito fluxo diário de não residentes (SIA, Plano Piloto) têm taxa inflada: o denominador conta só quem mora. |
| Denominador é sempre o Censo 2022 | Taxas de anos distantes de 2022 carregam esse denominador. `population_reference_year` acompanha o número. |
| CNES mede infraestrutura, não produção | "46 estabelecimentos" não diz quantos atendimentos foram feitos. |
| Matrícula é contada onde a escola fica | Não mede a escolarização dos moradores da RA. Por isso não há taxa de matrícula por habitante. |
| Oferta instalada ≠ acesso | Moradores se deslocam entre RAs para se tratar. |
| Clima é reanálise, não medição | Open-Meteo/ERA5 é fonte externa e não governamental, com resolução mais grossa que uma RA. |
| População por RA só existe em 2010 e 2022 | Não há série anual por Região Administrativa. |
| Correlação não implica causalidade | Nenhum insight afirma causa. A regra é verificada por teste automatizado. |

---

## 6. Como inspecionar

```bash
# Checagens da última execução de cada fonte
docker exec dfi-postgres psql -U df -d df_intelligence -c "
  select source_key, check_name, severity, passed, left(observed, 90) as observed
  from meta.data_quality_check c
  join meta.ingestion_run r using (run_id)
  order by c.check_id desc limit 20;"

# Estado do pipeline
curl -s localhost:8000/api/pipeline | python -m json.tool

# Cobertura por região
curl -s localhost:8000/api/coverage | python -m json.tool
```
