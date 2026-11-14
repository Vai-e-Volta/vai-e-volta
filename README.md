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

## Frontend

SPA em React 19 + Vite, com React Router 7, TanStack Query 5 e Tailwind CSS 4 (JavaScript/JSX),
em `frontend/`. Requer Node.js 24. Para desenvolver com recarga automática:

```powershell
cd frontend
npm ci
npm run dev
```

A tela abre em http://localhost:5173. O Vite encaminha `/api` e `/uploads` para a API em
http://localhost:8000 (suba-a antes com `make up`); para outro endereço, defina
`VITE_BACKEND_URL`. O código usa só caminhos relativos e acessa a API apenas por
`src/services/api.js`.

| Ação | Comando (em `frontend/`) |
|---|---|
| Lint e formatação | `npm run lint` · `npm run format:check` |
| Testes (Vitest) | `npm test` |
| Build de produção | `npm run build` |

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

## Documentação

- Documento Técnico do Projeto: escopo, regras de negócio (RN-nn), arquitetura, API e testes.
- Kit do Desenvolvedor: branches, commits, PRs, DoD, revisão e aceite.

## Fluxo de contribuição (resumo)

- Uma branch por tarefa: `tipo/H012-1-descricao-curta`.
- Commits no padrão Conventional Commits, com `Refs H012-1`.
- PR com título `feat(H012-1): descrição`, template preenchido, CI verde e aprovação de 1 colega dev.
- O merge (squash) é feito pelo Tech Lead depois do aceite do QA.
