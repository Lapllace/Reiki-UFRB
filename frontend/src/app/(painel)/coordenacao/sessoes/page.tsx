import type { Metadata } from "next";
import { CoordinationSessions } from "@/components/painel/coordination-sessions";

export const metadata: Metadata = { title: "Sessões e inscrições" };

export default function CoordinationSessionsPage() {
  return <CoordinationSessions />;
}
