"use client";

import { useMemo, useState, type FormEvent } from "react";
import { Ban, CalendarX2, ShieldCheck, Users } from "lucide-react";
import { z } from "zod";
import {
  InstructorLine,
  LocationLine,
  NoticeList,
} from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { EnrollmentBadge, SessionStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CapacityMeter } from "@/components/ui/capacity-meter";
import { TextAreaField } from "@/components/ui/form";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/section";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { Tabs, TabPanel } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { cn } from "@/lib/cn";
import { formatDayLong, formatTime, formatTimeRange } from "@/lib/dates";
import { fieldErrors } from "@/lib/forms";
import { useResource } from "@/lib/hooks/use-resource";
import type { InstructorSession } from "@/lib/types";

/** Lista de inscritos de uma sessão (dados privados: só o ministrante responsável e a coordenação). */
export function RosterDialog({
  sessionId,
  title,
  scope,
  open,
  onClose,
}: {
  sessionId: string | null;
  title: string;
  scope: "instructor" | "coordination";
  open: boolean;
  onClose: () => void;
}) {
  const { data, error, loading, reload } = useResource(
    open && sessionId ? `roster:${scope}:${sessionId}` : null,
    (signal) =>
      scope === "instructor"
        ? api.instructor.roster(sessionId as string, signal)
        : api.coordination.roster(sessionId as string, signal),
  );

  const confirmed = (data ?? []).filter((entry) => entry.status === "confirmed" || entry.status === "attended");
  const waitlisted = (data ?? []).filter((entry) => entry.status === "waitlisted");

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Inscrições da sessão"
      description={title}
      footer={
        <Button variant="secondary" onClick={onClose}>
          Fechar
        </Button>
      }
    >
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={2} label="Carregando inscrições…" />
      ) : (data ?? []).length === 0 ? (
        <EmptyState icon={Users} title="Nenhuma inscrição ainda" description="Quando houver inscritos, eles aparecerão aqui." />
      ) : (
        <div className="space-y-6">
          <p className="flex items-start gap-2 rounded-xl bg-sand-50 px-4 py-3 text-sm text-ink-700">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-forest-600" aria-hidden />
            Informações privadas dos participantes, visíveis apenas para quem é responsável pela sessão.
          </p>
          <section aria-label="Inscritos">
            <h3 className="font-semibold text-forest-900">
              {confirmed.length} {confirmed.length === 1 ? "inscrito" : "inscritos"}
            </h3>
            <ul className="mt-3 divide-y divide-line rounded-2xl border border-line">
              {confirmed.map((entry) => (
                <li key={entry.enrollmentId} className="flex items-center justify-between gap-3 px-4 py-3">
                  <span>{entry.participantName}</span>
                  <EnrollmentBadge status={entry.status} />
                </li>
              ))}
            </ul>
          </section>
          {waitlisted.length > 0 ? (
            <section aria-label="Fila de espera">
              <h3 className="font-semibold text-forest-900">Fila de espera ({waitlisted.length})</h3>
              <ol className="mt-3 divide-y divide-line rounded-2xl border border-line">
                {waitlisted.map((entry) => (
                  <li key={entry.enrollmentId} className="flex items-center justify-between gap-3 px-4 py-3">
                    <span>
                      {entry.waitlistPosition ? `${entry.waitlistPosition}º · ` : ""}
                      {entry.participantName}
                    </span>
                    <EnrollmentBadge status="waitlisted" />
                  </li>
                ))}
              </ol>
            </section>
          ) : null}
        </div>
      )}
    </Modal>
  );
}

const reasonSchema = z.object({
  reason: z.string().trim().min(10, "Descreva o motivo com pelo menos 10 caracteres."),
});

