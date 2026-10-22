"use client";

import { useState } from "react";
import { Eye, Hourglass, XCircle } from "lucide-react";
import { InstructorLine, LocationLine, NoticeList, SessionDetails, WhenLine } from "@/components/agenda/session-parts";
import { Alert } from "@/components/ui/alert";
import { EnrollmentBadge, SessionStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Modal } from "@/components/ui/modal";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDayLong, formatTime, relativeDayLabel } from "@/lib/dates";
import { useNow } from "@/lib/hooks/use-now";
import type { Enrollment } from "@/lib/types";

const accent: Record<Enrollment["status"], string> = {
  confirmed: "border-l-forest-600",
  waitlisted: "border-l-lavender-400",
  attended: "border-l-sand-300",
  cancelled: "border-l-clay-200",
};

interface EnrollmentCardProps {
  enrollment: Enrollment;
  onChanged: () => void;
  featured?: boolean;
}

export function EnrollmentCard({ enrollment, onChanged, featured }: EnrollmentCardProps) {
  const { session } = enrollment;
  const now = useNow();
  const toast = useToast();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);

  const active = enrollment.status === "confirmed" || enrollment.status === "waitlisted";
  const dayLabel = now && active ? relativeDayLabel(session.startsAt, now) : null;

  async function cancel() {
    // O servidor decide se o cancelamento é permitido; só mostramos sucesso após a resposta.
    await api.enrollments.cancel(enrollment.id);
    setCancelOpen(false);
    toast.push({
      tone: "success",
      title: "Inscrição cancelada",
      message: "O sistema registrou o cancelamento.",
    });
    onChanged();
  }

  return (
    <article
      className={cn(
        "rounded-(--radius-card) border border-l-4 border-line bg-paper shadow-soft",
        accent[enrollment.status],
        featured ? "p-6 sm:p-8" : "p-5 sm:p-6",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <EnrollmentBadge status={enrollment.status} />
        {dayLabel ? (
          <span className="text-sm font-semibold capitalize text-forest-700">{dayLabel}</span>
        ) : null}
      </div>

      <h3
        className={cn(
          "capitalize-first mt-4 font-display text-forest-900",
          featured ? "text-3xl sm:text-4xl" : "text-2xl",
        )}
      >
        {formatDayLong(new Date(session.startsAt))}
      </h3>
      <p className="mt-1 text-lg text-ink-700">
        {formatTime(session.startsAt)} – {formatTime(session.endsAt)}
      </p>

      <div className="mt-4 space-y-2">
        <LocationLine session={session} />
        <InstructorLine session={session} />
      </div>

      {enrollment.status === "waitlisted" ? (
        <p className="mt-4 flex items-start gap-2 rounded-xl bg-lavender-50 px-3.5 py-2.5 text-sm text-lavender-700">
          <Hourglass className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            Você está na fila de espera
            {enrollment.waitlistPosition ? ` (posição ${enrollment.waitlistPosition})` : ""}. Isso não
            garante uma vaga.
          </span>
        </p>
      ) : null}

      {enrollment.status === "cancelled" && enrollment.cancelledAt ? (
        <p className="mt-4 text-sm text-ink-600">Esta inscrição foi cancelada.</p>
      ) : null}

      <NoticeList notices={session.notices} className="mt-4" />

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setDetailsOpen(true)}
          icon={<Eye className="size-4" aria-hidden />}
        >
          Ver detalhes
        </Button>
        {active ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCancelOpen(true)}
            disabled={!enrollment.canCancel}
            className="text-clay-700 hover:bg-clay-50"
            icon={<XCircle className="size-4" aria-hidden />}
          >
            Cancelar inscrição
          </Button>
        ) : null}
      </div>
      {active && !enrollment.canCancel ? (
        <p className="mt-3 text-sm text-ink-600">
          {enrollment.cancelBlockedReason ?? "O cancelamento não está disponível para esta inscrição."}
        </p>
      ) : null}

      <Modal
        open={detailsOpen}
        onClose={() => setDetailsOpen(false)}
        title="Detalhes da sessão"
        description={`${formatDayLong(new Date(session.startsAt))}, ${formatTime(session.startsAt)} – ${formatTime(session.endsAt)}`}
        footer={
          <Button variant="secondary" onClick={() => setDetailsOpen(false)}>
            Fechar
          </Button>
        }
      >
        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            <EnrollmentBadge status={enrollment.status} />
            <SessionStatusBadge status={session.status} />
          </div>
          <NoticeList notices={session.notices} />
          <SessionDetails session={session} showCapacity={false} />
          <WhenLine session={session} className="sr-only" />
        </div>
      </Modal>

      <ConfirmDialog
        open={cancelOpen}
        onClose={() => setCancelOpen(false)}
        title="Cancelar inscrição?"
        description="Sua vaga será liberada para outra pessoa."
        confirmLabel="Sim, cancelar inscrição"
        cancelLabel="Manter inscrição"
        tone="danger"
        onConfirm={cancel}
      >
        <Alert tone="warning">
          Você está prestes a cancelar a sessão de{" "}
          <strong className="capitalize-first">{formatDayLong(new Date(session.startsAt))}</strong>, às{" "}
          {formatTime(session.startsAt)}, em {session.location.name}. O cancelamento só será
          confirmado depois da resposta do sistema.
        </Alert>
      </ConfirmDialog>
    </article>
  );
}
