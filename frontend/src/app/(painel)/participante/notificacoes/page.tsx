import type { Metadata } from "next";
import { ParticipantNotifications } from "@/components/painel/participant-views";

export const metadata: Metadata = { title: "Avisos" };

export default function ParticipantNotificationsPage() {
  return <ParticipantNotifications />;
}
