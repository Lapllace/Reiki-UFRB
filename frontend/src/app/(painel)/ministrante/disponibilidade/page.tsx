import type { Metadata } from "next";
import { AvailabilityWizard } from "@/components/painel/availability-wizard";

export const metadata: Metadata = { title: "Disponibilidade semanal" };

export default function AvailabilityPage() {
  return <AvailabilityWizard />;
}
