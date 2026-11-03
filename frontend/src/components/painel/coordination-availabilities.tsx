"use client";

import { useEffect, useRef, useState } from "react";
import {
  CalendarCheck2,
  CalendarX2,
  CheckCircle2,
  CircleDashed,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  UsersRound,
} from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import type { ApiError } from "@/lib/api/errors";
import { cyclePhaseLabel } from "@/lib/cycle-phases";
import { formatDateTime, formatDayLong, formatTimeRange } from "@/lib/dates";
import type {
  AvailabilityStatus,
  CoordinationAvailabilityEntry,
  CoordinationInstructorAvailability,
  WeekAvailabilities,
} from "@/lib/types";

const availabilityMeta: Record<
  AvailabilityStatus,
  { label: string; tone: Tone; icon: typeof CalendarCheck2 }
> = {
  submitted: { label: "Registrada", tone: "forest", icon: CalendarCheck2 },
  pending: { label: "Pendente", tone: "honey", icon: CircleDashed },
  unavailable: { label: "Indisponível", tone: "sage", icon: CalendarX2 },
};

function emptyEntriesMessage(status: AvailabilityStatus): string {
  if (status === "pending") return "Aguardando o registro de disponibilidade.";
  if (status === "unavailable") return "Declarou indisponibilidade para esta semana.";
  return "Nenhum horário ofertado.";
}

function AvailabilityEntryItem({ entry }: { entry: CoordinationAvailabilityEntry }) {
  return (
    <li className="rounded-2xl border border-line bg-paper px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-forest-900">
            {formatDayLong(new Date(entry.startsAt))}
          </p>
          <p className="mt-1 text-sm text-ink-600">
            {formatTimeRange(entry.startsAt, entry.endsAt)} ·{" "}
            {entry.location?.name ?? "Local não informado"}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone={entry.kind === "unavailable" ? "clay" : "sage"}>
            {entry.kind === "unavailable" ? "Indisponibilidade" : "Horário ofertado"}
          </Badge>
          {entry.isCurrent ? null : <Badge tone="sand">Histórico</Badge>}
          {entry.convertedSessionId ? (
            <Badge tone="lavender" icon={Link2}>
              Convertida em sessão
            </Badge>
          ) : null}
        </div>
      </div>
      {entry.note ? (
        <p className="mt-2 text-sm text-ink-600">
          <span className="font-semibold text-forest-900">Observação: </span>
          {entry.note}
        </p>
      ) : null}
    </li>
  );
}

