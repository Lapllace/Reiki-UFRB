import type { ElementType, HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: ElementType;
  tone?: "paper" | "sand" | "sage" | "forest";
  padded?: boolean;
}

const toneClasses = {
  paper: "bg-paper border-line shadow-soft",
  sand: "bg-sand-50 border-sand-200",
  sage: "bg-sage-50 border-sage-200",
  forest: "bg-forest-800 border-forest-700 text-ivory",
};

export function Card({ as: Tag = "div", tone = "paper", padded = true, className, ...props }: CardProps) {
  return (
    <Tag
      data-surface={tone === "forest" ? "dark" : undefined}
      className={cn("rounded-(--radius-card) border", toneClasses[tone], padded && "p-5 sm:p-6", className)}
      {...props}
    />
  );
}
