# Como contribuir

## Ambiente

```bash
./scripts/setup.sh        # .env, venv, npm install, Postgres em container
./scripts/run_pipeline.sh # popula o banco (~12 min na primeira vez)
docker compose up -d      # sobe API e frontend
```

## As três regras inegociáveis

### 1. Nunca invente dado

* Nenhum número no produto pode vir de outro lugar que não uma fonte oficial
  testada. Se a fonte não publica, o campo é `NULL` e a interface mostra `—`.
* **Ausência nunca vira zero.** Um mês sem publicação da SSP-DF é uma quebra na
  linha do gráfico, não um ponto em zero.
* Mock temporário, se inevitável durante o desenvolvimento, fica marcado com
  `DEVELOPMENT MOCK DATA` e é removido antes do merge.

### 2. Nunca afirme causa

Os dados descrevem o que foi **registrado**, não o que aconteceu. Texto de
insight que diga "causou", "provocou", "por causa de" ou "resultou em" falha no
teste `test_insights_never_claim_causation`.

Onde duas séries se movem juntas, escreva "associação" e inclua a ressalva.

### 3. Métrica que não pode ser calculada não é publicada

O caso de referência está em
[`int_region_lineage`](dbt/models/intermediate/int_region_lineage.sql): o
crescimento populacional por RA entre 2010 e 2022 **não existe** no produto,
porque as fronteiras mudaram entre os Censos. Preferimos publicar a explicação
da ausência a publicar um número errado.

## Adicionando uma fonte

1. **Descoberta antes de código.** Acesse a fonte de verdade, examine o payload,
   liste os campos, descubra a cobertura temporal e as limitações. Registre em
   [`docs/data_sources.md`](docs/data_sources.md) com status
   `VALIDADA` ou `REJEITADA` — e, se rejeitada, o motivo com a resposta obtida.
2. **Prefira API a arquivo; prefira fonte oficial a agregador.** Nada de Kaggle
   quando existe fonte oficial. Nada de endpoint suposto: teste antes.
3. **Adicione uma checagem** em `ingestion/validate_sources.py`. Ela roda no CI
   antes da ingestão e falha cedo se o contrato mudar.
4. **Crie o módulo** em `ingestion/<dominio>.py` seguindo o padrão dos
   existentes: `PoliteSession`, `ingestion_run`, `save_raw`, `upsert`
   idempotente, `record_check` para os achados de qualidade.
5. **Crie a tabela RAW** em `db/init/02_raw.sql`, com chave natural como
   `PRIMARY KEY`, `_source_url` e `_ingested_at`. Coluna nova em tabela que já
   existe entra como `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` na seção de
   migrações.
6. **Modele no dbt**: `staging` (limpeza) → `intermediate` (joins) → `marts`
   (tabelas). Declare o grão no cabeçalho do modelo e escreva o teste que o
   protege.
7. **Registre a fonte** em `dbt/seeds/source_catalog.csv`, incluindo o
   `caveat` — ele aparece na interface.
8. **Exponha na API** com schema Pydantic documentado.

## Escrevendo modelos dbt

* O comentário de cabeçalho explica **por que** o modelo existe e qual
  armadilha ele trata, não o que o SQL faz.
* Todo fato declara seu grão e tem um teste de unicidade correspondente.
* Mapeamento editorial (RA↔IBGE, natureza criminal↔categoria) vai para seed
  CSV — assim a mudança vira diff revisável no PR.
* Nada de `dbt_utils`: os testes de grão estão em `dbt/tests/` como SQL
  singular. Uma dependência a menos para manter.

## Testes

```bash
pytest                                  # tudo (integração é pulada sem banco)
pytest tests/test_security_parser.py    # só o parser da SSP
cd dbt && dbt build                     # modelos + 105 testes de qualidade
cd frontend && npm run typecheck
```

Todo PR precisa passar em `pytest`, `dbt build` e no typecheck do frontend.

Ao corrigir um bug de dado, **escreva primeiro o teste que falha**. Foi assim
que apareceram o bug de `12.0` virando `120` no parser da SSP e a coordenada de
preenchimento do CNES que inflava a rede de saúde do Cruzeiro.

## Frontend

* Dark mode é o padrão e o único tema.
* Use os tokens de `tailwind.config.js`. Uma cor por domínio: população aqua,
  segurança rosa, saúde azul, clima violeta.
* Todo número com ressalva metodológica carrega um `<DataNotice>` perto.
* Nenhum cálculo de indicador no frontend — ele apresenta o que a API devolve.

## Estilo

* Python: type hints, docstrings em português explicando a decisão.
* SQL: minúsculas, CTEs nomeadas, comentário de cabeçalho no modelo.
* TypeScript: `strict`, sem `any`.
* Commits: imperativo e específico (`corrige atribuição de RA para coordenadas
  de preenchimento do CNES`).

## Reportando um número errado

Abra uma issue com:

1. o valor exibido e onde;
2. o valor esperado e a fonte que o sustenta;
3. a saída de `curl localhost:8000/api/<endpoint>` correspondente.

Como toda tabela `raw` guarda `_source_url` e `_ingested_at`, e os payloads
brutos ficam em `data/raw/`, é possível rastrear qualquer número até a
requisição que o trouxe.
