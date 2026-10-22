"use client";

import { Button, ButtonLink } from "@/components/ui/button";
import { Container } from "@/components/ui/section";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main id="conteudo" className="flex-1">
      <Container className="flex flex-col items-center py-28 text-center">
        <h1 className="display-md">Algo não saiu como esperado.</h1>
        <p className="mt-3 max-w-md text-ink-600">
          Ocorreu um erro ao exibir esta página. Tente novamente; se continuar, volte ao início.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button onClick={reset}>Tentar novamente</Button>
          <ButtonLink href="/" variant="secondary">
            Voltar ao início
          </ButtonLink>
        </div>
      </Container>
    </main>
  );
}
