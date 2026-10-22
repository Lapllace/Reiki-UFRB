import type { ReactNode } from "react";
import { Container } from "@/components/ui/section";

/** Abertura das páginas internas do site público. */
export function PageHero({
  eyebrow,
  title,
  description,
  children,
  compact,
}: {
  eyebrow: string;
  title: ReactNode;
  description: ReactNode;
  children?: ReactNode;
  /** Reduz a altura para telas de uso (agenda), levando o conteúdo principal mais perto do topo. */
  compact?: boolean;
}) {
  return (
    <section className="surface-grain border-b border-line bg-sand-50/70">
      <Container className={compact ? "py-5 sm:py-8" : "py-16 sm:py-24"}>
        <p className="eyebrow animate-rise">{eyebrow}</p>
        <h1
                  className={`display-xl mt-4 max-w-4xl animate-rise [animation-delay:80ms] ${
                    compact ? "text-[clamp(1.5rem,5vw,2.2rem)]" : "text-[clamp(2.4rem,6vw,4.4rem)]"
                  }`}
                >
          {title}
        </h1>
        <p className={`lead max-w-xl animate-rise [animation-delay:160ms] ${compact ? "mt-2.5 text-sm sm:text-base" : "mt-6"}`}>
                  {description}
                </p>
        {children ? <div className="mt-6 animate-rise [animation-delay:240ms]">{children}</div> : null}
      </Container>
    </section>
  );
}
