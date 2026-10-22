import type { Metadata } from "next";
import { ParticipantEnrollments } from "@/components/painel/participant-views";

export const metadata: Metadata = { title: "Minhas inscrições" };

export default function ParticipantEnrollmentsPage() {
  return <ParticipantEnrollments />;
}
