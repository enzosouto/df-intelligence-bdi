# Fontes de Dados — DF Intelligence

> Documento da **Etapa 1 (Descoberta)**. Toda fonte listada como `VALIDADA` foi
> acessada e inspecionada de fato durante a descoberta (requisição HTTP real,
> payload examinado, campos listados). Fontes marcadas como `REJEITADA` também
> foram testadas — e falharam. Nenhum endpoint aqui é suposição.
>
> Data da validação: **2026-09-24**.

---

## 1. Resumo executivo

O Distrito Federal é um caso incomum: ele é, ao mesmo tempo, uma Unidade da
Federação e um único município IBGE (`5300108 — Brasília`). Isso significa que
quase todas as bases federais padrão (SIH, SIA, SINASC, estimativas
populacionais) param na granularidade "DF inteiro" e **não** descem até a
Região Administrativa.

A granularidade de RA só existe em quatro lugares:

1. **IBGE — subdistritos.** No DF, os *subdistritos* do IBGE correspondem às
   Regiões Administrativas. São 35 no Censo 2022. Isso destrava população por
   RA em 2010 e 2022 via API oficial.
2. **SSP-DF — Balanço Criminal por RA.** Planilhas mensais por RA, por natureza
   criminal, de 2014 até o mês corrente.
3. **Dados georreferenciados.** Qualquer base com latitude/longitude pode ser
   atribuída a uma RA por *join* espacial contra a malha oficial das RAs
   (usado aqui para o CNES e para as escolas).
4. **SEEDF — Educacenso recortado para o DF.** A Secretaria de Educação
   republica o Censo Escolar do Inep com a RA e a coordenada de cada escola,
   para todas as redes.

Essa restrição molda todo o modelo de dados do projeto e está documentada em
[`data_quality.md`](./data_quality.md) como limitação de granularidade.

---

## 2. Tabela de fontes

| Fonte | Dataset | URL | Tipo | Período | Granularidade | Atualização | Status |
|---|---|---|---|---|---|---|---|
| IBRAM / ONDA-DF (GDF) | Regiões Administrativas do DF 2025 (geometria) | `https://onda.ibram.df.gov.br/server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0/query` | API ArcGIS REST (GeoJSON) | 2025 | Região Administrativa (35) | Eventual (revisão cartográfica) | **VALIDADA** |
| IBGE | Localidades — subdistritos de Brasília | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios/5300108/subdistritos` | API REST (JSON) | Malha 2022 | Subdistrito = RA (35) | Por Censo | **VALIDADA** |
| IBGE / SIDRA | Agregado 9923 — População residente (Censo 2022) | `https://servicodados.ibge.gov.br/api/v3/agregados/9923/periodos/2022/variaveis/93?localidades=N11[...]` | API REST (JSON) | 2022 | Subdistrito = RA | Decenal | **VALIDADA** |
| IBGE / SIDRA | Agregado 1309 — População residente (Censo 2010) | `https://servicodados.ibge.gov.br/api/v3/agregados/1309/periodos/2010/variaveis/93?localidades=N11[...]` | API REST (JSON) | 2010 | Subdistrito = RA | Decenal | **VALIDADA** |
| IBGE / SIDRA | Agregado 6579 — População residente estimada | `https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/all/variaveis/9324?localidades=N6[5300108]` | API REST (JSON) | 2001–2026 | DF (município) | Anual | **VALIDADA** |
| SSP-DF | Balanço Criminal — Dados por Região Administrativa | `https://www.ssp.df.gov.br/dados-por-regiao-administrativa/` | Página HTML + XLS/XLSX | 2014–2026 | RA × mês × natureza | Mensal | **VALIDADA** |
| Ministério da Saúde / CNES | Estabelecimentos de saúde | `https://apidadosabertos.saude.gov.br/cnes/estabelecimentos?codigo_municipio=530010` | API REST (JSON) | Posição atual | Estabelecimento (lat/lon → RA) | Mensal | **VALIDADA** |
| SEEDF / Inep | Série histórica de unidades escolares e de matrículas (Educacenso) | `https://data.se.df.gov.br/api/3/action/package_show?id=...` | API CKAN + CSV | 2014–2025 | Escola (lat/lon → RA) × ano | Anual | **VALIDADA** |
| IDE-DF / SEDUH (GDF) | Sistema Cicloviário (218), Estação de Metrô (140) | `https://www.geoservicos.ide.df.gov.br/arcgis/rest/services/Publico/IDEDF/FeatureServer/{camada}/query` | API ArcGIS REST (GeoJSON) | Posição atual | Trecho/estação → RA | Eventual | **VALIDADA** |
| Open-Meteo | Historical Weather API (ERA5) | `https://archive-api.open-meteo.com/v1/archive` | API REST (JSON) | 1940–hoje | Ponto (centroide da RA) × dia | Diária (D-5) | **VALIDADA** |
| Portal de Dados Abertos do DF | Catálogo geral | `https://www.dados.df.gov.br/` | SPA Liferay 7.4 | — | — | — | **REJEITADA** |
| Inep | Microdados do Censo Escolar | `https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_{ano}.zip` | ZIP | — | — | — | **REJEITADA** |
| SEMOB-DF | GeoServer (paradas e linhas de ônibus), portal | `https://geoserver.semob.df.gov.br/geoserver/semob/ows` | WFS | — | — | — | **REJEITADA** |
| DETRAN-DF | Acidentes de trânsito (portal e `dados.df.gov.br`) | `https://www.detran.df.gov.br/dados-anuais/` | HTML/CSV | — | — | — | **REJEITADA** |
| SES-DF / InfoSaúde | Dados abertos da saúde | `https://info.saude.df.gov.br/transparencia-e-prestacao-de-contas/dados-abertos/` | Painéis BI | — | — | — | **REJEITADA** |

