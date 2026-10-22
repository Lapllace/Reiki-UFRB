import type { ComponentType, ReactNode } from "react";
import {
  BadgeCheck,
  CalendarClock,
  CheckCircle2,
  CircleSlash,
  Clock3,
  Hourglass,
  Sparkles,
  UserRoundSearch,
  UsersRound,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/cn";
import type { EnrollmentStatus, SessionStatus } from "@/lib/types";

export type Tone = "neutral" | "forest" | "sage" | "lavender" | "clay" | "honey" | "sand";

const tones: Record<Tone, string> = {
  neutral: "bg-paper text-ink-700 ring-line-strong",
  forest: "bg-forest-100 text-forest-800 ring-forest-200",
  sage: "bg-sage-100 text-sage-700 ring-sage-200",
  lavender: "bg-lavender-100 text-lavender-700 ring-lavender-200",
  clay: "bg-clay-50 text-clay-700 ring-clay-200",
  honey: "bg-honey-50 text-honey-700 ring-honey-200",
  sand: "bg-sand-100 text-ink-700 ring-sand-200",
};

interface BadgeProps {
  tone?: Tone;
  icon?: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  children: ReactNode;
  className?: string;
}

export function Badge({ tone = "neutral", icon: Icon, children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {Icon ? <Icon className="size-3.5" aria-hidden /> : null}
      {children}
    </span>
  );
}

const enrollmentMeta: Record<EnrollmentStatus, { label: string; tone: Tone; icon: BadgeProps["icon"] }> = {
  confirmed: { label: "Inscrição confirmada", tone: "forest", icon: CheckCircle2 },
  waitlisted: { label: "Fila de espera", tone: "lavender", icon: Hourglass },
  attended: { label: "Participação concluída", tone: "sand", icon: BadgeCheck },
  cancelled: { label: "Inscrição cancelada", tone: "clay", icon: XCircle },
};

export function EnrollmentBadge({ status, className }: { status: EnrollmentStatus; className?: string }) {
  const meta = enrollmentMeta[status];
  return (
    <Badge tone={meta.tone} icon={meta.icon} className={className}>
      {meta.label}
    </Badge>
  );
}

const sessionMeta: Record<SessionStatus, { label: string; tone: Tone; icon: BadgeProps["icon"] }> = {
  open: { label: "Inscrições abertas", tone: "sage", icon: Sparkles },
  scheduled: { label: "Abre em breve", tone: "lavender", icon: CalendarClock },
  full: { label: "Lotada", tone: "honey", icon: UsersRound },
  cancelled: { label: "Cancelada", tone: "clay", icon: CircleSlash },
  needs_cover: { label: "Buscando substituto", tone: "honey", icon: UserRoundSearch },
  uncovered: { label: "Sem ministrante", tone: "clay", icon: UserRoundSearch },
  completed: { label: "Realizada", tone: "sand", icon: Clock3 },
};

export function SessionStatusBadge({ status, className }: { status: SessionStatus; className?: string }) {
  const meta = sessionMeta[status];
  return (
    <Badge tone={meta.tone} icon={meta.icon} className={className}>
      {meta.label}
    </Badge>
  );
}
