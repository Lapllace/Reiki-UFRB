import type { Metadata } from "next";
import { CoordinationHistory } from "@/components/painel/coordination-history";

export const metadata: Metadata = { title: "Histórico de eventos" };

export default function CoordinationHistoryPage() {
  return <CoordinationHistory />;
}
