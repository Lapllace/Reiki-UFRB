"use client";

import { useEffect, useState } from "react";

/**
 * Horário atual, disponível apenas após a hidratação (`null` antes disso).
 * Evita divergência entre pré-renderização e navegador e respeita as regras de
 * Cache Components, que proíbem ler o relógio durante a renderização.
 */
export function useNow(refreshMs = 60_000): Date | null {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    const tick = () => setNow(new Date());
    const first = setTimeout(tick, 0);
    const interval = setInterval(tick, refreshMs);
    return () => {
      clearTimeout(first);
      clearInterval(interval);
    };
  }, [refreshMs]);

  return now;
}
