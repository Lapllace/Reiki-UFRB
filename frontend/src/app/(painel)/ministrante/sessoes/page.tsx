import type { Metadata } from "next";
import { InstructorSessions } from "@/components/painel/instructor-sessions";

export const metadata: Metadata = { title: "Minhas sessões" };

export default function InstructorSessionsPage() {
  return <InstructorSessions />;
}
