"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowRight, CalendarRange, ClipboardList, UserRoundCheck } from "lucide-react";
import { InstructorLine, LocationLine, NoticeList } from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { Badge, SessionStatusBadge } from "@/components/ui/badge";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth/auth-context";
import { formatDayLong, formatTimeRange, formatWeekRange } from "@/lib/dates";
import { plural } from "@/lib/format";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import { useCoverInvites } from "./cover-invites";

export function InstructorHome() {
  const { user } = useAuth();
  const sessions = useAccountResource("instructor-sessions", (signal) =>
    api.instructor.listSessions(signal),
  );
  const invites = useCoverInvites();
  const availability = useAccountResource("availability-open", (signal) =>
    api.availability.get(null, signal),
  );

  const upcoming = useMemo(
    () => (sessions.data ?? []).filter((item) => item.session.status !== "completed" && item.session.status !== "cancelled").slice(0, 3),
    [sessions.data],
  );
  const pendingInvites = (invites.data ?? []).filter((invite) => invite.status === "pending");

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Ministrante"
        title={user ? `Olá, ${user.name.split(" ")[0]}.` : "Olá."}
        description="Suas próximas sessões, convites de cobertura e o registro de disponibilidade."
      />

      {pendingInvites.length > 0 ? (
        <Alert
          tone="warning"
          title={`${plural(pendingInvites.length, "convite")} de cobertura aguardando resposta`}
          action={
            <ButtonLink href="/ministrante/convites" size="sm" icon={<ArrowRight className="size-4" aria-hidden />}>
              Ver convites
            </ButtonLink>
          }
        >
          Sessões sem ministrante precisam de cobertura. O primeiro aceite registrado pelo sistema assume a sessão.
        </Alert>
      ) : null}

      <section aria-labelledby="disponibilidade" className="space-y-4">
        <h2 id="disponibilidade" className="font-display text-2xl text-forest-900">
          Disponibilidade da semana aberta
        </h2>
        {availability.error ? (
          <ErrorState error={availability.error} onRetry={availability.reload} />
        ) : availability.loading || !availability.data ? (
          <LoadingBlock rows={1} label="Carregando disponibilidade…" />
        ) : (
          <Card className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-display text-xl text-forest-900">
                Semana de {formatWeekRange(availability.data.weekStart)}
              </p>
              <div className="mt-2">
                {availability.data.status === "pending" ? (
                  <Badge tone="honey">Ainda não registrada</Badge>
                ) : availability.data.status === "submitted" ? (
                  <Badge tone="forest">Disponibilidade registrada</Badge>
                ) : (
                  <Badge tone="sage">Indisponibilidade declarada</Badge>
                )}
              </div>
            </div>
            <ButtonLink
              href="/ministrante/disponibilidade"
              variant={availability.data.status === "pending" ? "primary" : "secondary"}
              icon={<CalendarRange className="size-5" aria-hidden />}
            >
              {availability.data.status === "pending" ? "Registrar disponibilidade" : "Revisar registro"}
            </ButtonLink>
          </Card>
        )}
      </section>

      <section aria-labelledby="proximas" className="space-y-4">
        <div className="flex items-end justify-between gap-4">
          <h2 id="proximas" className="font-display text-2xl text-forest-900">
            Próximas sessões
          </h2>
          <Link href="/ministrante/sessoes" className="text-sm font-semibold text-forest-700 underline underline-offset-4">
            Ver todas
          </Link>
        </div>
        {sessions.error ? (
          <ErrorState error={sessions.error} onRetry={sessions.reload} />
        ) : sessions.loading ? (
          <LoadingBlock rows={2} label="Carregando sessões…" />
        ) : upcoming.length === 0 ? (
          <EmptyState
            icon={UserRoundCheck}
            title="Você não tem sessões futuras"
            description="Registre a sua disponibilidade ou aceite convites de cobertura."
            action={<ButtonLink href="/ministrante/disponibilidade">Registrar disponibilidade</ButtonLink>}
          />
        ) : (
          <div className="space-y-4">
            {upcoming.map(({ session }) => (
              <Card key={session.id}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="capitalize-first font-display text-2xl text-forest-900">
                      {formatDayLong(new Date(session.startsAt))}
                    </h3>
                    <p className="mt-1 text-lg text-ink-700">{formatTimeRange(session.startsAt, session.endsAt)}</p>
                  </div>
                  <SessionStatusBadge status={session.status} />
                </div>
                <div className="mt-4 space-y-2">
                  <LocationLine session={session} />
                  <InstructorLine session={session} />
                </div>
                <NoticeList notices={session.notices} className="mt-4" />
              </Card>
            ))}
          </div>
        )}
      </section>

      <Card tone="sand" className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-paper text-forest-700">
            <ClipboardList className="size-6" aria-hidden />
          </span>
          <div>
            <p className="font-display text-xl text-forest-900">Convites de cobertura</p>
            <p className="text-ink-700">Veja convites pendentes e o histórico de coberturas.</p>
          </div>
        </div>
        <ButtonLink href="/ministrante/convites" variant="secondary">
          Abrir convites
        </ButtonLink>
      </Card>
    </div>
  );
}
