import { ChevronDown } from "lucide-react";
import { ProvisionalBadge } from "@/components/ui/provisional";
import type { FaqItem } from "@/content/faq";

/** Perguntas frequentes com <details> nativo: acessível por teclado e sem JavaScript. */
export function FaqList({ items }: { items: FaqItem[] }) {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-(--radius-card) border border-line bg-paper shadow-soft">
      {items.map((item) => (
        <details key={item.question} className="group">
          <summary className="flex min-h-16 list-none items-center justify-between gap-4 px-5 py-4 text-left marker:content-none sm:px-7 [&::-webkit-details-marker]:hidden">
            <span className="font-display text-lg text-forest-900 sm:text-xl">{item.question}</span>
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-sage-100 text-forest-700 transition-transform duration-300 group-open:rotate-180">
              <ChevronDown className="size-5" aria-hidden />
            </span>
          </summary>
          <div className="space-y-3 px-5 pb-6 text-ink-700 sm:px-7">
            <p className="max-w-3xl leading-relaxed">{item.answer}</p>
            {item.provisional ? <ProvisionalBadge /> : null}
          </div>
        </details>
      ))}
    </div>
  );
}
