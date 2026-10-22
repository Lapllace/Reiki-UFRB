import { CalendarClock, Plus } from "lucide-react";
import { EnrollmentBadge, SessionStatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CapacityMeter } from "@/components/ui/capacity-meter";
import { cn } from "@/lib/cn";
import { formatDateTime, formatTime } from "@/lib/dates";
import type { Session } from "@/lib/types";
import { InstructorLine, LocationLine, NoticeList } from "./session-parts";

/** O que a interface oferece para uma sessão. A decisão final é sempre do servidor. */
export type SessionAction = "enroll" | "waitlist" | "mine" | "details";

export function actionFor(session: Session): SessionAction {
  if (session.myEnrollment && session.myEnrollment.status !== "cancelled") return "mine";
  if (session.status === "open") return "enroll";
  if (session.status === "full" && session.waitlistEnabled !== false) return "waitlist";
  return "details";
}

const actionLabel: Record<SessionAction, string> = {
  enroll: "Ver detalhes e inscrever-se",
  waitlist: "Entrar na fila de espera",
  mine: "Ver minha inscrição",
  details: "Ver detalhes",
};

export function SessionCard({
  session,
  onOpen,
}: {
  session: Session;
  onOpen: (session: Session) => void;
}) {
  const action = actionFor(session);
  const inactive = session.status === "cancelled" || session.status === "completed";
  const mine = session.myEnrollment && session.myEnrollment.status !== "cancelled" ? session.myEnrollment : null;

  return (
    <article
      aria-label={`Sessão às ${formatTime(session.startsAt)} em ${session.location.name}`}
      className={cn(
        "flex h-full flex-col rounded-(--radius-card) border bg-paper p-5 shadow-soft transition-shadow hover:shadow-lift sm:p-6",
        inactive ? "border-line opacity-80" : "border-line",
        action === "mine" && "border-forest-300 ring-1 ring-forest-300/60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-[1.75rem] leading-none text-forest-900">
            {formatTime(session.startsAt)}
            <span className="ml-1.5 text-base text-ink-500">até {formatTime(session.endsAt)}</span>
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          {mine ? (
            <EnrollmentBadge status={mine.status} />
          ) : (
            <SessionStatusBadge status={session.status} />
          )}
          {session.isExtra ? (
            <span className="text-xs font-semibold uppercase tracking-wider text-lavender-700">
              Sessão extra
            </span>
          ) : null}
        </div>
      </div>

      <div className="mt-5 space-y-2">
        <LocationLine session={session} />
        <InstructorLine session={session} />
      </div>

      <NoticeList notices={session.notices} className="mt-4" />

      {mine?.status === "waitlisted" && mine.waitlistPosition ? (
        <p className="mt-4 text-sm font-medium text-lavender-700">
          Sua posição na fila: {mine.waitlistPosition}º
        </p>
      ) : null}

      {!inactive && session.status !== "scheduled" ? (
        <CapacityMeter
          className="mt-5"
          capacity={session.capacity}
          confirmed={session.confirmedCount}
          waitlist={session.waitlistCount}
        />
      ) : null}

      {session.status === "scheduled" && session.enrollmentOpensAt ? (
        <p className="mt-5 flex items-center gap-2 text-sm text-lavender-700">
          <CalendarClock className="size-4" aria-hidden />
          Inscrições abrem em {formatDateTime(session.enrollmentOpensAt)}
        </p>
      ) : null}

      <div className="mt-auto pt-6">
        <Button
          variant={action === "enroll" ? "primary" : action === "waitlist" ? "soft" : "secondary"}
          size="sm"
          fullWidth
          onClick={() => onOpen(session)}
          icon={action === "enroll" || action === "waitlist" ? <Plus className="size-4" aria-hidden /> : undefined}
        >
          {actionLabel[action]}
        </Button>
      </div>
    </article>
  );
}
