# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Adicionado
- **Domínio de educação** (Educacenso via SEEDF, `data.se.df.gov.br`, todas as
  redes, 2014–2025): `ingestion/education.py`, `fct_education_enrollment`,
  `mart_education_yearly`, `mart_education_coverage`, endpoints
  `/api/education` e `/api/education/coverage`, seção na página de região,
  três insights e a fonte `SEEDF_EDUCACENSO` no catálogo.
- 22 testes de parser (`tests/test_education_parser.py`), 5 testes singulares
  no dbt e 4 testes de integração, cada um codificando um achado dos arquivos
  reais (ver `docs/data_quality.md`, 2.13–2.19).

### Decisões de fonte (educação)
- **RA pela coordenada, não pela declaração.** Os códigos 34/35 da SEEDF estão
  invertidos em relação à numeração oficial em todos os anos, e o nome veio
  trocado em 2025. As escolas do Arapoanga seriam contadas em Água Quente.
- **2023 não publicado.** O arquivo de matrículas cobre 600 das 1.264 escolas
  do cadastro (385.801 matrículas contra ~620 mil nos anos vizinhos). Sem
  tratamento: "queda de 38%".
- **2024 sem total.** A fonte não publica a coluna; a soma das etapas só fecha
  exatamente em 2023 e 2025, então não a substitui.
- **Ensino médio = médio + integrado.** Sozinho, o médio "cai" 11% em 2025
  (100.541 → 89.098) por reclassificação; somado ao integrado fica estável
  (104.469 → 105.015).
- **Microdados do Inep rejeitados:** cadeia TLS incompleta a partir do runner
  do GitHub e ausência de RA.

### Alterado
- `load_region_index` passou de `ingestion/health.py` para
  `ingestion/common.py`: saúde e educação usam o mesmo índice espacial.

### Corrigido
- **Imagem do pipeline** (`ingestion/Dockerfile`): removido o `apt-get install
  bash postgresql-client`. Nenhum script usa `psql` (a conferência final é via
  `psycopg2`) e a `python:3.12-slim` já traz bash. Um passo de rede a menos
  para quebrar o build. `docker compose run --rm pipeline` testado.
- **`run_pipeline.sh --skip-ingestion`** exigia as 7 fontes no ar, porque a
  validação rodava antes de checar a flag. Remodelar o que já está no banco
  não depende de rede: agora a validação só roda quando há ingestão.
- **CI — ingestão em todo push na `main`:** o `if:` do job contradizia o
  comentário e o README ("roda todo dia 5"). Agora só roda no agendamento ou
  via `workflow_dispatch` com `run_ingestion: true` (o input existia e não era
  lido).
- **CI — teste de integração da API** instalava `fastapi`/`uvicorn` sem versão;
  passa a usar `api/requirements.txt`, as mesmas versões da imagem.
- **CI — job `docker`** passa a construir também a imagem do pipeline.

## [1.0.0] — 2026-09-24

Primeira versão funcional: pipeline completo de fontes públicas reais até a
interface, com 35 Regiões Administrativas, 4 domínios e 105 testes de qualidade.

### Adicionado

**Ingestão**
- Módulos para regiões, população, segurança, saúde e clima, todos idempotentes
  (`INSERT ... ON CONFLICT DO UPDATE` sobre chave natural).
- `ingestion.validate_sources`: requisição real a cada fonte antes do pipeline,
  para falhar cedo se alguma mudar de contrato.
- Sessão HTTP com retry exponencial, throttle e User-Agent de navegador — o
  Liferay da SSP-DF devolve desafio JavaScript para clientes identificados como
  script.
- Persistência do payload bruto em `data/raw/<fonte>/<data>/` para auditoria.
- Registro de execução e de checagens de qualidade em `meta`.

**Modelagem (dbt)**
- 24 modelos em `staging` → `intermediate` → `marts`.
- Dimensões `dim_region`, `dim_date`, `dim_category`, `dim_source`; fatos
  `fct_population`, `fct_population_df`, `fct_security_monthly`,
  `fct_health_facility`, `fct_weather_daily`; agregados `mart_*`.
- Seeds versionados para o mapeamento RA↔IBGE, a taxonomia criminal e o
  catálogo de fontes.
- 105 testes, incluindo reconciliação da soma populacional das RAs com o total
  oficial do IBGE (2010: 2.570.160; 2022: 2.817.381).

**API**
- FastAPI com 20 endpoints e documentação automática em `/docs`.
- Campos que podem enganar carregam a ressalva no próprio schema.
- `/api/coverage` e `/api/pipeline` expõem cobertura e estado do pipeline.