---

## 3. Detalhamento das fontes validadas

### 3.1 Regiões Administrativas — geometria oficial (IBRAM / ONDA-DF)

* **Órgão:** Instituto do Meio Ambiente e dos Recursos Hídricos do DF (Brasília
  Ambiental), servidor ArcGIS `onda.ibram.df.gov.br`, integrado à IDE-DF.
* **Endpoint testado:**
  ```
  GET /server/rest/services/Territorio/Regioes_Administrativas_DF_2025/MapServer/0/query
      ?where=1=1&outFields=*&returnGeometry=true&f=geojson
  ```
* **Resposta observada:** `FeatureCollection`, **35 features**, ~4,4 MB, WGS84.
* **Campos úteis:** `ra_nome` (nome em caixa alta), `ra_codigo` (`RA-I` …
  `RA-XXXV`), `ra_cira` (código numérico da RA), `ra_path` (link da monografia
  oficial da RA), `st_area(shape)`, `st_length(shape)`.
* **Uso no projeto:** base canônica de `dim_region` — chave, nome oficial,
  código romano, geometria para o mapa, centroide para o clima e polígono para
  o *join* espacial do CNES.
* **Limitações:** o campo `st_area(shape)` vem do CRS projetado do serviço e
  **não** confere com a área oficial publicada. O projeto ignora esse campo e
  calcula a área geodésica a partir do polígono WGS84.

### 3.2 Regiões Administrativas — identificador IBGE

* **Endpoint testado:** `GET /api/v1/localidades/municipios/5300108/subdistritos`
* **Resposta observada:** 35 subdistritos, ids `53001080506` … `53001080546`.
* **Uso:** fornece o `ibge_subdistrict_id`, que é a chave para consultar
  população por RA no SIDRA. É a ponte entre a nomenclatura do GDF
  (`ra_codigo`) e a nomenclatura do IBGE.
* **Divergências de nome conhecidas** (documentadas em
  [`region_mapping.md`](./region_mapping.md)): IBGE usa `Plano Piloto` onde o
  GDF usa `BRASÍLIA` / `PLANO PILOTO`; IBGE usa `Sol Nascente/Pôr do Sol` onde
  o GDF usa `SOL NASCENTE E POR DO SOL`.

