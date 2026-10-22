"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight, Bell, CalendarDays, CalendarX2, CheckCheck, History, Repeat2 } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { Button, ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { PageHeader } from "@/components/ui/section";
import { Tabs, TabPanel } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { useAccountResource } from "@/lib/hooks/use-account-resource";
import type { Enrollment } from "@/lib/types";
import { EnrollmentCard } from "./enrollment-card";
import { NotificationItem } from "./notification-item";

function useEnrollments() {
  return useAccountResource("enrollments", (signal) => api.enrollments.listMine(signal));
}

function useNotifications() {
  return useAccountResource("notifications", (signal) => api.notifications.list(signal));
}

const byStart = (a: Enrollment, b: Enrollment) => a.session.startsAt.localeCompare(b.session.startsAt);

function split(enrollments: Enrollment[]) {
  const upcoming = enrollments
    .filter((item) => item.status === "confirmed" || item.status === "waitlisted")
    .sort(byStart);
  const history = enrollments
    .filter((item) => item.status === "attended" || item.status === "cancelled")
    .sort((a, b) => byStart(b, a));
  return {
    upcoming,
    confirmed: upcoming.filter((item) => item.status === "confirmed"),
    waitlisted: upcoming.filter((item) => item.status === "waitlisted"),
    history,
    attended: history.filter((item) => item.status === "attended"),
  };
}

/* --------------------------------- Resumo --------------------------------- */

export function ParticipantHome() {
  const { user } = useAuth();
  const enrollments = useEnrollments();
  const notifications = useNotifications();

  const groups = useMemo(() => split(enrollments.data ?? []), [enrollments.data]);
  const next = groups.confirmed[0] ?? groups.waitlisted[0];
  const unread = (notifications.data ?? []).filter((item) => !item.read);
  const reallocation = (notifications.data ?? []).find((item) => item.kind === "reallocation" && !item.read);
  const firstName = user?.name.split(" ")[0];

  return (
    <div className="space-y-10">
      <PageHeader
        eyebrow="Minha área"
        title={firstName ? `Olá, ${firstName}.` : "Olá."}
        description="Acompanhe suas próximas sessões, a fila de espera e os avisos sobre mudanças."
        actions={
          <ButtonLink href="/agenda" icon={<CalendarDays className="size-5" aria-hidden />}>
            Ver agenda
          </ButtonLink>
        }
      />

      {reallocation ? (
        <Alert
          tone="info"
          title="Reorganização de participantes em andamento"
          action={
            <Link
              href="/participante/notificacoes"
              className="inline-flex items-center gap-1.5 text-sm font-semibold text-lavender-700 underline underline-offset-4"
            >
              Ler o aviso completo <ArrowRight className="size-4" aria-hidden />
            </Link>
          }
        >
          <span className="inline-flex items-start gap-2">
            <Repeat2 className="mt-1 size-4 shrink-0" aria-hidden />
            {reallocation.message}
          </span>
        </Alert>
      ) : null}

      <section aria-labelledby="proxima">
        <h2 id="proxima" className="font-display text-2xl text-forest-900">
          Próxima sessão
        </h2>
        <div className="mt-5">
          {enrollments.error ? (
            <ErrorState error={enrollments.error} onRetry={enrollments.reload} />
          ) : enrollments.loading ? (
            <LoadingBlock rows={1} label="Carregando sua próxima sessão…" />
          ) : next ? (
            <EnrollmentCard enrollment={next} featured onChanged={enrollments.reload} />
          ) : (
            <EmptyState
              icon={CalendarX2}
              title="Você ainda não tem sessões marcadas"
              description="Consulte a agenda da semana e escolha um horário que combine com você."
              action={<ButtonLink href="/agenda">Consultar a agenda</ButtonLink>}
            />
          )}
        </div>
      </section>

      {!enrollments.loading && !enrollments.error ? (
        <section aria-label="Resumo das inscrições" className="grid gap-4 sm:grid-cols-3">
          {[
            { label: "Confirmadas", value: groups.confirmed.length, tone: "text-forest-700" },
            { label: "Na fila de espera", value: groups.waitlisted.length, tone: "text-lavender-700" },
            { label: "Participações concluídas", value: groups.attended.length, tone: "text-ink-700" },
          ].map((stat) => (
            <Card key={stat.label}>
              <p className={`font-display text-5xl ${stat.tone}`}>{stat.value}</p>
              <p className="mt-2 text-sm font-semibold text-ink-600">{stat.label}</p>
            </Card>
          ))}
        </section>
      ) : null}

      <section aria-labelledby="avisos">
        <div className="flex items-end justify-between gap-4">
          <h2 id="avisos" className="font-display text-2xl text-forest-900">
            Avisos recentes
          </h2>
          <Link
            href="/participante/notificacoes"
            className="text-sm font-semibold text-forest-700 underline underline-offset-4"
          >
            Ver todos {unread.length > 0 ? `(${unread.length} novos)` : ""}
          </Link>
        </div>
        <div className="mt-5">
          {notifications.error ? (
            <ErrorState error={notifications.error} onRetry={notifications.reload} />
          ) : notifications.loading ? (
            <LoadingBlock rows={2} label="Carregando avisos…" />
          ) : (notifications.data ?? []).length === 0 ? (
            <EmptyState icon={Bell} title="Nenhum aviso por enquanto" description="Mudanças em suas sessões aparecerão aqui." />
          ) : (
            <ul className="space-y-3">
              {(notifications.data ?? []).slice(0, 3).map((item) => (
                <NotificationItem key={item.id} notification={item} />
              ))}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

/* -------------------------------- Inscrições ------------------------------- */

export function ParticipantEnrollments() {
  const { data, error, loading, reload } = useEnrollments();
  const [tab, setTab] = useState("upcoming");
  const groups = useMemo(() => split(data ?? []), [data]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Minha área"
        title="Minhas inscrições"
        description="Inscrições confirmadas, fila de espera e histórico de participações."
        actions={
          <ButtonLink href="/agenda" variant="secondary" icon={<CalendarDays className="size-5" aria-hidden />}>
            Ver agenda
          </ButtonLink>
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={3} label="Carregando suas inscrições…" />
      ) : (
        <>
          <Tabs
            ariaLabel="Filtrar inscrições"
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "upcoming", label: "Próximas", count: groups.upcoming.length },
              { id: "history", label: "Histórico", count: groups.history.length },
            ]}
          />

          {tab === "upcoming" ? (
            <TabPanel label="Próximas inscrições" className="space-y-10">
              {groups.upcoming.length === 0 ? (
                <EmptyState
                  icon={CalendarX2}
                  title="Nenhuma inscrição futura"
                  description="Quando você se inscrever em uma sessão, ela aparecerá aqui."
                  action={<ButtonLink href="/agenda">Consultar a agenda</ButtonLink>}
                />
              ) : null}
              {groups.confirmed.length > 0 ? (
                <section aria-labelledby="confirmadas" className="space-y-4">
                  <h2 id="confirmadas" className="font-display text-2xl text-forest-900">
                    Confirmadas
                  </h2>
                  {groups.confirmed.map((item) => (
                    <EnrollmentCard key={item.id} enrollment={item} onChanged={reload} />
                  ))}
                </section>
              ) : null}
              {groups.waitlisted.length > 0 ? (
                <section aria-labelledby="fila" className="space-y-4">
                  <h2 id="fila" className="font-display text-2xl text-forest-900">
                    Na fila de espera
                  </h2>
                  {groups.waitlisted.map((item) => (
                    <EnrollmentCard key={item.id} enrollment={item} onChanged={reload} />
                  ))}
                </section>
              ) : null}
            </TabPanel>
          ) : (
            <TabPanel label="Histórico de inscrições" className="space-y-4">
              {groups.history.length === 0 ? (
                <EmptyState
                  icon={History}
                  title="Seu histórico ainda está vazio"
                  description="Participações concluídas e inscrições canceladas ficam registradas aqui."
                />
              ) : (
                groups.history.map((item) => <EnrollmentCard key={item.id} enrollment={item} onChanged={reload} />)
              )}
            </TabPanel>
          )}
        </>
      )}
    </div>
  );
}

