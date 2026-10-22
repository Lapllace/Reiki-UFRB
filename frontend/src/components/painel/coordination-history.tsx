"use client";

import { useMemo, useState } from "react";
import {
  CalendarClock,
  CalendarPlus,
  CircleSlash,
  HandHelping,
  History,
  Repeat2,
  ShuffleIcon,
  UserCheck,
  type LucideIcon,
} from "lucide-react";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/dates";
import { useResource } from "@/lib/hooks/use-resource";
import type { AuditEventKind } from "@/lib/types";

const kinds: Record<AuditEventKind, { label: string; icon: LucideIcon; tone: string }> = {
  cycle: { label: "Ciclos", icon: CalendarClock, tone: "bg-sage-100 text-sage-700" },
  availability: { label: "Disponibilidade", icon: UserCheck, tone: "bg-sage-100 text-sage-700" },
  cover: { label: "Coberturas", icon: HandHelping, tone: "bg-honey-100 text-honey-700" },
  cancellation: { label: "Cancelamentos", icon: CircleSlash, tone: "bg-clay-100 text-clay-600" },
  extra_session: { label: "Sessões extras", icon: CalendarPlus, tone: "bg-lavender-100 text-lavender-700" },
  reallocation: { label: "Reorganização", icon: Repeat2, tone: "bg-lavender-100 text-lavender-700" },
  session_change: { label: "Alterações", icon: ShuffleIcon, tone: "bg-forest-100 text-forest-700" },
};

export function CoordinationHistory() {
  const { user } = useAuth();
  const [filter, setFilter] = useState<AuditEventKind | "all">("all");
  const { data, error, loading, reload } = useResource(
    user ? `events:${user.id}` : null,
    (signal) => api.coordination.listEvents(signal),
  );

  const events = useMemo(
    () => (data ?? []).filter((event) => filter === "all" || event.kind === filter).sort((a, b) => b.at.localeCompare(a.at)),
    [data, filter],
  );

  const available = useMemo(() => {
    const set = new Set((data ?? []).map((event) => event.kind));
    return (Object.keys(kinds) as AuditEventKind[]).filter((kind) => set.has(kind));
  }, [data]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Coordenação"
        title="Histórico de eventos"
        description="Cancelamentos, coberturas, sessões extras, reorganizações e outras alterações relevantes, da mais recente para a mais antiga."
      />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={4} label="Carregando histórico…" />
      ) : (data ?? []).length === 0 ? (
        <EmptyState icon={History} title="Nenhum evento registrado" description="Os eventos relevantes dos ciclos aparecerão aqui." />
      ) : (
        <>
          <div role="group" aria-label="Filtrar por tipo de evento" className="scroll-hidden -mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0">
            {(["all", ...available] as const).map((kind) => {
              const active = filter === kind;
              return (
                <button
                  key={kind}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(kind)}
                  className={cn(
                    "min-h-11 shrink-0 rounded-full border px-5 text-sm font-semibold transition-colors",
                    active ? "border-forest-700 bg-forest-700 text-ivory" : "border-line-strong bg-paper text-ink-700 hover:border-forest-300",
                  )}
                >
                  {kind === "all" ? "Todos" : kinds[kind].label}
                </button>
              );
            })}
          </div>

          {events.length === 0 ? (
            <EmptyState icon={History} title="Nenhum evento deste tipo" />
          ) : (
            <ol className="relative space-y-4 border-l-2 border-line pl-6 sm:pl-8">
              {events.map((event) => {
                const meta = kinds[event.kind];
                const Icon = meta.icon;
                return (
                  <li key={event.id} className="relative">
                    <span
                      className={cn(
                        "absolute -left-[2.9rem] top-1 grid size-9 place-items-center rounded-full border-4 border-ivory sm:-left-[3.4rem]",
                        meta.tone,
                      )}
                    >
                      <Icon className="size-4" aria-hidden />
                    </span>
                    <div className="rounded-2xl border border-line bg-paper p-4 shadow-soft sm:p-5">
                      <p className="text-ink-900">{event.description}</p>
                      <p className="mt-2 text-sm text-ink-600">
                        <span className="font-semibold">{meta.label}</span> · {formatDateTime(event.at)}
                        {event.actor ? ` · ${event.actor}` : ""}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
          )}
        </>
      )}
    </div>
  );
}
