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

O Compose sobe PostgreSQL 18, a API FastAPI, o worker e o frontend servido pelo Nginx em
http://localhost:8080. Em desenvolvimento, `docker-compose.override.yml` também publica a API em
http://localhost:8000 (docs em `/docs`) e o banco em `localhost:5432`, além de habilitar recarga
automática do backend. O Nginx encaminha `/api/` à API e serve `/uploads/` do volume compartilhado.
O banco usa o volume Docker `postgres_data`, montado no diretório de dados recomendado pela imagem
PostgreSQL 18.

## Comandos

| Ação | Comando |
|---|---|
| Subir/reconstruir | `make up` |
| Parar (mantém os dados) | `make down` |
| Apagar o banco local e subir novamente | `make reset` |
| Lint e testes | `make lint` · `make test` |
| Exportar contrato OpenAPI | `make openapi` |
| Carregar dados de demonstração | `make seed` |
| Rodar só a API no host | `make run-backend` |

Para subir a configuração de demonstração sem publicar as portas do banco e da API, use:

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`make test` usa sempre um container PostgreSQL temporário na máquina do desenvolvedor, mesmo que
`DATABASE_URL` esteja definido no shell. Assim, os testes que revertem migrações não alteram o banco
persistentemente usado pelo Compose. No CI, o runner usa o serviço PostgreSQL descartável do job.

`make seed` exige que o backend esteja em execução com `APP_ENV=dev`. Ele cria os cinco usuários
do Apêndice A, quinze anúncios com imagens ilustrativas e aluguéis nas situações principais. A
senha das contas fictícias é `Dev@12345`. As imagens do feed ficam em
`frontend/public/demo`; fotos enviadas pelos usuários continuam em `/uploads`. A conta
`elisa_rocha` começa excluída e pode ser
reativada pelo login. Executar novamente não duplica os dados nem desfaz alterações feitas nos
registros existentes. E-mails de demonstração usam o domínio reservado `exemplo.test`.

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

A migração `H002-1` cria `login_attempts` (bloqueio por tentativas, RN-14). O identificador
fica só como hash SHA-256 do valor normalizado, nunca em claro.

## Autenticação e conta

- `POST /api/auth/login` aceita e-mail ou nome de usuário e senha. Credenciais inválidas usam
  resposta única; após 5 falhas do mesmo identificador em 15 minutos, o acesso fica bloqueado por
  15 minutos (`429` com `Retry-After`). Os limites são configuráveis por `LOGIN_MAX_ATTEMPTS`,
  `LOGIN_WINDOW_MINUTES` e `LOGIN_LOCK_MINUTES`.
- A sessão usa JWT HS256 no cookie `vv_session` (HttpOnly, SameSite=Lax, Path=/), com validade de
  `JWT_EXPIRES_DAYS` (15 por padrão). `JWT_SECRET` deve ter pelo menos 32 caracteres; use
  `COOKIE_SECURE=true` quando a aplicação estiver sob HTTPS.
- `GET /api/auth/me`, `POST /api/auth/logout`, `PUT /api/me/password` e `DELETE /api/me` cobrem
  consulta privada da sessão, saída, troca de senha e exclusão da conta. A troca da senha exige a
  senha atual e encerra as outras sessões. A exclusão também exige a senha, cancela propostas
  pendentes, pausa anúncios e invalida a sessão; aluguéis aceitos em andamento ou futuros impedem
  a operação (`409`).
- Uma conta excluída pode ser reativada ao entrar antes de `purge_after`; seus anúncios permanecem
  pausados. `ACCOUNT_RETENTION_DAYS` define o prazo (365 dias por padrão).

