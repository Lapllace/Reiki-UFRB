"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, toApiError } from "@/lib/api/errors";

interface Settled<T> {
  key: string;
  token: string;
  data?: T;
  error?: ApiError;
}

/** Recarga aguardando o desfecho da consulta que ela disparou. */
interface Waiter {
  key: string;
  token: string;
  resolve: (ok: boolean) => void;
}

export interface Resource<T> {
  data: T | undefined;
  error: ApiError | undefined;
  /** Primeira carga (ou troca de chave) em andamento: sem dados utilizáveis. */
  loading: boolean;
  /** Recarregando em segundo plano com dados anteriores ainda exibidos. */
  refreshing: boolean;
  /** Dispara uma recarga em segundo plano, sem aguardar o resultado. */
  reload: () => void;
  /**
   * Dispara uma recarga e resolve quando ela termina: `true` se os novos dados
   * chegaram, `false` se a consulta falhou, foi substituída por outra recarga ou
   * pela troca/desativação da chave. Permite que fluxos que dependem do sucesso
   * da atualização (ex.: recuperação após criar um ciclo) reajam corretamente.
   */
  reloadAsync: () => Promise<boolean>;
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
  const nonceRef = useRef(0);
  const waitersRef = useRef<Waiter[]>([]);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  const token = key === null ? null : `${key}#${nonce}`;

  const resolveWaiters = useCallback((waiterToken: string, ok: boolean) => {
    if (waitersRef.current.length === 0) return;
    const pending = waitersRef.current;
    waitersRef.current = pending.filter((waiter) => waiter.token !== waiterToken);
    for (const waiter of pending) {
      if (waiter.token === waiterToken) waiter.resolve(ok);
    }
  }, []);

  useEffect(() => {
    if (key === null || token === null) return;
    const controller = new AbortController();
    fetcherRef
      .current(controller.signal)
      .then(
        (data) => {
          if (controller.signal.aborted) return;
          setSettled({ key, token, data });
          resolveWaiters(token, true);
        },
        (error: unknown) => {
          if (controller.signal.aborted) return;
          setSettled({ key, token, error: toApiError(error) });
          resolveWaiters(token, false);
        },
      );
    return () => {
      controller.abort();
      resolveWaiters(token, false);
    };
  }, [key, token, resolveWaiters]);

  // Recargas pendentes de outra chave não têm mais como ser concluídas.
  useEffect(() => {
    const pending = waitersRef.current;
    if (pending.length === 0) return;
    const kept: Waiter[] = [];
    for (const waiter of pending) {
      if (waiter.key === key) kept.push(waiter);
      else waiter.resolve(false);
    }
    waitersRef.current = kept;
  }, [key]);

  // Desmontou: nenhuma recarga pendente ficará sem resposta.
  useEffect(() => {
    return () => {
      const pending = waitersRef.current;
      waitersRef.current = [];
      for (const waiter of pending) waiter.resolve(false);
    };
  }, []);

  const bumpNonce = useCallback(() => {
    nonceRef.current += 1;
    setNonce(nonceRef.current);
  }, []);

  const reloadAsync = useCallback((): Promise<boolean> => {
    if (key === null) return Promise.resolve(false);
    // Uma nova recarga substitui as anteriores desta mesma consulta.
    const previous = waitersRef.current;
    waitersRef.current = [];
    for (const waiter of previous) waiter.resolve(false);

    nonceRef.current += 1;
    const nextToken = `${key}#${nonceRef.current}`;
    const result = new Promise<boolean>((resolve) => {
      waitersRef.current.push({ key, token: nextToken, resolve });
    });
    setNonce(nonceRef.current);
    return result;
  }, [key]);

  const reload = useCallback(() => {
    void reloadAsync();
  }, [reloadAsync]);

  useEffect(() => {
    if (!refreshInterval || key === null) return;
    const interval = setInterval(() => {
      if (document.visibilityState === "visible") bumpNonce();
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, key, bumpNonce]);

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
    reloadAsync,
  };
}
