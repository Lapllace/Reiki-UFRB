import type { Metadata } from "next";
import { PageHero } from "@/components/site/page-hero";
import { LocationsList } from "@/components/site/locations-list";
import { Container } from "@/components/ui/section";

export const metadata: Metadata = {
  title: "Locais de atendimento",
  description: "Endereços, referências e mapas dos locais onde as sessões de Reiki acontecem.",
};

export default function LocationsPage() {
  return (
    <>
      <PageHero
        eyebrow="Locais"
        title="Onde as sessões acontecem."
        description="Cada sessão informa o seu local na agenda. Aqui você encontra endereço, referências e, quando disponível, o link do mapa."
      />
      <section className="py-16 sm:py-20">
        <Container>
          <LocationsList variant="full" />
          <p className="mt-10 max-w-2xl text-sm text-ink-600">
            Os locais e endereços exibidos vêm do sistema de agendamento e são informados pela
            coordenação. Se um dado estiver marcado como &quot;a confirmar&quot;, ele ainda não foi
            divulgado oficialmente.
          </p>
        </Container>
      </section>
    </>
  );
}
