"use client";

import { lazy, Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { z } from "zod";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/form";
import { ProvisionalNote } from "@/components/ui/provisional";
import { ApiError, toApiError } from "@/lib/api/errors";
import { homeForRole, useAuth } from "@/lib/auth/auth-context";
import { fieldErrors, safeNextPath } from "@/lib/forms";

// Condição literal para o bundler eliminar a demonstração em produção (veja src/lib/config.ts).
const DemoLogin =
  process.env.NODE_ENV !== "production" && process.env.NEXT_PUBLIC_DEMO_MODE === "true"
    ? lazy(() => import("@/lib/demo/demo-login"))
    : null;

const schema = z.object({
  email: z.string().trim().min(1, "Informe o seu e-mail.").pipe(z.email("Digite um e-mail válido, como nome@exemplo.com.")),
  password: z.string().min(1, "Informe a sua senha."),
});

export function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNextPath(params.get("next"));
  const { user, login } = useAuth();

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (user) router.replace(next ?? homeForRole(user.role));
  }, [user, next, router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const parsed = schema.safeParse({
      email: form.get("email"),
      password: form.get("password"),
    });
    if (!parsed.success) {
      const found = fieldErrors(parsed.error);
      setErrors(found);
      setFormError(null);
      const first = Object.keys(found)[0];
      formRef.current?.querySelector<HTMLInputElement>(`[name="${first}"]`)?.focus();
      return;
    }
    setErrors({});
    setFormError(null);
    setPending(true);
    try {
      const loggedIn = await login(parsed.data);
      router.replace(next ?? homeForRole(loggedIn.role));
    } catch (caught) {
      const error = toApiError(caught);
      setFormError(
        error instanceof ApiError && (error.kind === "unauthenticated" || error.kind === "validation")
          ? "E-mail ou senha não conferem. Confira os dados e tente novamente."
          : error.message,
      );
    } finally {
      setPending(false);
    }
  }

  if (DemoLogin) {
    return (
      <Suspense fallback={null}>
        <DemoLogin next={next} />
      </Suspense>
    );
  }

  return (
    <form ref={formRef} onSubmit={onSubmit} noValidate className="space-y-5">
      {formError ? <Alert tone="danger">{formError}</Alert> : null}
      <TextField
        label="E-mail"
        name="email"
        type="email"
        autoComplete="username"
        inputMode="email"
        required
        error={errors.email}
      />
      <TextField
        label="Senha"
        name="password"
        type="password"
        autoComplete="current-password"
        required
        error={errors.password}
      />
      <Button type="submit" size="lg" fullWidth loading={pending}>
        Entrar
      </Button>
      <ProvisionalNote>
        O método de acesso (por exemplo, login institucional) ainda será definido junto ao backend.
        Este formulário envia os dados ao endpoint de autenticação configurado; nenhuma senha é
        guardada no navegador.
      </ProvisionalNote>
    </form>
  );
}
