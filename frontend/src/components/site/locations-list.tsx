"use client";

import { MapPinned } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/states";
import { LocationCard } from "@/components/site/location-card";
import { api } from "@/lib/api";
import { useResource } from "@/lib/hooks/use-resource";

/**
 * Locais carregados da API. `variant="preview"` (página inicial) nunca exibe
 * erros alarmantes: se não houver dados, mostra uma mensagem discreta.
 */
export function LocationsList({
  variant = "full",
  limit,
}: {
  variant?: "full" | "preview";
  limit?: number;
}) {
  const { data, error, loading, reload } = useResource("locations", (signal) =>
    api.locations.list(signal),
  );

  if (loading) {
    return (
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3" role="status">
        <span className="sr-only">Carregando locais…</span>
        {[0, 1, 2].map((item) => (
          <Skeleton key={item} className="h-56" />
        ))}
      </div>
    );
  }

  if (error && variant === "full") {
    return <ErrorState error={error} onRetry={reload} />;
  }

  const locations = error ? [] : (data ?? []);
  const visible = limit ? locations.slice(0, limit) : locations;

  if (visible.length === 0) {
    return (
      <EmptyState
        icon={MapPinned}
        title="Os locais serão divulgados em breve"
        description="Assim que a coordenação confirmar os endereços e pontos de referência, eles aparecerão aqui e na agenda de cada sessão."
        action={
          variant === "preview" ? (
            <ButtonLink href="/locais" variant="secondary">
              Ver página de locais
            </ButtonLink>
          ) : undefined
        }
      />
    );
  }

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      {visible.map((location) => (
        <LocationCard key={location.id} location={location} compact={variant === "preview"} />
      ))}
    </div>
  );
}
