import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, OctagonAlert, X } from "lucide-react";
import { cn } from "@/lib/cn";

type AlertTone = "info" | "success" | "warning" | "danger";

const styles: Record<AlertTone, { box: string; icon: string; Icon: typeof Info }> = {
  info: { box: "border-lavender-200 bg-lavender-50", icon: "text-lavender-700", Icon: Info },
  success: { box: "border-forest-200 bg-forest-50", icon: "text-forest-600", Icon: CheckCircle2 },
  warning: { box: "border-honey-200 bg-honey-50", icon: "text-honey-600", Icon: AlertTriangle },
  danger: { box: "border-clay-200 bg-clay-50", icon: "text-clay-600", Icon: OctagonAlert },
};

interface AlertProps {
  tone?: AlertTone;
  title?: string;
  children?: ReactNode;
  action?: ReactNode;
  onDismiss?: () => void;
  className?: string;
}

export function Alert({ tone = "info", title, children, action, onDismiss, className }: AlertProps) {
  const { box, icon, Icon } = styles[tone];
  return (
    <div
      role={tone === "danger" || tone === "warning" ? "alert" : "status"}
      className={cn("flex gap-3 rounded-2xl border p-4 sm:p-5", box, className)}
    >
      <Icon className={cn("mt-0.5 size-5 shrink-0", icon)} aria-hidden />
      <div className="min-w-0 flex-1 space-y-1">
        {title ? <p className="font-semibold text-forest-900">{title}</p> : null}
        {children ? <div className="text-[0.95rem] leading-relaxed text-ink-700">{children}</div> : null}
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dispensar aviso"
          className="-m-2 grid size-11 shrink-0 place-items-center rounded-full text-ink-600 transition-colors hover:bg-black/5"
        >
          <X className="size-4" aria-hidden />
        </button>
      ) : null}
    </div>
  );
}
