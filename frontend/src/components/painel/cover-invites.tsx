"use client";

import { useMemo, useState } from "react";
import { HandHeart, MailX } from "lucide-react";
import { InstructorLine, LocationLine, NoticeList } from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CapacityMeter } from "@/components/ui/capacity-meter";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";

import { cn } from "@/lib/cn";
import { formatDateTime, formatDayLong, formatTime, formatTimeRange } from "@/lib/dates";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { AcceptCoverResult, CoverInvite, CoverInviteStatus } from "@/lib/types";

const statusMeta: Record<CoverInviteStatus, { label: string; tone: Tone }> = {
  pending: { label: "Aguardando sua resposta", tone: "honey" },
  accepted: { label: "Você assumiu a sessão", tone: "forest" },
  taken: { label: "Outro ministrante assumiu", tone: "sand" },
  declined: { label: "Você recusou o convite", tone: "sand" },
  expired: { label: "Convite expirado", tone: "sand" },
  withdrawn: { label: "Convite retirado", tone: "sand" },
};

export function useCoverInvites() {
  return useAccountResource(
    "cover-invites",
    (signal) => api.instructor.listCoverInvites(signal),
    { refreshInterval: 30_000 },
  );
}

export function CoverInvites() {
  const toast = useToast();
  const { data, error, loading, refreshing, reload } = useCoverInvites();
  const [target, setTarget] = useState<CoverInvite | null>(null);
  const [result, setResult] = useState<AcceptCoverResult | null>(null);

  const groups = useMemo(() => {
    const all = data ?? [];
    return {
      pending: all.filter((invite) => invite.status === "pending"),
      resolved: all.filter((invite) => invite.status !== "pending"),
    };
  }, [data]);

  async function accept() {
    if (!target) return;
    // A decisão é do servidor: só mostramos o desfecho que ele devolver.
    const outcome = await api.instructor.acceptCover(target.id);
    setResult(outcome);
    setTarget(null);
    if (outcome.outcome === "accepted") {
      toast.push({ tone: "success", title: "Sessão assumida", message: "O sistema confirmou o seu aceite." });
    }
    reload();
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ministrante"
        title="Convites de cobertura"
        description="Quando uma sessão perde o ministrante, todos os elegíveis recebem o convite. Quem tiver o aceite registrado primeiro pelo sistema assume a sessão."
      />

      {result ? (
        <Alert
          tone={result.outcome === "accepted" ? "success" : "warning"}
          title={
            result.outcome === "accepted"
              ? "Você assumiu a sessão"
              : result.outcome === "already_taken"
                ? "Outro ministrante aceitou primeiro"
                : "Este convite expirou"
          }
          onDismiss={() => setResult(null)}
        >
          {result.outcome === "accepted"
            ? result.invite.session
            ? `${formatDayLong(new Date(result.invite.session.startsAt))}, ${formatTime(result.invite.session.startsAt)} agora está na sua lista de sessões.`
            : "A sessão foi adicionada à sua lista de sessões."
            : result.outcome === "already_taken"
              ? "Outro ministrante teve o aceite registrado antes do seu. A sessão não ficou com você."
              : "O prazo para responder terminou e a sessão não pôde ser assumida."}
        </Alert>
      ) : null}

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={2} label="Carregando convites…" />
      ) : (
        <>
          <section aria-labelledby="pendentes" className="space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h2 id="pendentes" className="font-display text-2xl text-forest-900">
                Aguardando resposta ({groups.pending.length})
              </h2>
              {refreshing ? <span className="text-sm text-ink-600">Atualizando…</span> : null}
            </div>
            {groups.pending.length === 0 ? (
              <EmptyState
                icon={MailX}
                title="Nenhum convite pendente"
                description="Quando houver uma sessão precisando de cobertura, o convite aparecerá aqui."
              />
            ) : (
              groups.pending.map((invite) => (
                <InviteCard key={invite.id} invite={invite} onAccept={() => setTarget(invite)} />
              ))
            )}
          </section>

          {groups.resolved.length > 0 ? (
            <section aria-labelledby="resolvidos" className="space-y-4">
              <h2 id="resolvidos" className="font-display text-2xl text-forest-900">
                Anteriores
              </h2>
              {groups.resolved.map((invite) => (
                <InviteCard key={invite.id} invite={invite} />
              ))}
            </section>
          ) : null}
        </>
      )}

      <ConfirmDialog
        open={target !== null}
        onClose={() => setTarget(null)}
        title="Assumir esta sessão?"
        description="Ao aceitar, você se compromete a conduzir a sessão caso o sistema confirme o seu aceite."
        confirmLabel="Aceitar cobertura"
        cancelLabel="Agora não"
        onConfirm={accept}
      >
        {target ? (
          <div className="rounded-2xl bg-sand-50 p-4 text-ink-800">
            {target.session ? (
              <>
                <p className="capitalize-first font-semibold">
                  {formatDayLong(new Date(target.session.startsAt))}, {formatTimeRange(target.session.startsAt, target.session.endsAt)}
                </p>
                <p className="mt-1 text-sm">{target.session.location.name}</p>
              </>
            ) : <p className="text-sm">Sessão {target.sessionId ?? "não informada"}</p>}
          </div>
        ) : null}
        <p className="text-sm text-ink-600">
          Outros ministrantes também receberam este convite. O resultado final (você assumir ou
          outra pessoa ter aceitado antes) é definido pelo sistema e será exibido aqui.
        </p>
      </ConfirmDialog>
    </div>
  );
}

function InviteCard({ invite, onAccept }: { invite: CoverInvite; onAccept?: () => void }) {
  const { session } = invite;
  const meta = statusMeta[invite.status];
  const pending = invite.status === "pending";
  if (!session) {
    return (
      <article className="rounded-(--radius-card) border border-line bg-paper p-5 shadow-soft sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-ink-700">Sessão do convite: {invite.sessionId ?? "não informada"}</p>
          <Badge tone={meta.tone}>{meta.label}</Badge>
        </div>
      </article>
    );
  }
  return (
    <article
      className={cn(
        "rounded-(--radius-card) border bg-paper p-5 shadow-soft sm:p-6",
        pending ? "border-honey-200" : "border-line",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="capitalize-first font-display text-2xl text-forest-900">
            {formatDayLong(new Date(session.startsAt))}
          </h3>
          <p className="mt-1 text-lg text-ink-700">{formatTimeRange(session.startsAt, session.endsAt)}</p>
        </div>
        <Badge tone={meta.tone} icon={pending ? HandHeart : undefined}>
          {meta.label}
        </Badge>
      </div>
      <div className="mt-4 space-y-2">
        <LocationLine session={session} />
        <InstructorLine session={session} />
      </div>
      {session.location.address ? <p className="mt-2 text-sm text-ink-600">{session.location.address}</p> : null}
      <NoticeList notices={pending ? session.notices : undefined} className="mt-4" />
      {pending ? (
        <CapacityMeter
          className="mt-5 max-w-sm"
          capacity={session.capacity}
          confirmed={session.confirmedCount}
          waitlist={session.waitlistCount}
        />
      ) : null}
      <p className="mt-4 text-xs text-ink-500">
        Convite enviado em {formatDateTime(invite.createdAt)}
        {invite.status === "taken" ? " · assumida por outro ministrante" : ""}
      </p>
      {pending && onAccept ? (
        <div className="mt-5">
          <Button onClick={onAccept} icon={<HandHeart className="size-4" aria-hidden />}>
            Aceitar cobertura
          </Button>
        </div>
      ) : null}
    </article>
  );
}
