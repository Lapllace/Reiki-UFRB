import type { Metadata } from "next";
import Image from "next/image";
import { Suspense } from "react";
import { LoginForm } from "@/components/layout/login-form";
import { Skeleton } from "@/components/ui/states";
import { Container } from "@/components/ui/section";

export const metadata: Metadata = {
  title: "Entrar",
  description: "Acesse a sua área para se inscrever e acompanhar suas sessões.",
};

export default function LoginPage() {
  return (
    <Container className="py-12 sm:py-20">
      <div className="mx-auto grid max-w-5xl overflow-hidden rounded-[2rem] border border-line bg-paper shadow-lift lg:grid-cols-2">
        <div className="p-6 sm:p-12">
          <p className="eyebrow">Área do usuário</p>
          <h1 className="display-md mt-4 text-3xl sm:text-4xl">Entrar</h1>
          <p className="mt-3 text-ink-600">
            Participantes, ministrantes e coordenação acessam a sua área por aqui.
          </p>
          <div className="mt-8">
            <Suspense fallback={<Skeleton className="h-64" />}>
              <LoginForm />
            </Suspense>
          </div>
        </div>
        <div className="relative hidden min-h-full lg:block">
          <Image
            src="/images/sessao-luz.jpg"
            alt=""
            fill
            sizes="40vw"
            className="object-cover"
          />
          <div data-surface="dark" className="absolute inset-x-0 bottom-0 bg-forest-950/80 p-8 text-ivory">
            <p className="font-display text-2xl leading-snug">Um espaço de calma começa com informação clara.</p>
          </div>
        </div>
      </div>
    </Container>
  );
}
