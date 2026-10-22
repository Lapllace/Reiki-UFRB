"use client";

import { useAuth } from "@/lib/auth/auth-context";
import { useResource, type Resource } from "./use-resource";

interface Options {
  refreshInterval?: number;
}

/**
 * Como `useResource`, mas para dados da conta autenticada.
 *
 * - Nada é buscado enquanto o servidor não confirmar a sessão (`auth.me`).
 * - Durante essa confirmação, `loading` é verdadeiro: a página exibe o próprio
 *   esqueleto dentro do shell estático, em vez de um estado vazio enganoso.
 * - `scope = null` significa "ainda não dá para montar a consulta" (ex.: a
 *   semana atual só é conhecida após a hidratação) e também conta como carregando.
 * - A chave inclui o id do usuário: trocar de conta nunca reaproveita dados.
 */
export function useAccountResource<T>(
  scope: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: Options = {},
): Resource<T> {
  const { state, user } = useAuth();
  const resource = useResource(user && scope ? `${scope}:${user.id}` : null, fetcher, options);

  const waiting = state.status === "loading" || (scope === null && state.status === "authenticated");
  return waiting ? { ...resource, loading: true } : resource;
}
