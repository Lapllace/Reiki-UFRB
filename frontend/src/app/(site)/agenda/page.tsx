import type { Metadata } from "next";
import { AgendaView } from "@/components/agenda/agenda-view";
import { PageHero } from "@/components/site/page-hero";
import { Container } from "@/components/ui/section";

export const metadata: Metadata = {
  title: "Agenda semanal",
  description: "Consulte as sessões de cada semana, veja vagas e inscreva-se.",
};

export default function AgendaPage() {
  return (
    <>
      <PageHero
        compact
        eyebrow="Agenda semanal"
        title="Escolha o seu momento da semana."
        description="Navegue entre as semanas, confira local, ministrante e vagas, e inscreva-se. A inscrição só vale depois da confirmação do sistema."
      />
      <section className="py-6 sm:py-8">
        <Container>
          <AgendaView />
        </Container>
      </section>
    </>
  );
}
