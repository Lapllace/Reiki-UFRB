import type { Metadata } from "next";
import { CoordinationOverview } from "@/components/painel/coordination-overview";

export const metadata: Metadata = { title: "Coordenação" };

export default function CoordinationPage() {
  return <CoordinationOverview />;
}
