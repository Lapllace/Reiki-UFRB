"use client";

import { useEffect, useId, useRef, type CSSProperties, type ReactNode } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  /** Largura máxima do painel (CSS). */
  width?: string;
  /** Impede fechar por Esc/clique fora (ex.: enquanto envia). */
  busy?: boolean;
  className?: string;
}

/**
 * Modal baseado em <dialog> nativo: foco preso, Esc fecha e o fundo fica inerte.
 * Em telas estreitas vira uma folha ancorada na parte inferior (ver globals.css).
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  width,
  busy,
  className,
}: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
      onClose={() => {
        if (open) onClose();
      }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      {open ? (
        <div
          className={cn("modal-panel", className)}
          style={width ? ({ "--modal-width": width } as CSSProperties) : undefined}
        >
          <header className="flex items-start justify-between gap-4 border-b border-line px-5 pb-4 pt-5 sm:px-7 sm:pt-6">
            <div className="min-w-0">
              <h2 id={titleId} className="font-display text-2xl leading-tight text-forest-900">
                {title}
              </h2>
              {description ? (
                <p id={descriptionId} className="mt-1.5 text-[0.95rem] text-ink-600">
                  {description}
                </p>
              ) : null}
            </div>
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              aria-label="Fechar"
              className="-mr-2 -mt-1 grid size-11 shrink-0 place-items-center rounded-full text-ink-600 transition-colors hover:bg-sand-100 disabled:opacity-50"
            >
              <X className="size-5" aria-hidden />
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 sm:px-7">{children}</div>
          {footer ? (
            <footer className="flex flex-col-reverse gap-3 border-t border-line bg-sand-50/70 px-5 py-4 sm:flex-row sm:justify-end sm:px-7">
              {footer}
            </footer>
          ) : null}
        </div>
      ) : null}
    </dialog>
  );
}
