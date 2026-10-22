import type { Metadata } from "next";
import { ParticipantHome } from "@/components/painel/participant-views";

export const metadata: Metadata = { title: "Minha área" };

export default function ParticipantHomePage() {
  return <ParticipantHome />;
}
