# Deploy

Dois serviços gerenciados e o GitHub Actions, cada um com a menor permissão
possível:

```
                  ┌──────────────────────────────────────────┐
  navegador ────► │ Vercel — df-intelligence-bdi.vercel.app  │
                  │   /          → site (Vue, estático, CDN) │
                  │   /api/*     → função Python (FastAPI)   │
                  └──────────────────────┬───────────────────┘
                                         │ role api_reader (só leitura)
                                         ▼
                              ┌──────────────────────┐
                              │ Neon — PostgreSQL    │
                              └──────────────────────┘
                                         ▲ role dona (única com escrita)
  ┌──────────────────────────────────────┴──────┐
  │ GitHub Actions — production-data.yml        │
  │ todo dia: clima + dbt · segundas: tudo      │
  └─────────────────────────────────────────────┘
```

| Peça | Onde | Credencial | Pode |
|---|---|---|---|
| Banco | Neon, `us-east-2` (Ohio) | — | — |
| Carga dos dados | GitHub Actions | `PRODUCTION_DATABASE_URL` (secret, role dona) | escrever |
| API | Vercel, função `api/index.py`, região `cle1` (Ohio) | `DATABASE_URL` da role `api_reader` | só ler `marts` |
| Site | Vercel, mesmo domínio, `vercel.json` | nenhuma | — |

**Por que a API saiu do Render:** no plano gratuito ele hiberna o serviço após
15 min e, em 25/09/2026, não o religou — o site ficou preso na tela de
carregamento até um deploy manual. Como função do Vercel, a partida a frio é de
~1 s, o domínio é o mesmo do site (sem CORS) e não há serviço para manter.

**Por que a carga roda no GitHub:** os portais do GDF recusam conexões de fora
do Brasil de forma irregular, e os runners do GitHub já provaram que alcançam
todas as fontes (é onde o CI roda a ingestão real).

## Segurança

- **API só lê.** Conecta com `api_reader`, que tem `SELECT` só no schema
  `marts` e `default_transaction_read_only = on`. Mesmo com uma falha na API,
  a role não altera nem apaga nada, e não enxerga `raw` nem `meta`. Os GRANTs
  são refeitos pelo próprio dbt a cada tabela recriada
  (`dbt/macros/grant_api_reader.sql`).
- **Senha de escrita em um lugar só:** o secret do GitHub Actions.
- **Nenhuma credencial no repositório.** `DATABASE_URL` fica nas variáveis do
  projeto no Vercel; a senha de escrita, no secret do GitHub.
- **TLS** em tudo (`sslmode=require` no Neon, HTTPS no Vercel).
- **Mesmo domínio:** site e API no mesmo endereço; o navegador não precisa de CORS.
- **Headers no site:** CSP (só scripts e conexões do próprio domínio), HSTS, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`.

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
   Depois disso roda sozinho todo dia às 06:23 de Brasília, com uma
   repescagem às 12:47 (o GitHub às vezes descarta execuções agendadas).

### 3. Vercel — site e API

*Add New → Project*, escolha o repositório e clique em *Deploy*, sem mudar
nada. O `vercel.json` da raiz faz o build de `frontend/`, publica `api/index.py`
como função Python e manda `/api/*`, `/docs`, `/redoc` e `/openapi.json` para
ela; o resto é o site.

Depois, em *Settings → Environments → Production → Environment Variables*:

| Variável | Valor |
|---|---|
| `DATABASE_URL` | `postgresql://api_reader:<senha>@<host-sem-pooler>/neondb?sslmode=require` |

e *Deployments → ⋯ → Redeploy* (variável nova só vale em deploy novo).

Confira: `https://<projeto>.vercel.app/api/health-check` → `{"status":"ok"}`.
Se vier 503, o `detail` diz a categoria da falha (variável ausente, senha
recusada, tempo esgotado…) sem expor a URL.

## Custos e limites (planos gratuitos)

- **Vercel Hobby**: função com partida a frio de ~1 s; uso pessoal e não
  comercial.
- **Neon free**: 0,5 GB (o banco usa bem menos) e computação que suspende
  sozinha após alguns minutos; acorda em ~1 s, e a API troca a conexão
  derrubada por uma nova sem erro.
- **GitHub Actions**: a carga diária leva ~1 min; a semanal, ~15.

## Rodando localmente

Nada muda: `docker compose up -d` sobe tudo, inclusive o `updater`, que faz
localmente o mesmo que o `production-data.yml` faz em produção.
