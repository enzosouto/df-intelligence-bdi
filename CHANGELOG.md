# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não lançado]

### Adicionado
- Miniatura de compartilhamento (`frontend/public/og.png`, 1200×630, 40 KB) e
  tags Open Graph/Twitter: título, descrição e malha de cobertura real das 35
  RAs quando o link é colado no WhatsApp, LinkedIn, X ou iMessage. Gerada por
  `scripts/og_image.py` a partir da API.

### Mudado
- **API saiu do Render e foi para o Vercel**, como função Python no mesmo
  domínio do site (`api/index.py`, região `cle1`, junto do Neon). O Render
  gratuito hibernou a API e não a religou; no Vercel a partida a frio é de
  ~1 s. Sem CORS, CSP só com `'self'`, `render.yaml` removido.
- `/api/health-check` diz a categoria da falha de banco (variável ausente,
  senha recusada, tempo esgotado…), sem expor a URL.
- Tela de carregamento sem o aviso de "até 1 minuto": deixou de ser verdade.

### Corrigido (produção)
- A atualização diária agendada para 09:00 UTC não rodou: o GitHub atrasa e
  descarta crons em hora cheia. Agora roda às 06:23 de Brasília, com
  repescagem às 12:47 (o clima é incremental, a segunda execução não duplica
  nada).
- "Não foi possível falar com a API" na primeira visita depois de um tempo
  parado: a API gratuita do Render dorme e responde 502/503 sem CORS enquanto
  acorda. O cliente tenta de novo com espera crescente por até ~75 s e mostra
  o aviso "Ligando o servidor".
- Previews do Vercel (um domínio por deploy) eram barrados pelo CORS:
  `API_CORS_ORIGIN_REGEX` libera só os domínios do projeto.

### Mobile
- **Página vazava para ~605px num celular de 390px** (o grid do mapa sem
  coluna explícita aceitava a largura da faixa de botões). Em todas as páginas
  a largura agora é a da tela.
- Barra de abas fixa embaixo (Painel, Insights, Fontes), com área da barra de
  gestos; cabeçalho de 56px; malha de cobertura só a partir do tablet.
- Gráficos desenhados na largura real (ResizeObserver): o texto dos eixos
  passava de 10px para ~4px ao encolher uma prancheta de 760px. Leitura por
  toque e arraste, sem travar a rolagem vertical.
- Mapa: no toque, o primeiro toque mostra nome e valor com botão "Abrir"; a
  prancheta segue o formato do DF (sem faixas vazias).
- Seletor nativo de região no painel e na página da RA; atalhos fixos para as
  seções; botão de compartilhar (folha do sistema ou copiar link).
- Ranking começa com 8 no celular e abre as 35 num toque; tabelas de
  cobertura e do pipeline viram cartões; metodologia dos insights recolhida
  (a limitação continua sempre visível).
- Alvos de toque de 40–44px; sem atraso de 300 ms nem flash de toque.
- Instalável na tela inicial (manifest, ícones 192/512 e maskable,
  `viewport-fit=cover`, safe areas). Grade do fundo parada em tela de toque.
- Links da API (documentação, JSON da região) apontam para o Render; antes
  caíam no próprio site.

### Adicionado
- **Atualização automática.** Serviço `updater` no Docker Compose
  (`scripts/scheduler.py`): clima + dbt todo dia às 06:00 de Brasília, todas
  as fontes às segundas; banco vazio dispara a carga completa na hora.
- **Deploy** (`docs/deploy.md`): Neon (banco), Render (API, `render.yaml`),
  Vercel (site, `vercel.json` + `.vercelignore`) e `production-data.yml` no GitHub
  Actions gravando no banco de produção no mesmo ritmo.
- Role `api_reader` só de leitura para a API; os GRANTs são refeitos pelo dbt
  a cada tabela recriada (`macros/grant_api_reader.sql`).
