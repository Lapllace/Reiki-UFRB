import type { Metadata } from "next";
import { CoordinationReallocations } from "@/components/painel/coordination-reallocations";

export const metadata: Metadata = { title: "Reorganização de participantes" };

export default function CoordinationReallocationsPage() {
  return <CoordinationReallocations />;
}
