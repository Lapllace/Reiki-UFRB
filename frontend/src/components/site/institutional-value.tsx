import { PendingValue } from "@/components/ui/provisional";
import type { InstitutionalField } from "@/content/institutional";

/** Exibe o dado institucional apenas se estiver confirmado; caso contrário, marca como pendente. */
export function InstitutionalValue({ field }: { field: InstitutionalField }) {
  if (field.status === "confirmed" && field.value) return <>{field.value}</>;
  return <PendingValue />;
}