**Frontend**
- Vue 3 + TypeScript + Tailwind, dark mode, responsivo.
- Mapa das RAs em SVG renderizado do GeoJSON, sem biblioteca de mapas.
- Gráficos em SVG com quebra de linha em lacuna e marcação de período parcial.
- Páginas: dashboard, região, insights, fontes & qualidade.

**Infraestrutura**
- `docker compose up -d` sobe Postgres, API e frontend; nginx faz proxy de
  `/api` para eliminar CORS.
- `scripts/setup.sh` e `scripts/run_pipeline.sh`.
- GitHub Actions: testes unitários e validação de fontes em todo push; pipeline
  completo mensal ou sob demanda.

### Decisões de fonte

- **Rejeitado** o Portal de Dados Abertos do DF (`dados.df.gov.br`): migrou de
  CKAN para SPA sobre Liferay 7.4 e não tem mais API pública. Os endpoints
  `/api/3/action/*` que toda a documentação da internet ainda cita respondem
  404.
- **Rejeitado** o InfoSaúde/SES-DF: publica painéis BI, não arquivos, e agrega
  por Região de Saúde (7) em vez de Região Administrativa (35).
- **Rejeitado** o INMET para clima: poucas estações, todas concentradas na
  porção central do DF; atribuir uma a cada RA produziria falsa granularidade.
- **Adotado** o CNES como fonte de saúde por ser a única base federal testada
  com coordenada por registro — e, portanto, a única que desce a Região
  Administrativa.

### Correções de dado durante a construção

- **Coordenada de preenchimento do CNES.** 274 estabelecimentos compartilhavam
  duas coordenadas, 232 deles no centro genérico de Brasília. Tratá-los como
  localizados fazia Cruzeiro aparecer com 99,1 estabelecimentos por 10 mil
  habitantes; após a correção, 9,7. Placeholders passaram a ser detectados por
  contagem nos próprios dados.
- **Setor público × privado.** A esfera administrativa do CNES vale `ESTADUAL`
  para 2.407 de 2.460 registros no DF, inclusive consultórios particulares. O
  setor passou a vir da natureza jurídica (CONCLA/IBGE): 2.336 privados, 88
  públicos, 36 sem fins lucrativos.
- **Agrupamento de serviços de saúde.** Os booleanos do CNES são verdadeiros em
  ~1% dos registros; o agrupamento passou a usar a descrição oficial do tipo de
  unidade, obtida da própria API.
- **Parsing numérico da SSP-DF.** Uma célula lida como `12.0` virava `120`,
  porque a limpeza de separador de milhar pt-BR removia o ponto decimal.
  Encontrado por teste antes de afetar o banco.
- **Ano da planilha da SSP-DF.** Os links da página se repetem entre anos; o ano
  passou a ser lido de dentro do arquivo.
- **Comparação temporal da segurança.** O insight comparava 2014 (29 RAs, 12
  meses) com 2026 (31 RAs, 8 meses), produzindo −85%. Passou a usar um painel
  fixo de RAs com anos completos em ambos os extremos.
- **Crescimento populacional por RA.** Removido do produto: as 19 RAs que
  existiam em 2010 todas cederam território às 16 criadas depois, e nenhuma
  comparação direta entre os Censos é válida. Publicamos a explicação da
  ausência.
- **Formatação numérica.** Os números dos insights saíam com separador
  americano (`1,006`); passaram a usar formatação pt-BR independente do locale
  do banco.
- **Cota do Open-Meteo.** 35 pontos × 8 anos estouravam o limite gratuito. As
  RAs passaram a ser agrupadas em 22 células de 0,1° — o que também é mais
  honesto, já que a grade do ERA5 é mais grossa que uma RA.

### Limitações conhecidas

- A SSP-DF não publica o balanço de 2024 para 15 das 35 RAs.
- O IBGE não publica Arapoanga e Água Quente no Censo 2022; conta-as nas RAs de
  origem.
- 151 estabelecimentos do CNES ficam sem região determinada e **não** são
  distribuídos entre as demais.
- Não existe série anual de população por RA — só os Censos de 2010 e 2022.
- Clima vem de reanálise ERA5, fonte externa e não governamental.

## Próximos passos

- Educação e mobilidade como novos domínios.
- Substituir o indicador de infraestrutura de saúde por produção de
  atendimentos, se o GDF publicar API para o novo portal de dados abertos.
- Validação cruzada da série climática com a estação do INMET em Brasília.
- Séries populacionais intercensitárias por RA a partir das projeções do
  IPEDF/Codeplan.