### 3.3 População por RA — Censos 2010 e 2022 (IBGE/SIDRA)

* **Censo 2022:** agregado `9923`, variável `93` (População residente), nível
  territorial `N11` (Subdistrito). Confirmado: `N11` está na lista de níveis
  do agregado.
* **Censo 2010:** agregado `1309`, variável `93`, nível `N11`.
* **Exemplo real de resposta** (Plano Piloto):
  `2010 → 209.855 pessoas`; `2022 → 198.697 pessoas`.
* **Atenção — armadilha:** o agregado `4709` (o mais citado em tutoriais) **não**
  aceita `N11`; a API retorna `Parâmetro N11 (Nível territorial) incompatível
  com a tabela`. Foi por isso que `9923` e `1309` foram escolhidos.
* **Uso:** `fact_population` em nível de RA, com dois pontos no tempo (2010 e
  2022), permitindo taxa de crescimento geométrica anualizada e densidade.

### 3.4 População do DF — série anual (IBGE/SIDRA)

* Agregado `6579`, variável `9324` (População residente estimada), nível `N6`,
  localidade `5300108`.
* **Série observada:** 2001–2026, com buracos reais em 2007, 2010, 2022 e 2023
  (anos de Censo / revisão metodológica). Os buracos são preservados como
  ausência de linha, não interpolados.
* **Uso:** KPI de população do DF e gráfico de evolução temporal. Não desce a RA.

### 3.5 Segurança pública — SSP-DF

* **Órgão:** Subsecretaria de Gestão da Informação (SGI/SSP-DF). É o único
  órgão com competência legal para divulgar estatística criminal do DF.
* **Como os dados são publicados:** uma página HTML lista, por RA e por ano,
  um par de arquivos (PDF e XLS/XLSX). Não há API. Os *slugs* do Liferay são
  opacos (ex.: `/documents/d/ssp/20_aguas-claras-84-xlsx`) e **se repetem entre
  anos diferentes** na marcação da página.
* **Estratégia de ingestão adotada:** o ano **não** é inferido do link nem do
  texto da página. Ele é lido de dentro do arquivo (célula do cabeçalho e/ou
  nome da aba). Assim, links duplicados ou trocados pelo portal não corrompem o
  dado — apenas geram um *upsert* redundante.
* **Estrutura da planilha (verificada em 2 arquivos reais):**

  | Linha | Conteúdo |
  |---|---|
  | 0–2 | Cabeçalho institucional (GDF / SSP / SGI) |
  | 3 | `BALANÇO CRIMINAL` |
  | 4 | `RA XX - ÁGUAS CLARAS` ← código romano + nome da RA |
  | 5 | `COMPARATIVO MENSAL <ano> ...` |
  | 6 | `EIXOS INDICADORES` \| `NATUREZA` \| `TOTAL` \| `<ano>` |
  | 7 | (vazio) \| (vazio) \| (vazio) \| `JAN` … `DEZ` |
  | 8+ | eixo, natureza, total, 12 valores mensais |

* **Eixos observados:** `1. C.V.L.I.` (Crimes Violentos Letais Intencionais),
  `2. C.C.P.` (Crimes Contra o Patrimônio), `3. OUTROS CRIMES`,
  `4. PRODUTIVIDADE POLICIAL`. Linhas de subtotal (`1.TOTAL C.V.L.I.`,
  `2. TOTAL C.C.P.`, `TOTAL CRIMES (CVLI + CCP)`) existem no arquivo e são
  **descartadas** na ingestão para evitar dupla contagem.
