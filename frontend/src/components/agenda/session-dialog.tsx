"use client";

import Link from "next/link";
import { useState } from "react";
import { CalendarClock, CheckCircle2, Hourglass, Info, MapPin } from "lucide-react";
import { Alert } from "@/components/ui/alert";
import { EnrollmentBadge, SessionStatusBadge } from "@/components/ui/badge";
import { Button, ButtonLink } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { api } from "@/lib/api";
import { toApiError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/auth-context";
import { formatDayLong, formatTimeRange } from "@/lib/dates";
import type { Enrollment, Session } from "@/lib/types";
import { actionFor } from "./session-card";
import { DetailRow as Row, NoticeList, SessionDetails } from "./session-parts";

type Phase =
  | { kind: "review" }
  | { kind: "submitting" }
  | { kind: "done"; enrollment: Enrollment }
  | { kind: "error"; message: string };

interface SessionDialogProps {
  session: Session | null;
  open: boolean;
  onClose: () => void;
  /** Chamado quando o servidor respondeu e a lista deve ser recarregada. */
  onChanged: () => void;
}


export function SessionDialog({ session, open, onClose, onChanged }: SessionDialogProps) {
  const { user } = useAuth();
  const [phase, setPhase] = useState<Phase>({ kind: "review" });
  const [wasOpen, setWasOpen] = useState(open);

  // Reinicia o fluxo sempre que o diálogo é reaberto.
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) setPhase({ kind: "review" });
  }

  if (!session) return null;

  const action = actionFor(session);
  const submitting = phase.kind === "submitting";
  const isParticipant = user?.role === "participant";
  const canTry = (action === "enroll" || action === "waitlist") && isParticipant;
  const date = new Date(session.startsAt);

  async function confirm() {
    if (!session) return;
    setPhase({ kind: "submitting" });
    try {
      const { enrollment } = await api.enrollments.create(session.id);
      setPhase({ kind: "done", enrollment });
      onChanged();
    } catch (caught) {
      const error = toApiError(caught);
      setPhase({ kind: "error", message: error.message });
      if (error.kind === "conflict") onChanged();
    }
  }

  const title = `${formatDayLong(date).replace(/^./, (letter) => letter.toUpperCase())}`;

  /* --------------------------- resultado do servidor --------------------------- */
  if (phase.kind === "done") {
    const { enrollment } = phase;
    const waitlisted = enrollment.status === "waitlisted";
    return (
      <Modal
        open={open}
        onClose={onClose}
        title={waitlisted ? "Você entrou na fila de espera" : "Inscrição confirmada"}
        footer={
          <>
            <Button variant="secondary" onClick={onClose}>
              Fechar
            </Button>
            <ButtonLink href="/participante/inscricoes">Ver minhas inscrições</ButtonLink>
          </>
        }
      >
        <div className="flex flex-col items-center text-center">
          <span
            className={`grid size-16 place-items-center rounded-full ${
              waitlisted ? "bg-lavender-100 text-lavender-700" : "bg-forest-100 text-forest-700"
            }`}
          >
            {waitlisted ? <Hourglass className="size-8" aria-hidden /> : <CheckCircle2 className="size-8" aria-hidden />}
          </span>
          <div className="mt-4">
            <EnrollmentBadge status={enrollment.status} />
          </div>
          <p className="mt-4 max-w-sm text-ink-700">
            {waitlisted
              ? `O sistema registrou você na fila de espera${
                  enrollment.waitlistPosition ? ` (posição ${enrollment.waitlistPosition})` : ""
                }. Isso não garante uma vaga: se uma for liberada, a sua situação será atualizada na sua área.`
              : "O sistema confirmou a sua vaga nesta sessão. Você pode consultar os detalhes a qualquer momento na sua área."}
          </p>
        </div>
        <dl className="mt-6 space-y-4 rounded-2xl bg-sand-50 p-5">
          <Row icon={<CalendarClock className="size-5" aria-hidden />} label="Quando">
            {title}, {formatTimeRange(enrollment.session.startsAt, enrollment.session.endsAt)}
          </Row>
          <Row icon={<MapPin className="size-5" aria-hidden />} label="Onde">
            {enrollment.session.location.name}
          </Row>
        </dl>
      </Modal>
    );
  }

  /* ------------------------------- revisão ---------------------------------- */
  const label = action === "waitlist" ? "Entrar na fila de espera" : "Confirmar inscrição";

  return (
    <Modal
      open={open}
      onClose={onClose}
      busy={submitting}
      title={title}
      description={formatTimeRange(session.startsAt, session.endsAt)}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={submitting}>
            {action === "mine" || !canTry ? "Fechar" : "Voltar"}
          </Button>
          {canTry ? (
            <Button
              variant={action === "waitlist" ? "soft" : "primary"}
              onClick={confirm}
              loading={submitting}
            >
              {submitting ? "Aguardando o sistema…" : label}
            </Button>
          ) : null}
        </>
      }
    >
      <div className="space-y-6">
        <div className="flex flex-wrap items-center gap-2">
          <SessionStatusBadge status={session.status} />
          {session.isExtra ? (
            <span className="text-xs font-semibold uppercase tracking-wider text-lavender-700">
              Sessão extra
            </span>
          ) : null}
        </div>

        <NoticeList notices={session.notices} />

        <SessionDetails session={session} />

        {/* Orientação conforme a situação */}
        {action === "mine" && session.myEnrollment ? (
          <Alert tone="success" title="Você já está nesta sessão">
            <EnrollmentBadge status={session.myEnrollment.status} className="mb-2" />
            <p>
              Gerencie esta inscrição em{" "}
              <Link href="/participante/inscricoes" className="font-semibold underline underline-offset-4">
                Minhas inscrições
              </Link>
              .
            </p>
          </Alert>
        ) : null}

        {action === "waitlist" && canTry ? (
          <Alert tone="info" title="Esta sessão está lotada">
            Ao entrar na fila de espera você <strong>não</strong> terá uma vaga garantida. Se alguém
            cancelar, o sistema atualiza a sua situação.
          </Alert>
        ) : null}

        {action === "details" && session.status === "scheduled" ? (
          <Alert tone="info">As inscrições para esta sessão ainda não abriram.</Alert>
        ) : null}
        {action === "details" && (session.status === "needs_cover" || session.status === "uncovered") ? (
          <Alert tone="warning">
            Esta sessão aguarda um ministrante. Novas inscrições ficam indisponíveis até que o
            sistema confirme a cobertura.
          </Alert>
        ) : null}
        {action === "details" && session.status === "full" ? (
          <Alert tone="warning">Sessão lotada e sem fila de espera disponível.</Alert>
        ) : null}

        {(action === "enroll" || action === "waitlist") && !user ? (
          <Alert
            tone="info"
            title="Entre para se inscrever"
            action={
              <ButtonLink href="/entrar?next=/agenda" size="sm">
                Entrar
              </ButtonLink>
            }
          >
            Você precisa estar com a sessão ativa para se inscrever.
          </Alert>
        ) : null}
        {(action === "enroll" || action === "waitlist") && user && !isParticipant ? (
          <Alert tone="info">A inscrição em sessões é feita por contas de participante.</Alert>
        ) : null}

        {canTry ? (
          <p className="flex items-start gap-2 text-sm text-ink-600">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            A vaga só é considerada sua depois que o sistema responder. Você verá aqui o resultado.
          </p>
        ) : null}

        {phase.kind === "error" ? (
          <Alert tone="danger" title="Não foi possível concluir">
            {phase.message}
          </Alert>
        ) : null}
      </div>
    </Modal>
  );
}