function InstructorAvailabilityCard({
  instructor,
}: {
  instructor: CoordinationInstructorAvailability;
}) {
  const meta = availabilityMeta[instructor.status];
  const StatusIcon = meta.icon;
  const current = instructor.entries.filter((entry) => entry.isCurrent);
  const history = instructor.entries.filter((entry) => !entry.isCurrent);

  return (
    <Card as="li" className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-full bg-sage-100 text-forest-800">
            <StatusIcon className="size-5" aria-hidden />
          </span>
          <div>
            <p className="font-semibold text-forest-900">{instructor.name}</p>
            <p className="text-sm text-ink-600">
              {instructor.submittedAt
                ? `Registrou em ${formatDateTime(instructor.submittedAt)}`
                : "Ainda não registrou"}
            </p>
          </div>
        </div>
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </div>

      {instructor.note ? (
        <p className="rounded-2xl bg-sand-50 px-4 py-3 text-sm text-ink-700">
          <span className="font-semibold text-forest-900">Observação: </span>
          {instructor.note}
        </p>
      ) : null}

      {instructor.entries.length === 0 ? (
        <p className="text-sm text-ink-600">{emptyEntriesMessage(instructor.status)}</p>
      ) : current.length === 0 ? (
        <p className="text-sm text-ink-600">Nenhuma oferta vigente para esta semana.</p>
      ) : null}

      {current.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-600">
            Ofertas vigentes
          </p>
          <ul className="space-y-2">
            {current.map((entry) => (
              <AvailabilityEntryItem key={entry.id} entry={entry} />
            ))}
          </ul>
        </div>
      ) : null}

      {history.length > 0 ? (
        <div className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-ink-600">
            Histórico (não vigente)
          </p>
          <ul className="space-y-2">
            {history.map((entry) => (
              <AvailabilityEntryItem key={entry.id} entry={entry} />
            ))}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}

/** Fase local da criação do ciclo, sempre vinculada a uma semana. */
type CreatePhase = "idle" | "creating" | "syncing" | "ready" | "stale";

interface CreateOperation {
  week: string;
  phase: CreatePhase;
  error: ApiError | null;
}

interface CoordinationAvailabilitiesProps {
  week: string;
  data?: WeekAvailabilities;
  error?: ApiError;
  loading: boolean;
  refreshing: boolean;
  onRetry: () => void;
  /**
   * Recarrega o ciclo e as disponibilidades da semana. Resolve `true` quando os
   * dados foram atualizados; `false` (ou uma rejeição) sinaliza falha. Nunca
   * cria o ciclo — a criação continua sendo uma ação explícita.
   */
  onRefresh?: () => Promise<boolean>;
}

export function CoordinationAvailabilities({
  week,
  data,
  error,
  loading,
  refreshing,
  onRetry,
  onRefresh,
}: CoordinationAvailabilitiesProps) {
  const [operation, setOperation] = useState<CreateOperation | null>(null);
  // Sempre a semana do render atual: respostas atrasadas de outra semana são
  // descartadas em vez de vazar para o estado da semana selecionada.
  const weekRef = useRef(week);
  useEffect(() => {
    weekRef.current = week;
  }, [week]);

  const current = operation?.week === week ? operation : null;
  const phase: CreatePhase = current?.phase ?? "idle";
  const createError = current?.error ?? null;
  const creating = phase === "creating";
  const syncing = phase === "syncing";
  // A partir de "syncing" o POST já foi confirmado: o ciclo existe.
  const confirmed = syncing || phase === "ready" || phase === "stale";

  const total = data?.instructors.length ?? 0;
  const registered = data?.instructors.filter((item) => item.status !== "pending").length ?? 0;
  const hasCycle = Boolean(data?.cycleId) || confirmed;
  const phaseLabel = cyclePhaseLabel(data?.cyclePhase);

  /**
   * Atualiza apenas os dados (nunca repete o POST). Quando a atualização falha,
   * a operação fica em `stale` para exibir a recuperação com "Tentar atualizar".
   */
  async function syncData(target: string) {
    setOperation({ week: target, phase: "syncing", error: null });
    let refreshed = true;
    if (onRefresh) {
      try {
        refreshed = (await onRefresh()) !== false;
      } catch {
        refreshed = false;
      }
    }
    if (weekRef.current !== target) return;
    setOperation({ week: target, phase: refreshed ? "ready" : "stale", error: null });
  }

  async function handleCreateCycle() {
    if (creating || syncing) return;
    const target = week;
    setOperation({ week: target, phase: "creating", error: null });
    try {
      await api.coordination.createCycle({ weekStart: target });
    } catch (requestError) {
      if (weekRef.current !== target) return;
      // O POST falhou: o ciclo não foi criado e a criação pode ser tentada de novo.
      setOperation({ week: target, phase: "idle", error: toApiError(requestError) });
      return;
    }
    if (weekRef.current !== target) return;
    // O ciclo foi criado: agora só falta atualizar os dados exibidos.
    await syncData(target);
  }

  async function handleRetryRefresh() {
    if (syncing) return;
    await syncData(week);
  }

  return (
    <section aria-labelledby="disponibilidades-ministrantes" className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="disponibilidades-ministrantes" className="font-display text-2xl text-forest-900">
            Disponibilidades dos ministrantes
          </h2>
          <p className="mt-1 text-sm text-ink-600">
            Horários ofertados e situação de cada ministrante na semana selecionada.
          </p>
        </div>
        {data ? (
          <p className="text-sm font-semibold text-ink-700">
            {registered} de {total} registraram
          </p>
        ) : null}
      </div>

      {phase === "stale" ? (
        <Alert
          tone="warning"
          title="Ciclo criado, mas os dados não foram atualizados"
          action={
            <Button
              variant="secondary"
              onClick={handleRetryRefresh}
              icon={<RefreshCw className="size-4" aria-hidden />}
            >
              Tentar atualizar
            </Button>
          }
        >
          O ciclo desta semana foi criado, mas não foi possível carregar as disponibilidades
          atualizadas. Esta ação repete apenas a atualização dos dados; o ciclo não é criado
          novamente.
        </Alert>
      ) : error && phase !== "syncing" ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : loading || !data ? (
        <LoadingBlock rows={2} label="Carregando disponibilidades…" />
      ) : (
        <>
          {refreshing ? (
            <p role="status" className="flex items-center gap-2 text-sm text-ink-600">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Atualizando disponibilidades…
            </p>
          ) : null}

          <Card
            tone={hasCycle ? "sage" : "sand"}
            className="flex flex-wrap items-center justify-between gap-4"
          >
            <div>
              <p className="eyebrow">Ciclo da semana</p>
              <p className="mt-1 font-display text-xl text-forest-900">
                {hasCycle ? "Ciclo criado" : "Ciclo ainda não criado"}
              </p>
              <p className="mt-1 max-w-2xl text-sm text-ink-600">
                {hasCycle
                  ? phaseLabel
                    ? `Fase atual: ${phaseLabel}.`
                    : "O ciclo existe, mas a fase não foi informada."
                  : "A criação do ciclo é uma ação explícita. Nenhum ciclo é criado automaticamente ao abrir ou atualizar a tela."}
              </p>
            </div>
            {hasCycle ? (
              <Badge tone="forest" icon={CheckCircle2}>
                Ciclo ativo
              </Badge>
            ) : (
              <Button
                onClick={handleCreateCycle}
                loading={creating}
                icon={<Plus className="size-4" aria-hidden />}
              >
                Criar ciclo da semana
              </Button>
            )}
          </Card>

          {createError ? (
            <Alert tone="danger" title="Não foi possível criar o ciclo">
              {createError.message}
            </Alert>
          ) : null}

          {phase === "ready" ? (
            <Alert tone="success" title="Ciclo da semana disponível">
              O ciclo foi criado (ou já existia) e as disponibilidades agora podem ser consultadas.
            </Alert>
          ) : null}

          {total > 0 ? (
            <div className="space-y-2">
              <div
                role="progressbar"
                aria-label="Ministrantes que registraram disponibilidade"
                aria-valuemin={0}
                aria-valuemax={total}
                aria-valuenow={registered}
                className="h-2 overflow-hidden rounded-full bg-sand-200"
              >
                <div
                  className="h-full rounded-full bg-sage-500 transition-[width] duration-500"
                  style={{ width: total ? `${(registered / total) * 100}%` : "0%" }}
                />
              </div>
            </div>
          ) : null}

          {data.instructors.length === 0 ? (
            <EmptyState
              icon={UsersRound}
              title="Nenhum ministrante cadastrado"
              description="Não há ministrantes ativos para esta semana."
            />
          ) : (
            <ul className="space-y-4">
              {data.instructors.map((instructor) => (
                <InstructorAvailabilityCard
                  key={instructor.instructorId}
                  instructor={instructor}
                />
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
