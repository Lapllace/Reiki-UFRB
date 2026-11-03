# Ajustes do contrato no frontend (Fase 2)

O backend implementa a regra real de disponibilidade: **o ministrante informa**
seus dias, horários e locais. O contrato proposto no frontend (`SlotOption`,
`options`, `selectedSlotIds`) assume opções pré-fornecidas pela coordenação e
**não corresponde ao domínio** — não foi mantido silenciosamente.

## `frontend/src/lib/types.ts`

1. Substituir em `WeeklyAvailability`:
   - remover `options: SlotOption[]` e `selectedSlotIds: string[]`;
   - adicionar `entries: AvailabilityEntry[]` e `submittedAt?: string | null`.
2. Substituir `SlotOption` por:

   ```ts
   export type AvailabilityEntryKind = "available" | "unavailable";

   export interface AvailabilityEntry {
     id: string;
     kind: AvailabilityEntryKind;
     startsAt: string; // ISO 8601 com fuso
     endsAt: string;
     locationId?: string | null;
     note?: string | null;
   }
   ```

3. Atualizar `AvailabilityStatus` para `"pending" | "submitted" | "unavailable"`
   (o backend não usa `"published"` como estado da submissão).
4. Atualizar `PublishAvailabilityInput`:

   ```ts
   export interface PublishAvailabilityInput {
     weekStart: string;
     unavailable: boolean;
     note?: string | null;
     entries: {
       startsAt: string;
       endsAt: string;
       locationId?: string | null;
       note?: string | null;
     }[];
   }
   ```

## `frontend/src/lib/api/contract.ts`

- `availability.get(weekStart | null)` e `availability.publish(input)` mantêm as
  assinaturas; apenas os tipos de entrada/saída mudam conforme acima.

## `frontend/src/lib/api/endpoints.ts`

- `instructor.availability` → `GET/POST /instructor/availability` (já correto).

## `frontend/src/lib/api/services.ts`

- Mapear `entries` (e não `options`/`slotIds`) na desserialização de
  `WeeklyAvailability`.
- `EnrollmentResult`: ler `enrollment` da resposta; `waitlistPosition` em camelCase.
- `Enrollment.canCancel`/`cancelBlockedReason` são decididos pelo servidor —
  não recalcular no cliente.

## Demonstração

- Manter `src/lib/demo` isolado; dados demonstrativos não são registros oficiais
  e não devem ser enviados ao backend.

## Fase 4 — reorganização

Os caminhos propostos pelo frontend são mantidos:

- `GET /coordination/reallocations`
- `POST /coordination/reallocations/{id}/apply`
- `POST /coordination/reallocations/{id}/dismiss`

O backend exige que `apply` informe explicitamente a alternativa:

```json
{ "alternative": "extra_session", "targetSessionId": "<uuid>" }
```

ou:

```json
{ "alternative": "future_priority" }
```

As respostas usam `originSession`, `candidateSessions`, `participantCount`,
`appliedTo`, `priorityGrantedAt` e `decidedAt`. A prioridade futura é
persistida e auditada, mas ainda não é usada para prometer vaga, pois as regras
de seleção semestral dependem de confirmação institucional. O frontend não
deve apresentar essa prioridade como inscrição confirmada.

Sessões extras são criadas por `POST /coordination/sessions/extra` com
`startsAt`, `endsAt`, `locationId` e `capacity` obrigatórios. Elas começam em
`scheduled`; a coordenação precisa publicá-las/abri-las segundo as regras do
ciclo antes de usá-las como destino.

## Fase 4.1 — integração efetiva

Disponibilidade usa `POST /instructor/availability` e envia `entries` com os
intervalos informados pelo ministrante. `options`/`selectedSlotIds` existem
somente como compatibilidade do modo demonstração.

`CoverInviteOut` retorna `sessionId`, `status` (inclusive `declined`) e
`accepted`; não retorna a sessão completa nem o nome de outro ministrante.
O cancelamento retorna `{ coverRequestId, status, sessionId }`, e não uma sessão.

As telas integradas usam ainda `GET /instructor/sessions`,
`GET /instructor/sessions/{id}/roster`, as rotas de ciclo/sessões/roster,
coberturas e eventos da coordenação, além de `GET /me/notifications` e
`POST /me/notifications/{id}/read`. Rosters são privados e notificações só
podem ser marcadas como lidas pelo próprio destinatário.
