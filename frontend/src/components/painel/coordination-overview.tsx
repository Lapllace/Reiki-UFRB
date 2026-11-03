"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Check, UsersRound } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/section";
import { ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";

import { cn } from "@/lib/cn";
import { cyclePhaseIndex, cyclePhases } from "@/lib/cycle-phases";
import { formatDateTime } from "@/lib/dates";
import { plural } from "@/lib/format";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { WeeklyCycle } from "@/lib/types";
import { CoordinationAvailabilities } from "./coordination-availabilities";
import { useWeekSelection, WeekSwitcher } from "./week-switcher";

export function PhaseTracker({ cycle }: { cycle: WeeklyCycle }) {
  const active = cyclePhaseIndex(cycle.phase);
  return (
    <Card>
      <h2 className="font-display text-xl text-forest-900">Andamento do ciclo</h2>
      <ol className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cyclePhases.map((phase, index) => {
          const done = index < active;
          const current = index === active;
          return (
            <li
              key={phase.id}
              aria-current={current ? "step" : undefined}
              className={cn(
                "rounded-2xl border p-4",
                current ? "border-forest-500 bg-forest-50" : done ? "border-line bg-sand-50" : "border-dashed border-line-strong",
              )}
            >
              <span
                className={cn(
                  "grid size-8 place-items-center rounded-full text-xs font-bold",
                  current ? "bg-forest-700 text-ivory" : done ? "bg-sage-300 text-forest-900" : "bg-sand-100 text-ink-600",
                )}
              >
                {done ? <Check className="size-4" aria-hidden /> : index + 1}
              </span>
              <p className="mt-3 font-semibold text-forest-900">{phase.label}</p>
              <p className="mt-1 text-sm text-ink-600">
                {current ? "Etapa atual" : done ? "Concluída" : "Ainda não iniciada"}
              </p>
              {phase.id === "collecting_availability" && cycle.availabilityDeadline ? (
                <p className="mt-2 text-xs text-ink-600">Prazo: {formatDateTime(cycle.availabilityDeadline)}</p>
              ) : null}
              {phase.id === "enrollment_open" && cycle.enrollmentOpensAt ? (
                <p className="mt-2 text-xs text-ink-600">Abertura: {formatDateTime(cycle.enrollmentOpensAt)}</p>
              ) : null}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

export function CoordinationOverview() {
  const [selected, setSelected] = useState<string | null>(null);
  const { current, week } = useWeekSelection(selected);

  const {
    data,
    error,
    loading,
    reload,
    reloadAsync: reloadCycleAsync,
  } = useAccountResource(
    week ? `cycle:${week}` : null,
    (signal) => api.coordination.getCycle(week as string, signal),
  );

  const {
    data: availabilities,
    error: availabilitiesError,
    loading: availabilitiesLoading,
    refreshing: availabilitiesRefreshing,
    reload: reloadAvailabilities,
    reloadAsync: reloadAvailabilitiesAsync,
  } = useAccountResource(
    week ? `coord-availabilities:${week}` : null,
    (signal) => api.coordination.listAvailabilities(week as string, signal),
  );

  const reloadAll = async () => {
    const [cycleReloaded, availabilitiesReloaded] = await Promise.all([
      reloadCycleAsync(),
      reloadAvailabilitiesAsync(),
    ]);
    return cycleReloaded && availabilitiesReloaded;
  };

  const stats = data
    ? [
        {
          label: "Sessões",
          value: String(data.totals.sessions),
          href: "/coordenacao/sessoes",
        },
        {
          label: "Vagas ocupadas",
          value:
            data.totals.capacity === null || data.totals.confirmed === null
              ? "—"
              : `${data.totals.confirmed}/${data.totals.capacity}`,
          href: "/coordenacao/sessoes",
        },
        { label: "Na fila de espera", value: data.totals.waitlisted === null ? "—" : String(data.totals.waitlisted), href: "/coordenacao/sessoes" },
        { label: "Sem substituto", value: String(data.totals.uncovered), href: "/coordenacao/coberturas", alert: data.totals.uncovered > 0 },
        { label: "Coberturas em aberto", value: String(data.totals.openCoverRequests), href: "/coordenacao/coberturas" },
        { label: "Reorganizações pendentes", value: String(data.totals.pendingReallocations), href: "/coordenacao/reorganizacao" },
      ]
    : [];

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Coordenação"
        title="Visão geral dos ciclos"
        description="Acompanhe o andamento de cada semana, as disponibilidades dos ministrantes e a abertura das inscrições."
      />
      <WeekSwitcher week={week} current={current} onChange={setSelected} />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading || !data ? (
        <LoadingBlock rows={3} label="Carregando o ciclo da semana…" />
      ) : (
        <>
          {data.totals.uncovered > 0 ? (
            <Alert
              tone="danger"
              title={`${plural(data.totals.uncovered, "sessão", "sessões")} sem substituto`}
              action={
                <Link href="/coordenacao/coberturas" className="inline-flex items-center gap-1.5 text-sm font-semibold text-clay-700 underline underline-offset-4">
                  Ver coberturas <ArrowRight className="size-4" aria-hidden />
                </Link>
              }
            >
              Nenhum ministrante aceitou cobrir estas sessões até agora.
            </Alert>
          ) : null}
          {data.totals.pendingReallocations > 0 ? (
            <Alert
              tone="info"
              title={`${plural(data.totals.pendingReallocations, "reorganização", "reorganizações")} aguardando decisão`}
              action={
                <Link href="/coordenacao/reorganizacao" className="inline-flex items-center gap-1.5 text-sm font-semibold text-lavender-700 underline underline-offset-4">
                  Gerenciar reorganização <ArrowRight className="size-4" aria-hidden />
                </Link>
              }
            >
              Há participantes afetados por cancelamentos aguardando uma nova sessão.
            </Alert>
          ) : null}

          <PhaseTracker cycle={data} />

          <section aria-label="Indicadores da semana" className="grid grid-cols-2 gap-4 lg:grid-cols-3">
            {stats.map((stat) => (
              <Link
                key={stat.label}
                href={stat.href}
                className={cn(
                  "group rounded-(--radius-card) border bg-paper p-5 shadow-soft transition-shadow hover:shadow-lift",
                  stat.alert ? "border-clay-200 bg-clay-50/60" : "border-line",
                )}
              >
                <p className={cn("font-display text-4xl", stat.alert ? "text-clay-700" : "text-forest-800")}>
                  {stat.value}
                </p>
                <p className="mt-2 flex items-center justify-between gap-2 text-sm font-semibold text-ink-600">
                  {stat.label}
                  <ArrowRight className="size-4 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100" aria-hidden />
                </p>
              </Link>
            ))}
          </section>

          {week ? (
            <CoordinationAvailabilities
              key={week}
              week={week}
              data={availabilities}
              error={availabilitiesError}
              loading={availabilitiesLoading}
              refreshing={availabilitiesRefreshing}
              onRetry={reloadAvailabilities}
              onRefresh={reloadAll}
            />
          ) : null}

          <p className="flex items-center gap-2 text-sm text-ink-600">
            <UsersRound className="size-4" aria-hidden />
            Valores calculados pelo servidor para a semana selecionada.
          </p>
        </>
      )}
    </div>
  );
}