function CancelSessionDialog({
  item,
  onClose,
  onDone,
}: {
  item: InstructorSession | null;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | undefined>();
  const [serverError, setServerError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [lastItem, setLastItem] = useState<InstructorSession | null>(null);

  // Limpa o formulário cada vez que um novo cancelamento é iniciado.
  if (item !== lastItem) {
    setLastItem(item);
    if (item) {
      setReason("");
      setError(undefined);
      setServerError(null);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!item) return;
    const parsed = reasonSchema.safeParse({ reason });
    if (!parsed.success) {
      setError(fieldErrors(parsed.error).reason);
      return;
    }
    setPending(true);
    setServerError(null);
    try {
      await api.instructor.cancelSession(item.session.id, parsed.data.reason);
      toast.push({
        tone: "success",
        title: "Cancelamento registrado",
        message: "O sistema registrou o cancelamento. Os ministrantes elegíveis serão consultados para cobrir a sessão.",
      });
      onDone();
      onClose();
    } catch (caught) {
      setServerError(toApiError(caught).message);
    } finally {
      setPending(false);
    }
  }

  return (
    <Modal
      open={item !== null}
      onClose={onClose}
      busy={pending}
      title="Cancelar sessão"
      description={item ? `${formatDayLong(new Date(item.session.startsAt))}, ${formatTime(item.session.startsAt)}` : undefined}
      width="32rem"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={pending}>
            Manter sessão
          </Button>
          <Button variant="danger" type="submit" form="form-cancelar-sessao" loading={pending}>
            Cancelar sessão
          </Button>
        </>
      }
    >
      <form id="form-cancelar-sessao" onSubmit={submit} noValidate className="space-y-5">
        <Alert tone="warning" title="O que acontece em seguida">
          Todos os ministrantes elegíveis receberão uma solicitação de cobertura. O primeiro aceite
          registrado pelo sistema assume a sessão. Os participantes serão avisados das mudanças.
        </Alert>
        <TextAreaField
          label="Motivo do cancelamento"
          name="reason"
          required
          value={reason}
          onChange={(event) => {
            setReason(event.target.value);
            setError(undefined);
          }}
          error={error}
          hint="Este motivo é visto pela coordenação."
        />
        {serverError ? <Alert tone="danger">{serverError}</Alert> : null}
      </form>
    </Modal>
  );
}

export function InstructorSessions() {
  const { user } = useAuth();
  const { data, error, loading, reload } = useResource(
    user ? `instructor-sessions:${user.id}` : null,
    (signal) => api.instructor.listSessions(signal),
  );
  const [tab, setTab] = useState("upcoming");
  const [rosterFor, setRosterFor] = useState<InstructorSession | null>(null);
  const [rosterOpen, setRosterOpen] = useState(false);
  const [cancelFor, setCancelFor] = useState<InstructorSession | null>(null);

  const groups = useMemo(() => {
    const all = data ?? [];
    return {
      upcoming: all.filter((item) => item.session.status !== "completed"),
      past: all.filter((item) => item.session.status === "completed").reverse(),
    };
  }, [data]);

  const list = tab === "upcoming" ? groups.upcoming : groups.past;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Ministrante"
        title="Minhas sessões"
        description="Sessões que você assumiu, com acesso às inscrições e ao cancelamento quando permitido."
      />

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading ? (
        <LoadingBlock rows={3} label="Carregando suas sessões…" />
      ) : (
        <>
          <Tabs
            ariaLabel="Filtrar sessões"
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "upcoming", label: "Próximas", count: groups.upcoming.length },
              { id: "past", label: "Realizadas", count: groups.past.length },
            ]}
          />
          <TabPanel label={tab === "upcoming" ? "Próximas sessões" : "Sessões realizadas"} className="space-y-4">
            {list.length === 0 ? (
              <EmptyState
                icon={CalendarX2}
                title={tab === "upcoming" ? "Nenhuma sessão futura" : "Nenhuma sessão realizada ainda"}
                description="Registre sua disponibilidade ou aceite convites de cobertura para assumir sessões."
              />
            ) : (
              list.map((item) => {
                const { session } = item;
                const coverPending = session.status === "needs_cover" || session.status === "uncovered";
                const cancellable = session.status === "open" || session.status === "full";
                return (
                  <article
                    key={session.id}
                    className={cn(
                      "rounded-(--radius-card) border border-line bg-paper p-5 shadow-soft sm:p-6",
                      session.status === "cancelled" && "opacity-80",
                    )}
                  >
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
                    {session.status !== "completed" && session.status !== "cancelled" ? (
                      <CapacityMeter
                        className="mt-5 max-w-sm"
                        capacity={session.capacity}
                        confirmed={session.confirmedCount}
                        waitlist={session.waitlistCount}
                      />
                    ) : null}
                    <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={<Users className="size-4" aria-hidden />}
                        onClick={() => {
                          setRosterFor(item);
                          setRosterOpen(true);
                        }}
                      >
                        Ver inscrições
                      </Button>
                      {cancellable ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-clay-700 hover:bg-clay-50"
                          disabled={!item.canCancel}
                          icon={<Ban className="size-4" aria-hidden />}
                          onClick={() => setCancelFor(item)}
                        >
                          Cancelar sessão
                        </Button>
                      ) : null}
                    </div>
                    {cancellable && !item.canCancel ? (
                      <p className="mt-3 text-sm text-ink-600">
                        {item.cancelBlockedReason ?? "O cancelamento não está disponível para esta sessão."}
                      </p>
                    ) : null}
                    {coverPending ? (
                      <p className="mt-3 text-sm text-honey-700">
                        Cobertura solicitada: acompanhe o andamento em Convites ou com a coordenação.
                      </p>
                    ) : null}
                  </article>
                );
              })
            )}
          </TabPanel>
        </>
      )}

      <RosterDialog
        sessionId={rosterFor?.session.id ?? null}
        title={
          rosterFor
            ? `${formatDayLong(new Date(rosterFor.session.startsAt))}, ${formatTime(rosterFor.session.startsAt)} · ${rosterFor.session.location.name}`
            : ""
        }
        scope="instructor"
        open={rosterOpen}
        onClose={() => setRosterOpen(false)}
      />
      <CancelSessionDialog item={cancelFor} onClose={() => setCancelFor(null)} onDone={reload} />
    </div>
  );
}
