# Reiki UFRB — Backend

FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL (psycopg3). Fundação (Fase 1) mais
disponibilidade semanal, inscrições/fila de espera (Fase 2), cobertura (Fase 3)
e reorganização administrativa (Fase 4).

## Status — IMPORTANTE

A migração **ainda NÃO foi executada contra o PostgreSQL real** (o acesso ao banco
local não está configurado). Os SQLs abaixo foram gerados no modo offline do
Alembic e servem apenas para inspeção:

- `migrations_offline_postgresql.sql` — Fase 1 (3bbfdbd42a4c)
- `migrations_offline_postgresql_phase2.sql` — Fase 1 + 2 (a7c3d9e1f2b4)
- `migrations_offline_postgresql_phase3.sql` — Fase 1 + 2 + 3 (b8d4e2f6a9c1)
- `migrations_offline_postgresql_phase4.sql` — Fase 1 + 2 + 3 + 4 (c4f5a6b7d8e9)

SQLite é usado nos testes unitários. Ele **não** valida: bloqueios (`FOR UPDATE`),
índice parcial único, timezone de `TIMESTAMP WITH TIME ZONE` nem a execução real
das migrações.

## Recursos implementados

- **Fase 1**: usuários (Argon2), sessões opacas por cookie (`reiki_session`,
  revogação no logout), locais, agenda semanal (`GET /sessions?weekStart=...`,
  normalização para segunda-feira, `published` derivado do ciclo).
- **Fase 2 — disponibilidade**: o ministrante **informa** seus dias/horários/locais
  (não escolhe slots pré-definidos). Um registro por (ministrante, semana);
  indisponibilidade é declarada explicitamente (`unavailable=true`) — ausência de
  submissão ≠ indisponibilidade. Publicação da agenda exige que **todos** os
  ministrantes ativos tenham submetido; é idempotente.
- **Fase 2 — inscrições**: decisão sempre do servidor. Capacidade indefinida
  bloqueia inscrição confirmada (não é ilimitada). Fila de espera com posição
  atribuída pelo servidor, ordenação determinística e promoção transacional do
  próximo no cancelamento.
- **Fase 3 — cobertura**: cancelamento pelo responsável, convites aos demais
  ministrantes e primeiro aceite vencedor.
- **Fase 4 — reorganização**: cada inscrição ativa afetada por uma sessão
  `uncovered` gera um caso único. A coordenação pode dispensá-lo, encaminhá-lo
  para uma sessão extra aberta com vaga ou registrar prioridade futura.
  Inscrições originais nunca são apagadas; a nova inscrição referencia o caso.
  A prioridade futura é apenas auditável e não garante vaga automaticamente.

## Endpoints (Fase 2)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/instructor/availability?weekStart=YYYY-MM-DD` | Submissão da semana (`pending` quando inexistente) |
| POST | `/instructor/availability` | Cria/atualiza a submissão (idempotente) |
| POST | `/enrollments` | `{ "sessionId": "<uuid>" }` → 201 com `EnrollmentResult` |
| GET | `/me/enrollments` | Inscrições do usuário autenticado |
| POST | `/enrollments/{id}/cancel` | Cancela e promove o próximo da fila |

Erros de regra de negócio: 409 com `detail` e cabeçalho `X-Error-Code`
(`locked`, `incomplete`, `not_open`, `duplicate`, `capacity_undefined`,
`not_cancellable`, `session_closed`); 404 para recurso inexistente.

## Endpoints (Fase 4)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/coordination/reallocations` | Casos de reorganização, apenas coordenação |
| POST | `/coordination/reallocations/{id}/apply` | Aplica `extra_session` ou `future_priority` |
| POST | `/coordination/reallocations/{id}/dismiss` | Encerra o caso sem apagar o histórico |
| POST | `/coordination/sessions/extra` | Cria sessão extra `scheduled` com capacidade explícita |

`apply` recebe `{"alternative":"extra_session","targetSessionId":"<uuid>"}`
ou `{"alternative":"future_priority"}`. Sessões extras só podem receber
reorganizações quando estiverem `open`/`full` e ainda houver vaga confirmada.
A criação não publica nem abre automaticamente a sessão.

### Exemplo — submeter disponibilidade

```json
POST /instructor/availability
{
  "weekStart": "2026-10-26",
  "unavailable": false,
  "entries": [
    { "kind": "available", "startsAt": "2026-10-28T14:00:00-03:00",
      "endsAt": "2026-10-28T17:00:00-03:00", "locationId": "<uuid>" }
  ]
}
```

### Exemplo — inscrição

```json
POST /enrollments
{ "sessionId": "<uuid>" }

201 →
{ "enrollment": { "id": "...", "status": "waitlisted", "waitlistPosition": 2,
  "createdAt": "2026-10-22T15:00:00+00:00", "sessionId": "...",
  "canCancel": true, "cancelBlockedReason": null } }
```

## Contrato com o frontend — divergência conhecida

O frontend (`SlotOption`/`slotIds`) assume horários pré-definidos pela
coordenação. A regra real é o ministrante informar os horários; o backend
implementa a regra real. Ajustes necessários no frontend:
`frontend/src/lib/types.ts` (`WeeklyAvailability.entries`, remover
`options`/`selectedSlotIds`), `contract.ts`, `endpoints.ts`
(`/instructor/availability`) e `services.ts`. Detalhes em
`docs/FRONTEND_CONTRACT_ADJUSTMENTS.md`.

## Regras que ainda dependem de confirmação institucional

- Capacidade por modalidade de atendimento — **não há padrão**; sessão sem
  capacidade não aceita inscrições confirmadas.
- Prazos de cancelamento — elegibilidade hoje depende apenas dos estados da
  inscrição e da sessão.
- Exceções da coordenação (liberar edição após o ciclo fechar) — etapa futura.

## Comandos

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest tests -q     # suite completa (SQLite)
& .\.venv\Scripts\python.exe -m alembic upgrade head  # quando o PostgreSQL estiver configurado
& .\.venv\Scripts\python.exe -m alembic upgrade head --sql  # SQL offline
```

## Pendências (bloqueadas por PostgreSQL)

1. Execução real das migrações no PostgreSQL (`alembic upgrade head`).
2. Testes de concorrência (inscrições simultâneas, `FOR UPDATE`, índice parcial).
3. Integração dos contratos de disponibilidade e inscrição com o frontend.
4. Definição institucional de capacidade por modalidade.
5. Regras semestrais de participação (desconhecidas).
6. Execução real da migração e testes de concorrência da Fase 4 no PostgreSQL.
7. Regras institucionais para uso e seleção de prioridades futuras.