* **Naturezas observadas:** `HOMICÍDIO`, `LATROCÍNIO`, `LESÃO CORPORAL SEG. DE
  MORTE`, `ROUBO A TRANSEUNTE`, `ROUBO DE VEÍCULO`, `ROUBO EM COLETIVO`,
  `ROUBO EM COMÉRCIO`, `ROUBO EM RESIDÊNCIA`, `FURTO EM VEÍCULO`, `TENTATIVA DE
  HOMICÍDIO`, `TENTATIVA DE LATROCÍNIO`, `ESTUPRO`, `ESTUPRO DE VULNERÁVEL`,
  `FURTO A TRANSEUNTE`, `TRÁFICO DE DROGAS` etc. O conjunto **varia entre anos**
  (ex.: `ESTUPRO DE VULNERÁVEL` não existe nos arquivos de 2014–2018), o que é
  tratado como esquema evolutivo, não como erro.
* **Limitação metodológica obrigatória:** são registros administrativos de
  ocorrência policial, não a totalidade dos crimes. Subnotificação ("cifra
  oculta") existe e varia entre regiões e naturezas. Comparações entre RAs
  devem ser normalizadas por população.

### 3.6 Saúde — CNES (Ministério da Saúde)

* **Endpoint testado:**
  `GET https://apidadosabertos.saude.gov.br/cnes/estabelecimentos?codigo_municipio=530010&limit=20&offset=0`
* **Resposta observada:** objeto `{"estabelecimentos": [...]}` com 37 campos por
  registro, incluindo `codigo_cnes`, `nome_fantasia`, `codigo_tipo_unidade`,
  `descricao_esfera_administrativa`, `bairro_estabelecimento`,
  `latitude_estabelecimento_decimo_grau`,
  `longitude_estabelecimento_decimo_grau`,
  `estabelecimento_possui_centro_cirurgico`,
  `estabelecimento_possui_atendimento_hospitalar`,
  `estabelecimento_faz_atendimento_ambulatorial_sus`, `data_atualizacao`.
* **Paginação:** `limit` + `offset`. A API não devolve total; a ingestão pagina
  até receber página vazia.
* **Por que esta fonte e não SIA/SIH:** o CNES é a **única** base de saúde
  federal testada que carrega coordenada geográfica por registro e, portanto, a
  única que pode ser atribuída a uma Região Administrativa. SIA/SIH/SINASC
  param no município `530010` (o DF inteiro).
* **Uso:** `fact_health` como indicador de **infraestrutura** de saúde por RA
  (estabelecimentos por tipo, por esfera, por 10 mil habitantes). Não é
  indicador de *produção* (atendimentos realizados) — essa limitação está
  explícita na interface e em `data_quality.md`.
* **Limitações:** cerca de 1–3% dos registros trazem coordenada ausente ou
  truncada (ex.: `-15.78, -47.93` exatos, claramente o centroide de Brasília).
  Esses casos caem na RA do centroide e são marcados com
  `geocode_quality = 'LOW'`.

### 3.7 Clima — Open-Meteo

* **Endpoint testado:**
  `GET https://archive-api.open-meteo.com/v1/archive?latitude=-15.78&longitude=-47.93&start_date=...&end_date=...&daily=...&timezone=America/Sao_Paulo`
* **Resposta observada:** JSON com `daily.time` e um array por variável.
* **Variáveis usadas:** `temperature_2m_max`, `temperature_2m_min`,
  `temperature_2m_mean`, `precipitation_sum`, `relative_humidity_2m_mean`,
  `wind_speed_10m_max`.
* **Uso:** `fact_weather`, uma série diária por centroide de RA.
* **Declaração obrigatória:** **esta NÃO é uma fonte governamental do Distrito
  Federal.** Open-Meteo é um serviço aberto europeu que serve reanálise ERA5
  (ECMWF). Os valores são de *modelo de reanálise* interpolado para o ponto
  consultado, **não** leitura de estação meteorológica do INMET. Como as RAs do
  DF estão dentro de poucas células de grade do ERA5, a variação entre RAs é
  pequena e deve ser lida como "microclima aproximado", não como medição local.
* **Sem chave de API, sem custo**, uso não comercial livre. Latência de ~5 dias
  no arquivo histórico.

### 3.8 Educação — Educacenso (SEEDF / Inep)

* **Portal:** `https://data.se.df.gov.br`, CKAN da Secretaria de Educação do
  DF, com API (`/api/3/action/package_show`). Não confundir com
  `dados.df.gov.br`, que perdeu a API (4.1).
* **Conjuntos usados:**
  * `relacao-de-unidades-escolares-abrangendo-todas-as-redes-de-ensino-do-distrito-federal`
    — um CSV por ano, 2014–2025, ~1.150–1.290 escolas por ano, com rede, RA,
    endereço e coordenada (até 2024).
  * `quantidade-de-matriculas-das-modalidades-de-ensino-abrangendo-todas-as-redes-de-ensino-do-df`
    — um CSV por ano (~20 MB), grão escola × idade × sexo × cor/raça
    (~75–85 mil linhas), com matrículas por etapa.
* **Testado:** download de todos os 24 CSVs a partir do runner do GitHub
  Actions; cabeçalhos, pares código/nome de RA e totais conferidos ano a ano.
* **Redes:** 1 federal, 2 SEEDF, 3 particular conveniada, 4 particular, 5
  pública não vinculada à SEEDF.
* **Uso:** `fct_education_enrollment` (escola × ano) e
  `mart_education_yearly` (RA × ano e DF × ano).
* **Limitações:** a matrícula é contada onde a escola fica, não onde o aluno
  mora; em 8 dos 12 anos o arquivo de matrículas omite escolas ativas; 2024 não publica total;
  os códigos de RA 34/35 vêm invertidos. Detalhes e tratamento em
  [`data_quality.md`](./data_quality.md), seções 2.13 a 2.18.

### 3.9 Mobilidade — IDE-DF (SEDUH)

* **Serviço:** `Publico/IDEDF/FeatureServer`, 240 camadas. Responde em ~1 s a
  partir do runner do GitHub. Paginação de 1.000 registros, ordenada por
  `objectid`; geometria pedida em `outSR=4326` (a nativa é SIRGAS 2000 /
  UTM 23S, EPSG:31983).
* **Camadas usadas:**
  * **218 Sistema Cicloviário** — 2.293 trechos, 671,9 km, com RA declarada,
    km, ano de construção (2002–2023, todos preenchidos) e tipologia
    (1.764 ciclovias, 259 ciclofaixas, 201 calçadas compartilhadas, 69 outros).
  * **140 Estação de Metrô** — 29 estações: 27 em operação, 2 em construção
    (Onoyama e 104 Sul).
  * **127 Estações e Terminais** — **não usada**. As 17 "ESTAÇÃO METRÔ"
    repetem a camada 140, as 5 "ESTAÇÃO BRT" vêm sem nome e os 21
    "TERMINAIS DFTRANS" omitem a Rodoviária do Plano Piloto.
* **Uso:** `fct_mobility_bikeway` (trecho × RA, recorte geodésico),
  `fct_mobility_station`, `mart_mobility_region`,
  `mart_mobility_bikeway_yearly`.
* **Limitações:** retrato do presente, sem data de atualização publicada. A
  série por ano de construção descreve os trechos atuais, não a malha histórica.
  Mede infraestrutura, não uso nem qualidade. Detalhes em
  [`data_quality.md`](./data_quality.md), 2.20 a 2.22.

---

## 4. Fontes rejeitadas (e por quê)

### 4.1 Portal de Dados Abertos do DF — `dados.df.gov.br`

Historicamente o portal rodava **CKAN**, e praticamente toda a documentação e
todos os tutoriais na internet ainda apontam para
`https://dados.df.gov.br/api/3/action/...`.

**Esse endpoint não existe mais.** Testes realizados:

| Requisição | Resultado real |
|---|---|
| `GET /api/3/action/status_show` | `{"message":"The requested resource [/api/3/action/status_show] is not available","statusCode":404}` |
| `GET /api/3/action/package_list` | 404, mesma mensagem |
| `GET /api/dataset`, `/api/datasets`, `/api/v1/dataset`, `/api/package_search`, `/api/search` | 404, mesma mensagem |
| `GET /` | HTML do **Liferay 7.4** (`importmap` com `@clayui/*`) |
| `GET /dataset/exames-producao-ambulatorial` | redireciona para `/dataset#/exames-producao-ambulatorial` — roteamento por *hash*, ou seja, SPA |

O portal foi migrado de CKAN para uma SPA sobre Liferay sem API pública
documentada. Os *datasets* citados na busca (ex.: "Exames - Produção
Ambulatorial") existem na interface, mas não há contrato de máquina estável
para eles. **Decisão: não depender dessa fonte.** Um raspador de SPA quebraria
no primeiro deploy do portal e violaria o princípio de "não inventar
endpoints".

> Se/quando o GDF publicar uma API para o novo portal, os *datasets* de saúde
> por RA passam a ser a melhor fonte para `fact_health` de produção, e a
> substituição está prevista em [`architecture.md`](./architecture.md).

### 4.2 SES-DF / InfoSaúde

`info.saude.df.gov.br` publica painéis interativos (dengue, SIA, vacinas, SAMU,
Lacen) e documentos PDF. A página de Dados Abertos foi inspecionada e **não**
expõe links diretos para CSV/XLSX — ela delega para `dados.df.gov.br`, que caiu
no caso 4.1. Além disso, a SES-DF agrega por **Região de Saúde** (7 regiões), e
não por Região Administrativa (35), o que exigiria um mapeamento N:1 lossy.

### 4.3 INMET

Considerada para clima. A API de estações (`apitempo.inmet.gov.br`) oferece
dados horários por estação, mas o DF tem poucas estações automáticas, todas
concentradas na porção central. Atribuir uma estação a cada uma das 35 RAs
produziria uma falsa granularidade. Open-Meteo/ERA5, apesar de não ser
governamental brasileiro, é mais honesto aqui porque a interpolação é explícita
e documentada. **Anotado como alternativa futura** para validação cruzada da
série de Brasília.

### 4.3.1 Inep — microdados do Censo Escolar

`download.inep.gov.br` respondeu, a partir do runner do GitHub Actions, com
`ConnectionResetError` (2023) e `CERTIFICATE_VERIFY_FAILED: unable to get local
issuer certificate` (2024, 2025) — cadeia TLS incompleta. Desligar a
verificação de certificado não é opção. Além disso, os microdados nacionais
não trazem a RA. A SEEDF (3.8) republica o mesmo censo já recortado para o DF.

### 4.3.2 SEMOB-DF e DETRAN-DF

Testados a partir do runner do GitHub Actions (setembro de 2026):

* `geoserver.semob.df.gov.br` (WFS de paradas e linhas): `ConnectTimeout` —
  a conexão nem é aceita.
* `www.semob.df.gov.br`, `www.detran.df.gov.br/dados-anuais/` e
  `www.dados.df.gov.br/dataset/...` (acidentes com vítimas fatais):
  `ReadTimeout` mesmo com 30 s de espera.

O padrão (IDE-DF, SEEDF e IBRAM respondem na hora; estes nem abrem) sugere
bloqueio de IP de fora do Brasil, mas isso não foi confirmado. Enquanto o
pipeline roda no GitHub, essas fontes não são viáveis. Acidentes de trânsito
por RA ficam como próximo passo para execução local.

### 4.4 Kaggle e agregadores não oficiais

Não utilizados, conforme regra do projeto. Toda RA, todo número de população,
toda ocorrência criminal e todo estabelecimento de saúde vem de órgão oficial.

---

## 5. Como reexecutar a validação

```bash
python -m ingestion.validate_sources
```

O comando faz uma requisição real a cada fonte `VALIDADA`, confere o formato da
resposta e imprime um relatório. É o mesmo comando executado pelo GitHub
Actions antes de rodar a ingestão — se uma fonte sair do ar ou mudar de
contrato, o pipeline falha cedo e alto, em vez de gravar lixo no banco.
