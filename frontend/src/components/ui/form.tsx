"use client";

import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { AlertCircle } from "lucide-react";
import { cn } from "@/lib/cn";

const control =
  "w-full rounded-xl border bg-paper px-4 text-base text-ink-900 shadow-[inset_0_1px_0_rgb(255_255_255/0.6)] transition-[border-color,box-shadow] placeholder:text-ink-400 hover:border-forest-300 focus:border-forest-600 focus:outline-none focus:ring-4 focus:ring-forest-600/15 disabled:cursor-not-allowed disabled:bg-sand-50 disabled:text-ink-500";

interface FieldShellProps {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
}

function FieldShell({ id, label, hint, error, required, children }: FieldShellProps) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-semibold text-forest-900">
        {label}
        {required ? (
          <span aria-hidden className="ml-0.5 text-clay-600">
            *
          </span>
        ) : null}
      </label>
      {children}
      {hint && !error ? (
        <p id={`${id}-hint`} className="text-sm text-ink-600">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-error`} className="flex items-start gap-1.5 text-sm font-medium text-clay-700">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{error}</span>
        </p>
      ) : null}
    </div>
  );
}

function describedBy(id: string, hint?: string, error?: string) {
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}

interface BaseFieldProps {
  label: string;
  hint?: string;
  error?: string;
}

export const TextField = forwardRef<
  HTMLInputElement,
  BaseFieldProps & InputHTMLAttributes<HTMLInputElement>
>(function TextField({ label, hint, error, className, required, ...props }, ref) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} required={required}>
      <input
        ref={ref}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={cn(control, "min-h-12", error ? "border-clay-500" : "border-line-strong", className)}
        {...props}
      />
    </FieldShell>
  );
});

export const TextAreaField = forwardRef<
  HTMLTextAreaElement,
  BaseFieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextAreaField({ label, hint, error, className, required, ...props }, ref) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} required={required}>
      <textarea
        ref={ref}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={cn(control, "min-h-28 py-3 leading-relaxed", error ? "border-clay-500" : "border-line-strong", className)}
        {...props}
      />
    </FieldShell>
  );
});

export const SelectField = forwardRef<
  HTMLSelectElement,
  BaseFieldProps & SelectHTMLAttributes<HTMLSelectElement>
>(function SelectField({ label, hint, error, className, required, children, ...props }, ref) {
  const id = useId();
  return (
    <FieldShell id={id} label={label} hint={hint} error={error} required={required}>
      <select
        ref={ref}
        id={id}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, hint, error)}
        className={cn(control, "min-h-12", error ? "border-clay-500" : "border-line-strong", className)}
        {...props}
      >
        {children}
      </select>
    </FieldShell>
  );
});

interface CheckProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: ReactNode;
  description?: ReactNode;
}

/** Caixa de seleção com área de toque ampliada (o rótulo inteiro é clicável). */
export const CheckField = forwardRef<HTMLInputElement, CheckProps>(function CheckField(
  { label, description, className, ...props },
  ref,
) {
  const id = useId();
  return (
    <label
      htmlFor={id}
      className={cn(
        "flex min-h-12 cursor-pointer items-start gap-3 rounded-xl border border-line-strong bg-paper p-3.5 transition-colors hover:border-forest-300 has-checked:border-forest-500 has-checked:bg-forest-50 has-focus-visible:ring-4 has-focus-visible:ring-forest-600/15",
        className,
      )}
    >
      <input
        ref={ref}
        id={id}
        type="checkbox"
        className="mt-0.5 size-5 shrink-0 cursor-pointer accent-forest-700"
        {...props}
      />
      <span className="min-w-0">
        <span className="block text-[0.95rem] font-semibold text-forest-900">{label}</span>
        {description ? <span className="mt-0.5 block text-sm text-ink-600">{description}</span> : null}
      </span>
    </label>
  );
});
