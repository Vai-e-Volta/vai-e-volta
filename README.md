# Vai e Volta

Plataforma de locação entre pessoas (P2P) de itens ordinários. Projeto da disciplina
Projeto e Desenvolvimento de Software II (FURG).

## Como executar

Requisito: apenas Docker (com Compose v2) instalado.

```bash
cp .env.example .env      # troque POSTGRES_PASSWORD e JWT_SECRET
make up                   # sobe db, backend, worker e web
make seed                 # dados de exemplo (só em desenvolvimento)
```

A aplicação abre em http://localhost:8080.

## Comandos

| Ação | Comando |
|---|---|
| Subir | `make up` |
| Parar (mantém dados) | `make down` |
| Resetar tudo (apaga banco e fotos) | `make reset` |
| Lint e testes | `make lint` · `make test` |
| Exportar contrato OpenAPI | `make openapi` |
| Backup · restauração | `make backup` · `make restore DIR=backups/<carimbo>` |

## Documentação

- Documento Técnico do Projeto: escopo, regras de negócio (RN-nn), arquitetura, API e testes.
- Kit do Desenvolvedor: branches, commits, PRs, DoD, revisão e aceite.

## Fluxo de contribuição (resumo)

- Uma branch por tarefa: `tipo/H012-1-descricao-curta`.
- Commits no padrão Conventional Commits, com `Refs H012-1`.
- PR com título `feat(H012-1): descrição`, template preenchido, CI verde e aprovação de 1 colega dev.
- O merge (squash) é feito pelo Tech Lead depois do aceite do QA.