`GET /api/listings` exige sessão e retorna o feed, por padrão do mais recente ao mais antigo, com paginação por cursor
(padrão 20 itens, máximo 50). O total considera anúncios ativos cuja janela não terminou e cujo
dono não foi excluído; os cards mostram bairro e cidade, sem dados pessoais ou endereço completo.
O parâmetro opcional `q` busca parte do título sem diferenciar maiúsculas ou acentos; `%`, `_` e
`\` são tratados como texto comum. Cada card também traz `is_favorite`; `favorites=true` limita o
feed aos favoritos. Favoritar e desfavoritar usam `PUT` e `DELETE /api/listings/{id}/favorite` e são
idempotentes. Um cursor inválido retorna `400 INVALID_CURSOR`.

O parâmetro `sort=newest|oldest|price_asc|price_desc` (padrão `newest`, F-20) ordena o feed por data
de publicação ou por valor por dia, sempre com desempate por `id` na mesma direção da chave. A
paginação é por chave (RN-30): o `next_cursor` guarda a ordem usada, a chave dela (`created_at` ou
`daily_price`) e o `id` do último item, então a rolagem não repete nem pula itens em nenhuma ordem,
mesmo que anúncios sejam criados durante ela. Um cursor só vale para a ordem em que foi gerado;
usado com outro `sort`, ou malformado, retorna `400 INVALID_CURSOR`. Um `sort` desconhecido retorna
`422 VALIDATION_ERROR`. A consulta usa os índices `(created_at, id)` e `(daily_price, id)`.

O parâmetro `availability=all|available_now|rented_now` (padrão `all`) filtra por disponibilidade
(RN-28, F-21), sempre com o "hoje" de `today_br()` (`America/Sao_Paulo`). `available_now` traz
anúncios ativos com janela vigente hoje (`available_from ≤ hoje ≤ available_until`) e sem aluguel
`accepted` cobrindo hoje; `rented_now` traz os que têm aluguel `accepted` em andamento hoje
(início e fim inclusivos). `all` não restringe e mantém a RN-24. Valor desconhecido retorna
`422 VALIDATION_ERROR`. O filtro combina com E com os demais (`q`, `categories[]`, `favorites`).

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
`app/services/rental_situation.py` centraliza a situação exibida do aluguel (aguardando,
reservado, em andamento, atrasado e histórico) e usa o dia local de `America/Sao_Paulo`.
O locatário pode registrar a solicitação de devolução antecipada em
`POST /api/rentals/{id}/return-request` após o início do aluguel.

A migração `H022-1` cria `notifications` (RN-68). O banco guarda só dados (`type` e `payload`),
nunca a frase, e um CHECK recusa chaves de dados pessoais no `payload`. O índice único parcial
`uq_notifications_worker_user_type_rental` vale para `rental_starting`, `return_due` e
`rental_overdue` e torna o worker idempotente (`ON CONFLICT DO NOTHING`).

## Página do item

`GET /api/listings/{id}` (exige sessão) devolve a página do item (F-28, F-31): fotos (`id` e
`filename`, a primeira é a capa), título, descrição, valor por dia, prazo máximo, janela, categoria,
tags, `owner_username` e `is_owner`. `404 LISTING_NOT_FOUND` se o anúncio não existe. Anúncio
pausado, excluído ou de conta excluída responde `200` com `{"id": ..., "unavailable": true}` e nada
mais (RN-34); o dono o vê normalmente, com `status` indicando a situação (F-31). O local de retirada
traz rua, bairro e cidade para todos; `pickup_number` e `pickup_complement` só vêm para o locatário
com aluguel `accepted` no item, lidos da `listing_snapshot` desse aluguel, e o CEP nunca é devolvido
(RN-35, RN-15).

`GET /api/listings/{id}/booked-periods` (exige sessão) lista os períodos que bloqueiam datas
(F-29): aluguéis `accepted` e `completed`, como na restrição `rentals_no_overlap` (RN-42), em ordem
de início, no formato `{"items": [{"start_date", "end_date"}]}`. Propostas `pending` não bloqueiam
(RN-44). Para anúncio indisponível a quem não é o dono, a lista vem vazia.

## Worker (tarefas agendadas)

O serviço `worker` do Compose usa a mesma imagem do backend com o comando `python -m app.worker`
(APScheduler 3.11). A cada ciclo, cada tarefa obtém um lock consultivo do PostgreSQL
(`pg_try_advisory_lock`); se outra instância estiver com o lock, o ciclo é pulado. Ao final de
cada ciclo o worker atualiza `/tmp/worker_heartbeat`, e o healthcheck do contêiner
(`python -m app.worker.healthcheck`) falha se o arquivo tiver mais de 120 s. Logs em JSON, uma
linha `INFO` por tarefa.

Para criar uma tarefa, registre uma função **idempotente** `(session, now)` em
`app/worker/tasks.py` (ou em um módulo importado por ele):

```python
@registry.register("expire_proposals", minutes=1)
def expire_proposals(session: Session, now: datetime) -> None: ...
```

`now` é o instante atual em UTC, injetado pelo runner para permitir testes com relógio congelado.

Tarefas registradas:

| Tarefa | Frequência | O que faz |
|---|---|---|
| `heartbeat` | 30 s | Confere a conexão com o banco |
| `calendar_notices` | 15 min | Avisa as duas partes de aluguéis `accepted`: véspera do início, véspera do fim e atraso (F-50); um aviso por parte e evento |
| `expire_proposals` | 1 min | `pending` com `expires_at` vencido ou `start_date` antes de hoje vira `expired` (RN-47) |
| `anonymize_accounts` | diária | Anonimiza contas excluídas após a retenção (RN-21) |
| `cleanup` | diária | Remove tentativas de login antigas e fotos órfãs |

Para acompanhar: `docker compose logs -f worker`.

## Documentação

- Documento Técnico do Projeto: escopo, regras de negócio (RN-nn), arquitetura, API e testes.
- Kit do Desenvolvedor: branches, commits, PRs, DoD, revisão e aceite.

## Fluxo de contribuição (resumo)

- Uma branch por tarefa: `tipo/H012-1-descricao-curta`.
- Commits no padrão Conventional Commits, com `Refs H012-1`.
- PR com título `feat(H012-1): descrição`, template preenchido, CI verde e aprovação de 1 colega dev.
- O merge (squash) é feito pelo Tech Lead depois do aceite do QA.
