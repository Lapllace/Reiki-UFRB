import { clsx, type ClassValue } from "clsx";

/** Junta classes condicionais. As variações dos componentes são estruturadas para não conflitar entre si. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
