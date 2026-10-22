import {
  Bell,
  CalendarPlus,
  CircleSlash,
  PartyPopper,
  Repeat2,
  UserRoundCog,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/dates";
import type { AppNotification, NotificationKind } from "@/lib/types";

const meta: Record<NotificationKind, { icon: LucideIcon; tone: string }> = {
  session_cancelled: { icon: CircleSlash, tone: "bg-clay-100 text-clay-600" },
  instructor_changed: { icon: UserRoundCog, tone: "bg-lavender-100 text-lavender-700" },
  reallocation: { icon: Repeat2, tone: "bg-lavender-100 text-lavender-700" },
  extra_session: { icon: CalendarPlus, tone: "bg-sage-100 text-sage-700" },
  waitlist_promoted: { icon: PartyPopper, tone: "bg-forest-100 text-forest-700" },
  info: { icon: Bell, tone: "bg-sand-100 text-ink-700" },
};

export function NotificationItem({
  notification,
  action,
}: {
  notification: AppNotification;
  action?: React.ReactNode;
}) {
  const { icon: Icon, tone } = meta[notification.kind];
  return (
    <li
      className={cn(
        "flex gap-4 rounded-2xl border p-4 sm:p-5",
        notification.read ? "border-line bg-paper" : "border-forest-200 bg-forest-50/60",
      )}
    >
      <span className={cn("grid size-11 shrink-0 place-items-center rounded-xl", tone)}>
        <Icon className="size-5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <p className="font-semibold text-forest-900">{notification.title}</p>
          {!notification.read ? (
            <span className="rounded-full bg-forest-700 px-2 py-0.5 text-[0.68rem] font-bold uppercase tracking-wider text-ivory">
              Nova
            </span>
          ) : null}
        </div>
        <p className="mt-1 text-[0.95rem] text-ink-700">{notification.message}</p>
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-ink-500">{formatDateTime(notification.createdAt)}</p>
          {action}
        </div>
      </div>
    </li>
  );
}