- `scripts/init_db.py` aplica `db/init/*.sql` em banco sem o gancho do Docker.
- `run_pipeline.sh --skip-validation`; `sslmode` da URL repassado ao dbt.

### Corrigido
- API: conexão do pool derrubada pelo banco (Neon suspende o computador
  ocioso) virava erro 500; agora é trocada por uma nova antes do uso.

### Removido
- Brilho magenta que acompanhava o cursor dentro dos painéis. No hover, o
  painel só ganha a borda do destaque.

### Corrigido
- **`docker compose run --rm pipeline` não executava nada.** Num checkout
  Windows com `core.autocrlf=true`, o `scripts/run_pipeline.sh` ia para o
  disco em CRLF e o `COPY` do Docker levava os `\r` para dentro da imagem
  Linux, onde o bash morre em `set -euo pipefail` — e o script saía com
  código 0, então a falha era silenciosa. O CI nunca pegou porque executa os
  passos direto, sem container. Corrigido na raiz com `.gitattributes`
  (`*.sh text eol=lf`), que vale para todo checkout, não só para o blob.
- **Cobertura omitia um domínio inteiro.** `mart_data_coverage` não conhecia
  mobilidade: uma RA sem ciclovia mapeada era contada como coberta. Passa a
  publicar `mobility_bikeway_km`, `mobility_metro_stations` e
  `domains_with_data` (0 a 6), que é o número que a interface pinta na malha.
- **Duas verificações de qualidade falhavam em toda execução.**
  `population.census_2010_coverage` e `census_2022_coverage` exigiam as 35 RAs,
  mas em 2010 só 19 existiam e em 2022 o IBGE não divulga duas. Severidade
  `ERROR` que nunca passa treina a equipe a ignorar erro; agora o piso é a
  cobertura real publicada por Censo, e violá-lo continua sendo `ERROR`.
- **As capturas de tela do README eram tiradas no meio da animação** —
  contadores a caminho do valor, painéis ainda em opacidade zero.
  `scripts/screenshots.py` passa a usar `reduced_motion="reduce"`, o que torna
  a captura determinística e serve de prova de que o caminho sem movimento
  renderiza o mesmo estado final.
- **A página travava quando o encaminhamento de porta do Docker engasgava.** O
  `.env` local apontava `VITE_API_BASE_URL` para `http://localhost:8000`, o que
  amarra o navegador à porta do host e anula o proxy de `/api` que o nginx do
  container já faz. Com um `wslrelay` órfão segurando `[::1]:8000`, toda
  requisição ficava pendurada e a interface não saía do carregamento. Passa a
  usar a mesma origem, como `.env.example` sempre documentou.
- `scripts/screenshots.py` espera a tela de carregamento sair, um sinal do
  próprio app, em vez de `networkidle` — que trava 30s inteiros quando uma
  requisição fica pendurada, e ainda esconde a causa.
- Números do README reconferidos contra o banco: são 112 testes de qualidade
  no dbt (153 era o total de nós — seeds, modelos e testes somados), 23
  endpoints, quatro páginas, e a tabela do modelo de dados ganhou as linhas de
  educação e mobilidade que faltavam.

### Alterado
- **Sistema visual refeito.** A interface antiga era o preset de dashboard
  escuro genérico: fundo quase preto, um accent verde-ácido, cards arredondados
  com sombra e halos em gradiente. Nada nela sabia que o assunto é uma cidade
  projetada. O novo sistema desenha como um projeto: grade de réguas de 1px,
  canto vivo, nenhuma sombra; violeta quase preto (`#060010`) de fundo, magenta
  (`#FF006A`) de destaque e tons de branco. Os três níveis de texto ficam todos
  perto do branco e a hierarquia é feita por tamanho, peso e entreletra: texto
  escuro sobre fundo escuro é ilegível, e hierarquia não vale o custo de
  ninguém conseguir ler a cota. As seis cores de domínio ficam espalhadas pela
  roda de cor para que duas séries num mesmo gráfico nunca se confundam.
  Tipografia: Archivo expandida, IBM Plex Sans e IBM Plex Mono.
