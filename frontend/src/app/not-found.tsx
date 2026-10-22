import { SiteFooter } from "@/components/layout/site-footer";
import { SiteHeader } from "@/components/layout/site-header";
import { ButtonLink } from "@/components/ui/button";
import { Container } from "@/components/ui/section";

export default function NotFound() {
  return (
    <>
      <SiteHeader />
      <main id="conteudo" className="flex-1">
        <Container className="flex flex-col items-center py-28 text-center">
          <p className="font-display text-8xl text-sage-400">404</p>
          <h1 className="display-md mt-4">Não encontramos esta página.</h1>
          <p className="mt-3 max-w-md text-ink-600">
            O endereço pode ter mudado ou não existir. Volte ao início ou consulte a agenda.
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <ButtonLink href="/">Voltar ao início</ButtonLink>
            <ButtonLink href="/agenda" variant="secondary">
              Ver agenda
            </ButtonLink>
          </div>
        </Container>
      </main>
      <SiteFooter />
    </>
  );
}
