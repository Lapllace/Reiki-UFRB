"use client";

import { useMemo, useState } from "react";
import { CalendarOff, Users } from "lucide-react";
import { InstructorLine, LocationLine, NoticeList } from "@/components/agenda/session-parts";
import { SessionStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CapacityMeter } from "@/components/ui/capacity-meter";
import { CheckField } from "@/components/ui/form";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { formatDayLong, formatTime, formatTimeRange, localDateKey } from "@/lib/dates";
import { useResource } from "@/lib/hooks/use-resource";
import type { Session } from "@/lib/types";
import { RosterDialog } from "./instructor-sessions";
import { useWeekSelection, WeekSwitcher } from "./week-switcher";

export function CoordinationSessions() {
  const { user } = useAuth();
  const [selected, setSelected] = useState<string | null>(null);
  const [onlyExtra, setOnlyExtra] = useState(false);
  const [onlyAttention, setOnlyAttention] = useState(false);
  const [rosterFor, setRosterFor] = useState<Session | null>(null);
  const [rosterOpen, setRosterOpen] = useState(false);
  const { current, week } = useWeekSelection(selected);

  const { data, error, loading, refreshing, reload } = useResource(
    user && week ? `coord-sessions:${user.id}:${week}` : null,
    (signal) => api.coordination.listSessions(week as string, signal),
  );

  const sessions = useMemo(
    () =>
      (data?.sessions ?? [])
        .filter((session) => !onlyExtra || session.isExtra)
        .filter(
          (session) =>
            !onlyAttention ||
            ["uncovered", "needs_cover", "cancelled"].includes(session.status),
        )
        .sort((a, b) => a.startsAt.localeCompare(b.startsAt)),
    [data, onlyExtra, onlyAttention],
  );

  const grouped = useMemo(() => {
    const map = new Map<string, Session[]>();
    for (const session of sessions) {
      const key = localDateKey(session.startsAt);
      map.set(key, [...(map.get(key) ?? []), session]);
    }
    return [...map.entries()];
  }, [sessions]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Coordenação"
        title="Sessões, vagas e inscrições"
        description="Consulte todas as sessões da semana, a ocupação e as inscrições. Sessões extras e com alterações podem ser filtradas."
      />
      <div className="flex flex-wrap items-center justify-between gap-4">
        <WeekSwitcher week={week} current={current} onChange={setSelected} />
        {refreshing ? <span className="text-sm text-ink-600">Atualizando…</span> : null}
      </div>

      <fieldset className="grid gap-3 sm:grid-cols-2">
        <legend className="sr-only">Filtros</legend>
        <CheckField
          label="Somente sessões extras"
          description="Criadas fora do ciclo regular."
          checked={onlyExtra}
          onChange={(event) => setOnlyExtra(event.target.checked)}
        />
        <CheckField
          label="Somente sessões que exigem atenção"
          description="Canceladas, sem ministrante ou aguardando cobertura."
          checked={onlyAttention}
          onChange={(event) => setOnlyAttention(event.target.checked)}
        />
      </fieldset>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading || !data ? (
        <LoadingBlock rows={3} label="Carregando sessões…" />
      ) : !data.published || data.sessions.length === 0 ? (
        <EmptyState
          icon={CalendarOff}
          title="Nenhuma sessão nesta semana"
          description="A agenda desta semana ainda não foi publicada ou não possui sessões."
        />
      ) : sessions.length === 0 ? (
        <EmptyState
          icon={CalendarOff}
          title="Nenhuma sessão corresponde aos filtros"
          description="Desative um filtro para ver mais sessões."
        />
      ) : (
        <div className="space-y-8">
          {grouped.map(([key, items]) => (
            <section key={key} aria-labelledby={`dia-${key}`}>
              <h2 id={`dia-${key}`} className="capitalize-first font-display text-xl text-forest-900">
                {formatDayLong(new Date(items[0].startsAt))}
              </h2>
              <ul className="mt-4 space-y-3">
                {items.map((session) => (
                  <li
                    key={session.id}
                    className={cn(
                      "grid gap-4 rounded-(--radius-card) border bg-paper p-5 shadow-soft md:grid-cols-[8rem_1fr_14rem_auto] md:items-center",
                      session.status === "cancelled" || session.status === "uncovered" ? "border-clay-200" : "border-line",
                    )}
                  >
                    <div>
                      <p className="font-display text-2xl text-forest-900">{formatTime(session.startsAt)}</p>
                      <p className="text-sm text-ink-600">{formatTimeRange(session.startsAt, session.endsAt)}</p>
                    </div>
                    <div className="space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <SessionStatusBadge status={session.status} />
                        {session.isExtra ? (
                          <span className="text-xs font-semibold uppercase tracking-wider text-lavender-700">
                            Sessão extra
                          </span>
                        ) : null}
                      </div>
                      <LocationLine session={session} />
                      <InstructorLine session={session} />
                      <NoticeList notices={session.notices} className="pt-1" />
                    </div>
                    <CapacityMeter
                      capacity={session.capacity}
                      confirmed={session.confirmedCount}
                      waitlist={session.waitlistCount}
                    />
                    <Button
                      variant="secondary"
                      size="sm"
                      icon={<Users className="size-4" aria-hidden />}
                      onClick={() => {
                        setRosterFor(session);
                        setRosterOpen(true);
                      }}
                    >
                      Inscrições
                    </Button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <RosterDialog
        sessionId={rosterFor?.id ?? null}
        title={
          rosterFor
            ? `${formatDayLong(new Date(rosterFor.startsAt))}, ${formatTime(rosterFor.startsAt)} · ${rosterFor.location.name}`
            : ""
        }
        scope="coordination"
        open={rosterOpen}
        onClose={() => setRosterOpen(false)}
      />
    </div>
  );
}
