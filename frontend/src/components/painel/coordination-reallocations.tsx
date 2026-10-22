"use client";

import { useMemo, useState } from "react";
import { Repeat2, Users } from "lucide-react";
import { LocationLine, WhenLine } from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

import { cn } from "@/lib/cn";
import { formatDateTime, formatDayLong, formatTimeRange } from "@/lib/dates";
import { plural } from "@/lib/format";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { Reallocation, ReallocationStatus } from "@/lib/types";

const statusMeta: Record<ReallocationStatus, { label: string; tone: Tone }> = {
  pending: { label: "Aguardando decisão", tone: "honey" },
  applied: { label: "Aplicada", tone: "forest" },
  dismissed: { label: "Dispensada", tone: "sand" },
};

type Pending = { kind: "apply" | "dismiss"; item: Reallocation } | null;

export function CoordinationReallocations() {
  const toast = useToast();
  const { data, error, loading, reload } = useAccountResource(
    "reallocations",
    (signal) => api.coordination.listReallocations(signal),
  );
  const [choices, setChoices] = useState<Record<string, string>>({});
  const [pending, setPending] = useState<Pending>(null);

  const groups = useMemo(() => {
    const all = data ?? [];
    return {
      pending: all.filter((item) => item.status === "pending"),
      done: all.filter((item) => item.status !== "pending"),
    };
  }, [data]);

  async function confirm() {
    if (!pending) return;
    const { kind, item } = pending;
    if (kind === "apply") {
      const target = choices[item.id];
      await api.coordination.applyReallocation(item.id, { targetSessionId: target });
      toast.push({ tone: "success", title: "Reorganização aplicada", message: "O sistema confirmou a nova sessão para os participantes." });
    } else {
      await api.coordination.dismissReallocation(item.id);
      toast.push({ tone: "info", title: "Reorganização dispensada", message: "A decisão foi registrada no histórico." });
    }
    setPending(null);
    reload();
  }

  const chosenSession = pending?.kind === "apply" ? pending.item.candidateSessions.find((s) => s.id === choices[pending.item.id]) : undefined;

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Coordenação"
        title="Reorganização de participantes"
        description="Quando uma sessão deixa de acontecer, escolha uma sessão extra ou de uma semana futura para receber os participantes afetados."
      />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={2} label="Carregando reorganizações…" />
      ) : (
        <>
          <section aria-labelledby="pendentes" className="space-y-4">
            <h2 id="pendentes" className="font-display text-2xl text-forest-900">
              Aguardando decisão ({groups.pending.length})
            </h2>
            {groups.pending.length === 0 ? (
              <EmptyState icon={Repeat2} title="Nada para reorganizar" description="Quando houver participantes afetados por cancelamentos, eles aparecerão aqui." />
            ) : (
              groups.pending.map((item) => {
                const choice = choices[item.id];
                return (
                  <article key={item.id} className="rounded-(--radius-card) border border-honey-200 bg-paper p-5 shadow-soft sm:p-6">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <p className="font-semibold text-forest-900">{item.reason}</p>
                        <WhenLine session={item.originSession} />
                        <LocationLine session={item.originSession} />
                      </div>
                      <Badge tone="honey" icon={Users}>
                        {plural(item.participantCount, "participante")}
                      </Badge>
                    </div>

                    <fieldset className="mt-6">
                      <legend className="font-semibold text-forest-900">Destino sugerido pelo sistema</legend>
                      {item.candidateSessions.length === 0 ? (
                        <p className="mt-3 text-sm text-ink-600">Nenhuma sessão candidata foi sugerida.</p>
                      ) : (
                        <div className="mt-3 grid gap-3 sm:grid-cols-2">
                          {item.candidateSessions.map((session) => {
                            const free = session.capacity !== null && session.confirmedCount !== null ? session.capacity - session.confirmedCount : null;
                            const insufficient = free !== null && free < item.participantCount;
                            return (
                              <label
                                key={session.id}
                                className={cn(
                                  "flex min-h-16 cursor-pointer items-start gap-3 rounded-2xl border border-line-strong bg-paper p-4 transition-colors hover:border-forest-300 has-checked:border-forest-600 has-checked:bg-forest-50 has-focus-visible:ring-4 has-focus-visible:ring-forest-600/15",
                                  insufficient && "cursor-not-allowed opacity-60 hover:border-line-strong",
                                )}
                              >
                                <input
                                  type="radio"
                                  name={`destino-${item.id}`}
                                  className="mt-1 size-5 accent-forest-700"
                                  disabled={insufficient}
                                  checked={choice === session.id}
                                  onChange={() => setChoices((current) => ({ ...current, [item.id]: session.id }))}
                                />
                                <span className="text-sm">
                                  <span className="capitalize-first block font-semibold text-forest-900">
                                    {formatDayLong(new Date(session.startsAt))}
                                  </span>
                                  <span className="block text-ink-700">
                                    {formatTimeRange(session.startsAt, session.endsAt)} · {session.location.name}
                                    {session.isExtra ? " · extra" : ""}
                                  </span>
                                  <span className={cn("mt-1 block", insufficient ? "text-clay-700" : "text-ink-600")}>
                                    {free === null
                                      ? "Vagas não informadas"
                                      : insufficient
                                        ? `Apenas ${plural(free, "vaga")}: insuficiente`
                                        : `${plural(free, "vaga livre", "vagas livres")}`}
                                  </span>
                                </span>
                              </label>
                            );
                          })}
                        </div>
                      )}
                    </fieldset>

                    <div className="mt-6 flex flex-col gap-3 sm:flex-row">
                      <Button disabled={!choice} onClick={() => setPending({ kind: "apply", item })}>
                        Aplicar reorganização
                      </Button>
                      <Button variant="ghost" onClick={() => setPending({ kind: "dismiss", item })}>
                        Dispensar
                      </Button>
                    </div>
                  </article>
                );
              })
            )}
          </section>

          {groups.done.length > 0 ? (
            <section aria-labelledby="tratadas" className="space-y-4">
              <h2 id="tratadas" className="font-display text-2xl text-forest-900">
                Já tratadas
              </h2>
              <ul className="space-y-3">
                {groups.done.map((item) => (
                  <li key={item.id} className="flex flex-col gap-2 rounded-2xl border border-line bg-paper p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
                    <div>
                      <p className="font-semibold text-forest-900">{item.reason}</p>
                      <p className="text-sm text-ink-600">
                        {plural(item.participantCount, "participante")} · {formatDateTime(item.createdAt)}
                        {item.appliedTo
                          ? ` · destino: ${formatDayLong(new Date(item.appliedTo.startsAt))}, ${formatTimeRange(item.appliedTo.startsAt, item.appliedTo.endsAt)}`
                          : ""}
                      </p>
                    </div>
                    <Badge tone={statusMeta[item.status].tone}>{statusMeta[item.status].label}</Badge>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}

      <ConfirmDialog
        open={pending !== null}
        onClose={() => setPending(null)}
        title={pending?.kind === "apply" ? "Aplicar reorganização?" : "Dispensar reorganização?"}
        description={
          pending?.kind === "apply"
            ? "Os participantes afetados serão movidos para a sessão escolhida."
            : "Os participantes não serão movidos e a decisão ficará registrada."
        }
        confirmLabel={pending?.kind === "apply" ? "Aplicar" : "Dispensar"}
        tone={pending?.kind === "apply" ? "primary" : "danger"}
        onConfirm={confirm}
      >
        {chosenSession ? (
          <Alert tone="info">
            Destino: <strong className="capitalize-first">{formatDayLong(new Date(chosenSession.startsAt))}</strong>,{" "}
            {formatTimeRange(chosenSession.startsAt, chosenSession.endsAt)} · {chosenSession.location.name}. O sistema
            pode recusar se as vagas mudarem.
          </Alert>
        ) : null}
      </ConfirmDialog>
    </div>
  );
}