- **Crédito do projeto** a Enzo Souto, analista de dados, na tela de
  carregamento e no rodapé.
- **O fundo virou uma prancheta viva** (`BackgroundField.vue`): grade em canvas
  onde uma faixa atravessa a tela acendendo as linhas por onde passa, os
  cruzamentos acendem em volta do cursor e alguns piscam sozinhos em magenta.
  Canvas e não DOM porque são centenas de pontos repintados por quadro; o laço é o
  `gsap.ticker`, o mesmo relógio das outras animações.
- **Retícula no lugar do cursor** (`Reticle.vue`), onde existe mouse: uma cruz
  magenta, e só. Fica exatamente sob o ponteiro, sem atraso — trocar o cursor
  do sistema não pode custar precisão; quem reage é a própria cruz, que cresce
  sobre o que é clicável. Os painéis acendem por dentro na posição do cursor,
  por um listener delegado só, em variáveis CSS.
- **Tela de carregamento** (`AppLoader.vue`): o vocabulário real do projeto
  varre o fundo enquanto a malha é plotada célula a célula e cada endpoint
  aparece com o seu status de verdade. Mínimo de 3s em tela — as duas
  requisições do boot voltam em ~200ms em localhost, e um loader que pisca por
  200ms é pior que loader nenhum.
- **Favicon**: o módulo da malha com uma célula vazia — a lacuna virou a marca.
  SVG mais PNGs rasterizados pelo Chromium do Playwright, sem dependência nova.
- **Mobile**: faixas de controle viram carrossel horizontal em vez de quebrar em
  quatro linhas, a malha acompanha a largura da tela, e nem retícula nem brilho
  de cursor montam em telas de toque.
- **Revelação por scroll** (ScrollTrigger): os grupos só tocam quando encostam
  na viewport, em vez de a página inteira gastar a animação de entrada acima da
  dobra.
- **A malha** (`frontend/src/components/Malha.vue`): 35 módulos, um por RA, com
  seis células cada — uma por domínio, preenchida ou vazia conforme a fonte
  publique. Fica no topo de toda página e é, ao mesmo tempo, identidade,
  leitura de cobertura e navegação.
- **Movimento em GSAP** (`frontend/src/motion.ts`), com uma regra só: a página é
  plotada, não exibida. Réguas crescem da margem, painéis assentam em cascata,
  linhas são traçadas da esquerda para a direita, números correm até o valor, e
  trocar a métrica do mapa repinta as 35 RAs numa onda de oeste para leste.
  `prefers-reduced-motion` monta direto no estado final.
- O dashboard mostra os **seis** domínios com o número que cada fonte publica
  hoje; antes mostrava quatro, repetindo os KPIs logo acima.
- A conferência final do `run_pipeline.sh` passa a contar também matrículas e
  trechos cicloviários.

### Adicionado
- **Domínio de educação** (Educacenso via SEEDF, `data.se.df.gov.br`, todas as
  redes, 2014–2025): `ingestion/education.py`, `fct_education_enrollment`,
  `mart_education_yearly`, `mart_education_coverage`, endpoints
  `/api/education` e `/api/education/coverage`, seção na página de região,
  três insights e a fonte `SEEDF_EDUCACENSO` no catálogo.
- Validado no pipeline real (GitHub Actions, ingestão das 6 fontes): 1.594
  escolas, 1.471 com RA pela coordenada, 121 pela declaração confiável, 2 sem
  região; 128 testes dbt e 20 de integração passando.
- 22 testes de parser (`tests/test_education_parser.py`), 5 testes singulares
  no dbt e 4 testes de integração, cada um codificando um achado dos arquivos
  reais (ver `docs/data_quality.md`, 2.13–2.19).

