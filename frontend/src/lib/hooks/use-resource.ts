"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toApiError } from "@/lib/api/errors";

interface Settled<T> {
  key: string;
  token: string;
  data?: T;
  error?: ApiError;
}

export interface Resource<T> {
  data: T | undefined;
  error: ApiError | undefined;
  /** Primeira carga (ou troca de chave) em andamento: sem dados utilizáveis. */
  loading: boolean;
  /** Recarregando em segundo plano com dados anteriores ainda exibidos. */
  refreshing: boolean;
  reload: () => void;
}

interface Options {
  /** Atualização periódica em segundo plano (ms). Pausa quando a aba está oculta. */
  refreshInterval?: number;
}

/**
 * Carrega dados assíncronos com estados de carregamento/erro/vazio.
 *
 * - `key`: identifica a consulta. Mudou a chave, os dados antigos deixam de valer.
 *   `null` desativa a consulta (ex.: usuário ainda não identificado).
 * - `fetcher`: recebe um `AbortSignal` cancelado ao trocar a chave ou desmontar.
 */
export function useResource<T>(
  key: string | null,
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: Options = {},
): Resource<T> {
  const { refreshInterval } = options;
  const [nonce, setNonce] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const token = key === null ? null : `${key}#${nonce}`;

  useEffect(() => {
    if (key === null || token === null) return;
    const controller = new AbortController();
    fetcherRef
      .current(controller.signal)
      .then(
        (data) => {
          if (!controller.signal.aborted) setSettled({ key, token, data });
        },
        (error: unknown) => {
          if (!controller.signal.aborted) setSettled({ key, token, error: toApiError(error) });
        },
      );
    return () => controller.abort();
  }, [key, token]);

  useEffect(() => {
    if (!refreshInterval || key === null) return;
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") setNonce((value) => value + 1);
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, key]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  const sameKey = settled !== null && settled.key === key;
  const upToDate = settled !== null && settled.token === token;
  const hasData = sameKey && settled.data !== undefined;

  return {
    data: sameKey ? settled.data : undefined,
    // Um erro de uma consulta antiga não deve aparecer enquanto recarrega a nova.
    error: upToDate ? settled.error : undefined,
    loading: key !== null && !upToDate && !hasData,
    refreshing: key !== null && !upToDate && hasData,
    reload,
  };
}
