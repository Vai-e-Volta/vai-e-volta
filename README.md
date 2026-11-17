# Vai e Volta

Plataforma de locação entre pessoas (P2P) de itens ordinários. Projeto da disciplina
Projeto e Desenvolvimento de Software II (FURG).

## Como executar localmente

Requisitos: Docker Desktop com Compose v2, GNU Make e `uv` instalado.

No Windows, instale o GNU Make uma vez pelo WinGet:

```powershell
winget install --id ezwinports.make --exact
```

Depois de instalar, abra um novo terminal. Copie `.env.example` para `.env`, mantendo as
credenciais locais de desenvolvimento, e execute:

```powershell
Copy-Item .env.example .env
make up
```

O Compose sobe PostgreSQL 18 e a API FastAPI. A API aplica as migrações ao iniciar e fica em
http://localhost:8000; documentação interativa em http://localhost:8000/docs. O banco usa o
volume Docker `postgres_data`, montado no diretório de dados recomendado pela imagem PostgreSQL 18.

## Comandos

| Ação | Comando |
|---|---|
| Subir/reconstruir | `make up` |
| Parar (mantém os dados) | `make down` |
| Apagar o banco local e subir novamente | `make reset` |
| Lint e testes | `make lint` · `make test` |
| Exportar contrato OpenAPI | `make openapi` |
| Rodar só a API no host | `make run-backend` |

`make test` usa sempre um container PostgreSQL temporário na máquina do desenvolvedor, mesmo que
`DATABASE_URL` esteja definido no shell. Assim, os testes que revertem migrações não alteram o banco
persistentemente usado pelo Compose. No CI, o runner usa o serviço PostgreSQL descartável do job.

O frontend ainda não foi criado; por isso os alvos `lint-frontend` e `test-frontend` informam que
foram ignorados até existir `frontend/package.json`.

## Banco de dados e migrações

O backend usa `DATABASE_URL` para se conectar ao PostgreSQL. No diretório `backend`, use:

```powershell
uv run alembic revision --autogenerate -m "descricao_da_migracao"
uv run alembic upgrade head
uv run alembic downgrade -1
```

A migração `H001-1` cria `users`, incluindo identificadores únicos, endereço de retirada,
controle de versão do token e datas de exclusão/anonimização. O banco aplica restrições de
formato e unicidade; regras completas de cadastro permanecem na API.

A migração `H002-1` cria `login_attempts` (bloqueio por tentativas, RN-14). O identificador
fica só como hash SHA-256 do valor normalizado, nunca em claro.

A migração `H006-1` cria `categories` (com as 8 categorias fixas da RN-58), `listings`,
`listing_photos`, `tags` e `listing_tags`. Preço, prazo máximo, janela de disponibilidade, posição
das fotos e tag normalizada têm CHECK no banco; mínimo/máximo de fotos, máximo de tags e
`available_until ≥ hoje` ficam na API.

A migração `H013-1` cria `favorites` com PK (`user_id`, `listing_id`). O favorito de anúncio
pausado ou excluído é mantido (RN-31); por isso a FK não tem `ON DELETE CASCADE`.

A migração `H016-1` cria `rentals` (propostas e aluguéis) com a restrição `rentals_no_overlap`
(`EXCLUDE USING gist`, RN-42): aluguéis `accepted` ou `completed` do mesmo anúncio não se
sobrepõem, com intervalos inclusivos (devolução no dia 14 libera retirada só no dia 15). Propostas
`pending` não entram na restrição. `expires_at` é gravado pela API (`created_at` +
`PROPOSAL_TTL_HOURS`). A duração inclusiva fica em `app/services/rental_period.py` (RN-36).

A migração `H022-1` cria `notifications` (RN-68). O banco guarda só dados (`type` e `payload`),
nunca a frase, e um CHECK recusa chaves de dados pessoais no `payload`. O índice único parcial
`uq_notifications_worker_user_type_rental` vale para `rental_starting`, `return_due` e
`rental_overdue` e torna o worker idempotente (`ON CONFLICT DO NOTHING`).

## Documentação

- Documento Técnico do Projeto: escopo, regras de negócio (RN-nn), arquitetura, API e testes.
- Kit do Desenvolvedor: branches, commits, PRs, DoD, revisão e aceite.

## Fluxo de contribuição (resumo)

- Uma branch por tarefa: `tipo/H012-1-descricao-curta`.
- Commits no padrão Conventional Commits, com `Refs H012-1`.
- PR com título `feat(H012-1): descrição`, template preenchido, CI verde e aprovação de 1 colega dev.
- O merge (squash) é feito pelo Tech Lead depois do aceite do QA.
