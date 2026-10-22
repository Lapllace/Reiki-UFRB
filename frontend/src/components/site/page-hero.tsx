import type { ReactNode } from "react";
import { Container } from "@/components/ui/section";

/** Abertura das páginas internas do site público. */
export function PageHero({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: ReactNode;
  description: ReactNode;
  children?: ReactNode;
}) {
  return (
    <section className="surface-grain border-b border-line bg-sand-50/70">
      <Container className="py-16 sm:py-24">
        <p className="eyebrow animate-rise">{eyebrow}</p>
        <h1 className="display-xl mt-5 max-w-4xl animate-rise text-[clamp(2.4rem,6vw,4.4rem)] [animation-delay:80ms]">
          {title}
        </h1>
        <p className="lead mt-6 max-w-2xl animate-rise [animation-delay:160ms]">{description}</p>
        {children ? <div className="mt-8 animate-rise [animation-delay:240ms]">{children}</div> : null}
      </Container>
    </section>
  );
}
