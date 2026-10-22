"use client";

import { useMemo } from "react";
import { CheckCircle2, HandHelping, SearchX, UserRoundSearch } from "lucide-react";
import { LocationLine, WhenLine } from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { Badge, type Tone } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/dates";
import { useResource } from "@/lib/hooks/use-resource";
import type { CoverRequest, CoverRequestStatus } from "@/lib/types";

const meta: Record<CoverRequestStatus, { label: string; tone: Tone }> = {
  open: { label: "Convites em andamento", tone: "honey" },
  covered: { label: "Coberta", tone: "forest" },
  uncovered: { label: "Sem substituto", tone: "clay" },
};

function RequestCard({ request }: { request: CoverRequest }) {
  const status = meta[request.status];
  return (
    <article
      className={cn(
        "rounded-(--radius-card) border bg-paper p-5 shadow-soft sm:p-6",
        request.status === "uncovered" ? "border-clay-200" : "border-line",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-2">
          <WhenLine session={request.session} className="font-semibold text-forest-900" />
          <LocationLine session={request.session} />
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <dl className="mt-5 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-ink-600">Ministrante que cancelou</dt>
          <dd className="text-ink-900">{request.originalInstructor?.name ?? "—"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink-600">Motivo informado</dt>
          <dd className="text-ink-900">{request.reason ?? "Não informado"}</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink-600">Ministrantes convidados</dt>
          <dd className="text-ink-900">{request.invitedCount}</dd>
        </div>
        <div>
          <dt className="font-semibold text-ink-600">Solicitação enviada</dt>
          <dd className="text-ink-900">{formatDateTime(request.createdAt)}</dd>
        </div>
        {request.status === "covered" && request.coveredBy ? (
          <div className="sm:col-span-2">
            <dt className="font-semibold text-ink-600">Assumida por (primeiro aceite)</dt>
            <dd className="flex items-center gap-2 text-ink-900">
              <CheckCircle2 className="size-4 text-forest-600" aria-hidden />
              {request.coveredBy.name}
              {request.resolvedAt ? ` · ${formatDateTime(request.resolvedAt)}` : ""}
            </dd>
          </div>
        ) : null}
      </dl>
    </article>
  );
}

export function CoordinationCovers() {
  const { user } = useAuth();
  const { data, error, loading, refreshing, reload } = useResource(
    user ? `cover-requests:${user.id}` : null,
    (signal) => api.coordination.listCoverRequests(signal),
    { refreshInterval: 30_000 },
  );

  const groups = useMemo(() => {
    const all = data ?? [];
    return {
      open: all.filter((item) => item.status === "open"),
      uncovered: all.filter((item) => item.status === "uncovered"),
      covered: all.filter((item) => item.status === "covered"),
    };
  }, [data]);

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Coordenação"
        title="Solicitações de cobertura"
        description="Acompanhe os convites enviados aos ministrantes elegíveis e as sessões que ainda não têm substituto."
      />
      {refreshing ? <p className="-mt-6 text-sm text-ink-600">Atualizando…</p> : null}

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={3} label="Carregando solicitações…" />
      ) : (
        <>
          <section aria-labelledby="sem-substituto" className="space-y-4">
            <h2 id="sem-substituto" className="font-display text-2xl text-forest-900">
              Sessões sem substituto ({groups.uncovered.length})
            </h2>
            {groups.uncovered.length === 0 ? (
              <EmptyState icon={SearchX} title="Nenhuma sessão sem substituto" description="Todas as sessões com cancelamento têm cobertura ou convites em andamento." />
            ) : (
              <>
                <Alert tone="danger">
                  Estas sessões não têm ministrante. Considere a reorganização dos participantes.
                </Alert>
                {groups.uncovered.map((request) => (
                  <RequestCard key={request.id} request={request} />
                ))}
              </>
            )}
          </section>

          <section aria-labelledby="em-andamento" className="space-y-4">
            <h2 id="em-andamento" className="font-display text-2xl text-forest-900">
              Convites em andamento ({groups.open.length})
            </h2>
            {groups.open.length === 0 ? (
              <EmptyState icon={UserRoundSearch} title="Nenhuma solicitação aberta" description="Quando um ministrante cancelar, a solicitação aparecerá aqui." />
            ) : (
              groups.open.map((request) => <RequestCard key={request.id} request={request} />)
            )}
          </section>

          <section aria-labelledby="resolvidas" className="space-y-4">
            <h2 id="resolvidas" className="font-display text-2xl text-forest-900">
              Coberturas resolvidas ({groups.covered.length})
            </h2>
            {groups.covered.length === 0 ? (
              <EmptyState icon={HandHelping} title="Nenhuma cobertura concluída ainda" />
            ) : (
              groups.covered.map((request) => <RequestCard key={request.id} request={request} />)
            )}
          </section>
        </>
      )}
    </div>
  );
}