- **Domínio de mobilidade** (IDE-DF): malha cicloviária com recorte geodésico
  por RA, estações de metrô e terminais de ônibus. `ingestion/mobility.py`,
  `fct_mobility_bikeway`, `fct_mobility_station`, `mart_mobility_region`,
  `mart_mobility_bikeway_yearly`, endpoints `/api/mobility`,
  `/api/mobility/bikeways/yearly` e `/api/mobility/stations`, seção na página
  de região e três insights. Achados em `docs/data_quality.md`, 2.20–2.22.
  SEMOB e DETRAN rejeitados: não respondem a partir do runner do GitHub.
  Validado no pipeline real: 2.293 trechos, 671,9 km; 27 estações de metrô em
  operação em 6 das 35 RAs (40,7% da população); 44% da malha atual construída
  entre 2012 e 2014; 147 testes dbt e 22 de integração passando.

### Decisões de fonte (educação)
- **RA pela coordenada, não pela declaração.** Os códigos 34/35 da SEEDF estão
  invertidos em relação à numeração oficial em todos os anos, e o nome veio
  trocado em 2025. As escolas do Arapoanga seriam contadas em Água Quente.
- **Só anos completos são publicados.** Em 8 dos 12 anos o arquivo de
  matrículas omite escolas ativas do cadastro — sobretudo particulares (15% a
  29% delas de 2015 a 2022) e, em 2023, 664 das 1.264 escolas. Prova no
  pipeline real: das 102 escolas ausentes do arquivo de 2015, 87 tinham 26.844
  matrículas em 2014 — 94% da "queda" 2014→2015. Publicados: 2014, 2021,
  2024 (sem total) e 2025.
- **2024 sem total.** A fonte não publica a coluna; a soma das etapas só fecha
  exatamente em 2023 e 2025, então não a substitui.
- **Ensino médio = médio + integrado.** Sozinho, o médio "cai" 11% em 2025
  (100.541 → 89.098) por reclassificação; somado ao integrado fica estável
  (104.469 → 105.015).
- **Rótulo declarado só vale se as coordenadas o confirmam.** Em 2025 as
  escolas do Arapoanga vêm com código 35 **e** nome "AGUA QUENTE" — coerentes
  entre si, errados os dois. Cada par (ano, código, nome) precisa que a maioria
  das suas escolas geolocalizadas caia na RA indicada.
- **Microdados do Inep rejeitados:** cadeia TLS incompleta a partir do runner
  do GitHub e ausência de RA.

### Alterado
- `load_region_index` passou de `ingestion/health.py` para
  `ingestion/common.py`: saúde e educação usam o mesmo índice espacial.

### Corrigido
- **Terminais de ônibus deixam de ser publicados.** A validação visual com
  dados reais mostrou "0 terminais" no Plano Piloto: a camada da IDE-DF omite
  a Rodoviária do Plano Piloto. Métrica que não pode ser calculada não é
  publicada.
- **Gráficos:** ano com dado cercado de lacunas não aparecia (2014 e 2021 nas
  matrículas); a área era preenchida por cima das lacunas (série populacional
  do DF); o último rótulo do eixo X se sobrepunha ao anterior. Corrigidos no
  `LineChart`.
- **Interface:** eixo do gráfico de crimes em ISO (`2018-01-01`), título dos
  cards de indicador quase invisível na página de fontes, textos que citavam só
  quatro domínios. Mapa ganhou "Ciclovia / 10 mil hab.".
- **Regra 5 (nenhum cálculo de indicador na API) violada em três endpoints.**
  `/api/health` calculava a taxa por 10 mil habitantes; `/api/security/summary`
  somava as RAs para o total do DF; `/api/weather/summary` fazia a média do
  clima do DF. Os três números agora saem do dbt (`mart_health_region.
  facilities_per_10k`, `mart_security_df_monthly`, `mart_weather_df_monthly`),
  onde são testados. A série de segurança do DF ganhou `regions_reporting`.
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