/* ------------------------------- Notificações ------------------------------ */

export function ParticipantNotifications() {
  const { data, error, loading, reload } = useNotifications();
  const toast = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function markRead(ids: string[]) {
    setBusyId(ids.length === 1 ? ids[0] : "all");
    try {
      await Promise.all(ids.map((id) => api.notifications.markRead(id)));
      reload();
    } catch (caught) {
      toast.push({ tone: "error", title: "Não foi possível atualizar", message: toApiError(caught).message });
    } finally {
      setBusyId(null);
    }
  }

  const unread = (data ?? []).filter((item) => !item.read);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Minha área"
        title="Avisos"
        description="Cancelamentos, mudança de ministrante, sessões extras e reorganização de participantes."
        actions={
          unread.length > 0 ? (
            <Button
              variant="secondary"
              loading={busyId === "all"}
              onClick={() => void markRead(unread.map((item) => item.id))}
              icon={<CheckCheck className="size-5" aria-hidden />}
            >
              Marcar todos como lidos
            </Button>
          ) : null
        }
      />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={4} label="Carregando avisos…" />
      ) : (data ?? []).length === 0 ? (
        <EmptyState
          icon={Bell}
          title="Nenhum aviso por enquanto"
          description="Se uma sessão mudar ou for cancelada, você verá o aviso aqui."
        />
      ) : (
        <ul className="space-y-3">
          {(data ?? []).map((item) => (
            <NotificationItem
              key={item.id}
              notification={item}
              action={
                !item.read ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    loading={busyId === item.id}
                    onClick={() => void markRead([item.id])}
                  >
                    Marcar como lido
                  </Button>
                ) : null
              }
            />
          ))}
        </ul>
      )}
    </div>
  );
}
