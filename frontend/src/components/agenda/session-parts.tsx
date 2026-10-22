import type { ReactNode } from "react";
import { CalendarClock, MapPin, Navigation, UserRound, UserRoundX, UsersRound } from "lucide-react";
import { CapacityMeter } from "@/components/ui/capacity-meter";
import { cn } from "@/lib/cn";
import { formatDayLong, formatTimeRange } from "@/lib/dates";
import type { Session, SessionNotice, SessionNoticeKind } from "@/lib/types";

const noticeStyles: Record<SessionNoticeKind, string> = {
  cancelled: "border-clay-200 bg-clay-50 text-clay-700",
  instructor_changed: "border-lavender-200 bg-lavender-50 text-lavender-700",
  reallocation: "border-lavender-200 bg-lavender-50 text-lavender-700",
  needs_cover: "border-honey-200 bg-honey-50 text-honey-700",
  info: "border-sage-200 bg-sage-50 text-sage-700",
};

const noticeTitles: Record<SessionNoticeKind, string> = {
  cancelled: "Cancelamento",
  instructor_changed: "Mudança de ministrante",
  reallocation: "Reorganização",
  needs_cover: "Cobertura em andamento",
  info: "Aviso",
};

export function NoticeList({ notices, className }: { notices?: SessionNotice[]; className?: string }) {
  if (!notices || notices.length === 0) return null;
  return (
    <ul className={cn("space-y-2", className)}>
      {notices.map((notice, index) => (
        <li
          key={`${notice.kind}-${index}`}
          className={cn("rounded-xl border px-3.5 py-2.5 text-sm leading-snug", noticeStyles[notice.kind])}
        >
          <span className="font-semibold">{noticeTitles[notice.kind]}: </span>
          {notice.message}
        </li>
      ))}
    </ul>
  );
}

export function InstructorLine({ session, className }: { session: Session; className?: string }) {
  return (
    <p className={cn("flex items-center gap-2 text-[0.95rem] text-ink-700", className)}>
      {session.instructor ? (
        <>
          <UserRound className="size-4 shrink-0 text-sage-600" aria-hidden />
          <span>
            <span className="sr-only">Ministrante: </span>
            {session.instructor.name}
          </span>
        </>
      ) : (
        <>
          <UserRoundX className="size-4 shrink-0 text-clay-600" aria-hidden />
          <span>Ministrante a definir</span>
        </>
      )}
    </p>
  );
}

export function LocationLine({ session, className }: { session: Session; className?: string }) {
  return (
    <p className={cn("flex items-center gap-2 text-[0.95rem] text-ink-700", className)}>
      <MapPin className="size-4 shrink-0 text-sage-600" aria-hidden />
      <span>
        <span className="sr-only">Local: </span>
        {session.location.name}
      </span>
    </p>
  );
}

export function DetailRow({
  icon,
  label,
  children,
}: {
  icon: ReactNode;
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="flex gap-4">
      <span className="mt-0.5 grid size-9 shrink-0 place-items-center rounded-xl bg-sage-100 text-forest-700">
        {icon}
      </span>
      <div className="min-w-0">
        <dt className="text-sm font-semibold text-ink-600">{label}</dt>
        <dd className="mt-0.5 text-ink-900">{children}</dd>
      </div>
    </div>
  );
}

/** Local, ministrante e vagas de uma sessão (usado em diálogos de detalhe). */
export function SessionDetails({ session, showCapacity = true }: { session: Session; showCapacity?: boolean }) {
  return (
    <dl className="space-y-5">
      <DetailRow icon={<MapPin className="size-5" aria-hidden />} label="Local">
        <span className="font-semibold">{session.location.name}</span>
        {session.location.address ? (
          <span className="block text-ink-700">{session.location.address}</span>
        ) : null}
        {session.location.reference ? (
          <span className="mt-1 flex items-start gap-1.5 text-sm text-ink-600">
            <Navigation className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            {session.location.reference}
          </span>
        ) : null}
        {session.location.mapUrl ? (
          <a
            href={session.location.mapUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-1.5 inline-block text-sm font-semibold text-forest-700 underline underline-offset-4 hover:text-forest-900"
          >
            Abrir no mapa<span className="sr-only"> (abre em nova aba)</span>
          </a>
        ) : null}
      </DetailRow>
      <DetailRow icon={<UserRound className="size-5" aria-hidden />} label="Ministrante">
        {session.instructor ? session.instructor.name : "A definir"}
      </DetailRow>
      {showCapacity ? (
        <DetailRow icon={<UsersRound className="size-5" aria-hidden />} label="Vagas">
          <CapacityMeter
            capacity={session.capacity}
            confirmed={session.confirmedCount}
            waitlist={session.waitlistCount}
            className="mt-1 w-full min-w-56"
          />
        </DetailRow>
      ) : null}
    </dl>
  );
}

/** Data + horário em uma linha legível (para listas dos painéis). */
export function WhenLine({ session, className }: { session: Session; className?: string }) {
  return (
    <p className={cn("flex items-center gap-2 text-[0.95rem] text-ink-700", className)}>
      <CalendarClock className="size-4 shrink-0 text-sage-600" aria-hidden />
      <span className="capitalize-first">
        {formatDayLong(new Date(session.startsAt))}, {formatTimeRange(session.startsAt, session.endsAt)}
      </span>
    </p>
  );
}
