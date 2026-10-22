"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarOff, CalendarSearch, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import {
  addWeeks,
  formatDayMonth,
  formatTime,
  formatWeekRange,
  localDateKey,
  parseISODate,
  startOfWeek,
  toISODate,
  weekdayAbbr,
  weekdayName,
  weekDays,
} from "@/lib/dates";
import { plural } from "@/lib/format";
import { useNow } from "@/lib/hooks/use-now";
import { useResource } from "@/lib/hooks/use-resource";
import type { Session } from "@/lib/types";
import { SessionCard } from "./session-card";
import { SessionDialog } from "./session-dialog";

const NOTICE_KINDS = new Set(["cancelled", "instructor_changed", "reallocation", "needs_cover"]);

export function AgendaView() {
  const { state: auth, user } = useAuth();
  const now = useNow();
  const [selectedWeek, setSelectedWeek] = useState<string | null>(null);
  const [locationFilter, setLocationFilter] = useState<string>("all");
  const [dialog, setDialog] = useState<{ session: Session; open: boolean } | null>(null);

  const currentWeek = now ? toISODate(startOfWeek(now)) : null;
  const weekStart = selectedWeek ?? currentWeek;
  const authReady = auth.status !== "loading";

  const { data, error, loading, refreshing, reload } = useResource(
    weekStart && authReady ? `agenda:${weekStart}:${user?.id ?? "anon"}` : null,
    (signal) => api.sessions.listWeek(weekStart as string, signal),
  );

  const days = useMemo(() => (weekStart ? weekDays(weekStart) : []), [weekStart]);
  const todayKey = now ? toISODate(now) : null;

  const locations = useMemo(() => {
    const map = new Map<string, string>();
    data?.sessions.forEach((session) => map.set(session.location.id, session.location.name));
    return [...map.entries()].map(([id, name]) => ({ id, name }));
  }, [data]);

  const filtered = useMemo(
    () =>
      (data?.sessions ?? []).filter(
        (session) => locationFilter === "all" || session.location.id === locationFilter,
      ),
    [data, locationFilter],
  );

  const byDay = useMemo(() => {
    const map = new Map<string, Session[]>();
    for (const session of filtered) {
      const key = localDateKey(session.startsAt);
      map.set(key, [...(map.get(key) ?? []), session].sort((a, b) => a.startsAt.localeCompare(b.startsAt)));
    }
    return map;
  }, [filtered]);

  const noticeSessions = useMemo(
    () => (data?.sessions ?? []).filter((session) => session.notices?.some((notice) => NOTICE_KINDS.has(notice.kind))),
    [data],
  );

  function goTo(week: string) {
    setSelectedWeek(week);
    setLocationFilter("all");
  }

  const isCurrent = weekStart !== null && weekStart === currentWeek;

  return (
    <div>
      {/* Navegação entre semanas */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2" role="group" aria-label="Navegar entre semanas">
          <Button
            variant="secondary"
            size="sm"
            className="size-11 px-0!"
            aria-label="Semana anterior"
            disabled={!weekStart}
            onClick={() => weekStart && goTo(addWeeks(weekStart, -1))}
          >
            <ChevronLeft className="size-5" aria-hidden />
          </Button>
          <div className="min-w-0 flex-1 px-2 text-center sm:min-w-72">
            <p className="eyebrow text-xs sm:text-sm">{isCurrent ? "Esta semana" : "Semana"}</p>
            <p className="mt-1 font-display text-lg text-forest-900 sm:text-2xl" aria-live="polite">
              {weekStart ? formatWeekRange(weekStart) : "Carregando…"}
            </p>
          </div>
          <Button
            variant="secondary"
            size="sm"
            className="size-11 px-0!"
            aria-label="Próxima semana"
            disabled={!weekStart}
            onClick={() => weekStart && goTo(addWeeks(weekStart, 1))}
          >
            <ChevronRight className="size-5" aria-hidden />
          </Button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {!isCurrent && currentWeek ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => goTo(currentWeek)}
              icon={<RotateCcw className="size-4" aria-hidden />}
            >
              Voltar para esta semana
            </Button>
          ) : null}
          {refreshing ? <span className="text-sm text-ink-600">Atualizando…</span> : null}
        </div>
      </div>

      {/* Filtro por local */}
      {locations.length > 1 ? (
        <div className="mt-3" role="group" aria-label="Filtrar por local">
          <div className="scroll-hidden overflow-x-auto px-5 sm:px-0">
            <div className="flex gap-2 sm:flex-wrap">
              {[{ id: "all", name: "Todos os locais" }, ...locations].map((location) => {
                const active = locationFilter === location.id;
                return (
                  <button
                    key={location.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setLocationFilter(location.id)}
                    className={cn(
                      "min-h-10 shrink-0 whitespace-nowrap rounded-full border px-4 py-2 text-sm font-semibold transition-colors sm:min-h-11 sm:px-5",
                      active
                        ? "border-forest-700 bg-forest-700 text-ivory"
                        : "border-line-strong bg-paper text-ink-700 hover:border-forest-300",
                    )}
                  >
                    {location.name}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      ) : null}

      {/* Conteúdo */}
      <div className="mt-4">
        {error ? (
          <ErrorState
            error={error}
            onRetry={reload}
            action={
              error.kind === "unauthenticated" ? (
                <ButtonLink href="/entrar?next=/agenda">Entrar</ButtonLink>
              ) : undefined
            }
          />
        ) : loading || !weekStart || !authReady ? (
          <LoadingBlock rows={3} label="Carregando a agenda da semana…" />
        ) : !data || !data.published || data.sessions.length === 0 ? (
          <EmptyState
            icon={CalendarOff}
            title="Ainda não há horários nesta semana"
            description="A coordenação publica a agenda semana a semana. Volte em breve ou veja outra semana."
            action={
              <div className="flex flex-wrap justify-center gap-3">
                {currentWeek && !isCurrent ? (
                  <Button variant="secondary" onClick={() => goTo(currentWeek)}>
                    Voltar para esta semana
                  </Button>
                ) : null}
                <Button variant="secondary" onClick={() => goTo(addWeeks(weekStart, 1))}>
                  Ver a próxima semana
                </Button>
              </div>
            }
          />
        ) : (
          <>
            {noticeSessions.length > 0 ? (
              <Alert tone="warning" title="Há avisos para esta semana" className="mb-8">
                <ul className="mt-1 list-disc space-y-1 pl-5">
                  {noticeSessions.slice(0, 4).map((session) => (
                    <li key={session.id}>
                      <span className="capitalize-first">
                        {weekdayName(new Date(session.startsAt))}
                      </span>
                      , {formatTime(session.startsAt)} ({session.location.name}):{" "}
                      {session.notices?.find((notice) => NOTICE_KINDS.has(notice.kind))?.message}
                    </li>
                  ))}
                </ul>
                {noticeSessions.length > 4 ? (
                  <p className="mt-2">E mais {plural(noticeSessions.length - 4, "aviso")} nos cartões abaixo.</p>
                ) : null}
              </Alert>
            ) : null}

            {/* Atalhos de dia */}
            <nav
              aria-label="Ir para um dia da semana"
              className="scroll-hidden sticky top-18 z-30 -mx-5 mb-8 overflow-x-auto border-b border-line bg-ivory/95 px-5 py-3 sm:mx-0 sm:px-0"
            >
              <ul className="flex min-w-max gap-2 sm:min-w-0 sm:justify-between">
                {days.map((key) => {
                  const date = parseISODate(key);
                  const count = byDay.get(key)?.length ?? 0;
                  const isToday = key === todayKey;
                  return (
                    <li key={key} className="sm:flex-1">
                      <a
                        href={`#dia-${key}`}
                        className={cn(
                          "flex min-h-14 min-w-16 flex-col items-center justify-center rounded-2xl px-3 text-center transition-colors",
                          count > 0 ? "hover:bg-sage-100" : "text-ink-500",
                          isToday && "bg-sage-100",
                        )}
                      >
                        <span className="text-xs font-semibold uppercase tracking-wider text-ink-600">
                          {weekdayAbbr(date)}
                        </span>
                        <span className="font-display text-xl leading-tight text-forest-900">
                          {date.getDate()}
                        </span>
                        <span className="sr-only">
                          {count === 0 ? "sem sessões" : plural(count, "sessão", "sessões")}
                        </span>
                        <span
                          aria-hidden
                          className={cn(
                            "mt-0.5 h-1 w-4 rounded-full",
                            count > 0 ? "bg-forest-500" : "bg-transparent",
                          )}
                        />
                      </a>
                    </li>
                  );
                })}
              </ul>
            </nav>

            {filtered.length === 0 ? (
              <EmptyState
                icon={CalendarSearch}
                title="Nenhuma sessão neste local"
                description="Escolha outro local ou veja todos."
                action={
                  <Button variant="secondary" onClick={() => setLocationFilter("all")}>
                    Mostrar todos os locais
                  </Button>
                }
              />
            ) : (
              <div className="space-y-6">
                {days.map((key) => {
                  const sessions = byDay.get(key) ?? [];
                  const date = parseISODate(key);
                  const isToday = key === todayKey;
                  return (
                    <section
                      key={key}
                      id={`dia-${key}`}
                      aria-labelledby={`titulo-${key}`}
                      className="grid gap-4 sm:grid-cols-[8rem_1fr] sm:gap-8"
                    >
                      <header className="flex items-baseline gap-3 sm:block sm:pt-1">
                        <p className="font-display text-5xl leading-none text-forest-800 sm:text-6xl">
                          {date.getDate()}
                        </p>
                        <div className="sm:mt-2">
                          <h2 id={`titulo-${key}`} className="capitalize-first text-base font-bold text-forest-900">
                            {weekdayName(date)}
                          </h2>
                          <p className="text-sm text-ink-600">{formatDayMonth(date)}</p>
                          {isToday ? (
                            <span className="mt-1.5 inline-block rounded-full bg-forest-700 px-2.5 py-0.5 text-xs font-semibold text-ivory">
                              Hoje
                            </span>
                          ) : null}
                        </div>
                      </header>

                      {sessions.length === 0 ? (
                        <p className="rounded-2xl border border-dashed border-line-strong px-5 py-4 text-ink-600 sm:self-start">
                          Sem sessões neste dia.
                        </p>
                      ) : (
                        <div className="grid gap-4 md:grid-cols-2">
                          {sessions.map((session) => (
                            <SessionCard
                              key={session.id}
                              session={session}
                              onOpen={(item) => setDialog({ session: item, open: true })}
                            />
                          ))}
                        </div>
                      )}
                    </section>
                  );
                })}
              </div>
            )}

            {!user && auth.status === "anonymous" ? (
              <p className="mt-12 rounded-2xl bg-sand-50 px-5 py-4 text-sm text-ink-700">
                Para se inscrever, <Link href="/entrar?next=/agenda" className="font-semibold text-forest-700 underline underline-offset-4">entre na sua conta</Link>.
              </p>
            ) : null}
          </>
        )}
      </div>

      <SessionDialog
        session={
          dialog
            ? (data?.sessions.find((session) => session.id === dialog.session.id) ?? dialog.session)
            : null
        }
        open={dialog?.open ?? false}
        onClose={() => setDialog((current) => (current ? { ...current, open: false } : null))}
        onChanged={reload}
      />
    </div>
  );
}
