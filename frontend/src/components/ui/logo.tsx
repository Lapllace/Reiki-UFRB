import { cn } from "@/lib/cn";

/** Marca: uma folha sustentada por um arco (cuidado e acolhimento), dentro de um círculo. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" fill="none" aria-hidden className={cn("size-9", className)}>
      <circle cx="20" cy="20" r="20" fill="currentColor" />
      <path
        d="M20 7.5c7.4 3.6 9.6 11.6 0 20.5-9.6-8.9-7.4-16.9 0-20.5Z"
        fill="var(--color-ivory)"
      />
      <path d="M20 13v14" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity=".55" />
      <path
        d="M8.5 27.5c3.3 4.6 8.4 6.6 11.5 6.6s8.2-2 11.5-6.6"
        stroke="var(--color-ivory)"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Logo({ className, tone = "dark" }: { className?: string; tone?: "dark" | "light" }) {
  return (
    <span className={cn("inline-flex items-center gap-3", className)}>
      <LogoMark className={tone === "dark" ? "text-forest-700" : "text-sage-400"} />
      <span className="leading-none">
        <span
          className={cn(
            "block font-display text-[1.45rem] tracking-tight",
            tone === "dark" ? "text-forest-900" : "text-ivory",
          )}
        >
          Reiki
        </span>
        <span
          className={cn(
            "mt-1 block text-[0.62rem] font-bold uppercase tracking-[0.34em]",
            tone === "dark" ? "text-sage-700" : "text-sage-300",
          )}
        >
          UFRB
        </span>
      </span>
    </span>
  );
}
