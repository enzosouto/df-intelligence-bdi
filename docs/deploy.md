# Deploy

Três serviços gerenciados, cada um com uma função e a menor permissão possível:

```
                  ┌──────────────────────────┐
  navegador ────► │ Vercel  — site (Vue)     │  estático, CDN, headers de segurança
      │           └──────────────────────────┘
      │ fetch /api/*
      ▼
  ┌──────────────────────────┐   role api_reader    ┌──────────────────────┐
  │ Render  — API (FastAPI)  │ ───── só leitura ──► │ Neon — PostgreSQL    │
  └──────────────────────────┘                      └──────────────────────┘
                                                              ▲
  ┌────────────────────────────────────────────┐  role dona   │
  │ GitHub Actions — production-data.yml        │ ─────────────┘
  │ todo dia: clima + dbt · segundas: tudo      │  (única com escrita)
  └────────────────────────────────────────────┘
```

| Peça | Onde | Credencial | Pode |
|---|---|---|---|
| Banco | Neon, `us-east-2` (Ohio) | — | — |
| Carga dos dados | GitHub Actions | `PRODUCTION_DATABASE_URL` (secret, role dona) | escrever |
| API | Render, região `ohio`, `render.yaml` | `DATABASE_URL` da role `api_reader` | só ler `marts` |
| Site | Vercel, raiz `frontend/`, `frontend/vercel.json` | nenhuma | — |

**Por que a carga roda no GitHub e não no Render:** os portais do GDF recusam
conexões de fora do Brasil de forma irregular, e os runners do GitHub já
provaram que alcançam todas as fontes (é onde o CI roda a ingestão real).

## Segurança

- **API só lê.** Conecta com `api_reader`, que tem `SELECT` só no schema
  `marts` e `default_transaction_read_only = on`. Mesmo com uma falha na API,
  a role não altera nem apaga nada, e não enxerga `raw` nem `meta`. Os GRANTs
  são refeitos pelo próprio dbt a cada tabela recriada
  (`dbt/macros/grant_api_reader.sql`).
- **Senha de escrita em um lugar só:** o secret do GitHub Actions.
- **Nenhuma credencial no repositório.** `render.yaml` declara as variáveis
  com `sync: false`; os valores ficam nos painéis.
- **TLS** em tudo (`sslmode=require` no Neon, HTTPS no Render e no Vercel).
- **CORS** restrito ao domínio do site, só `GET`.
- **Headers no site:** CSP (só scripts do próprio domínio; conexões só com a
  API no Render), HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`.

## Passo a passo

### 1. Neon

1. Crie o projeto na região **AWS US East 2 (Ohio)**.
2. Copie a connection string **sem** pooling (host sem `-pooler`). A com
   pooling (PgBouncer em modo transação) não guarda o `SET` de sessão que o
   dbt e a API usam.
3. No SQL Editor, crie a role da API (senha longa, só letras e números):
   ```sql
   create role api_reader with login password '<senha>';
   alter role api_reader set default_transaction_read_only = on;
   ```

### 2. GitHub — carga dos dados

1. *Settings → Secrets and variables → Actions → New repository secret*
   - Nome: `PRODUCTION_DATABASE_URL`
   - Valor: a connection string da role **dona** (passo 1.2).
2. *Actions → production-data → Run workflow* (carga completa, ~15 min).
   Depois disso roda sozinho todo dia às 06:00 de Brasília.

### 3. Render — API

*New → Blueprint*, escolha o repositório. O `render.yaml` cria o serviço.
Preencha:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `postgresql://api_reader:<senha>@<host-sem-pooler>/neondb?sslmode=require` |
| `API_CORS_ORIGINS` | domínio do site, ex. `https://df-intelligence.vercel.app` |

Confira: `https://<servico>.onrender.com/api/health-check`.

### 4. Vercel — site

*Add New → Project*, escolha o repositório.

- **Root Directory:** `frontend`
- **Environment Variable:** `VITE_API_BASE_URL` = `https://<servico>.onrender.com`

O `frontend/vercel.json` cuida do resto (build, rotas do Vue, cache, headers).
Depois do primeiro deploy, confira se `API_CORS_ORIGINS` no Render bate com o
domínio final do Vercel.

## Custos e limites (planos gratuitos)

- **Render free** hiberna após 15 min sem acesso; a primeira visita depois
  disso leva ~30–60 s (o site mostra a tela de carregamento). O plano Starter
  (US$ 7/mês) mantém a API sempre ligada.
- **Neon free**: 0,5 GB (o banco usa bem menos) e computação que suspende
  sozinha; a API troca a conexão derrubada por uma nova sem erro.
- **GitHub Actions**: a carga diária leva poucos minutos; a semanal, ~15.

## Rodando localmente

Nada muda: `docker compose up -d` sobe tudo, inclusive o `updater`, que faz
localmente o mesmo que o `production-data.yml` faz em produção.
