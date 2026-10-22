import { Compass, MapPin, MapPinOff } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PendingValue } from "@/components/ui/provisional";
import type { Location } from "@/lib/types";

/** Apresenta um local de atendimento. Campos ausentes são marcados como pendentes, nunca inventados. */
export function LocationCard({ location, compact }: { location: Location; compact?: boolean }) {
  return (
    <Card className="flex h-full flex-col">
      <div className="flex items-start gap-4">
        <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-sage-100 text-forest-700">
          <MapPin className="size-6" aria-hidden />
        </span>
        <div className="min-w-0">
          <h3 className="font-display text-2xl text-forest-900">{location.name}</h3>
          <p className="mt-1 text-ink-700">{location.address ?? <PendingValue>Endereço a confirmar</PendingValue>}</p>
        </div>
      </div>

      {!compact ? (
        <dl className="mt-6 space-y-4 text-[0.95rem]">
          <div className="flex gap-3">
            <Compass className="mt-1 size-4 shrink-0 text-sage-600" aria-hidden />
            <div>
              <dt className="font-semibold text-forest-900">Como chegar</dt>
              <dd className="text-ink-700">
                {location.reference ?? <PendingValue>Ponto de referência a confirmar</PendingValue>}
              </dd>
            </div>
          </div>
          {location.notes ? (
            <div className="rounded-xl bg-sand-50 px-4 py-3 text-ink-700">{location.notes}</div>
          ) : null}
        </dl>
      ) : null}

      <div className="mt-auto pt-6">
        {location.mapUrl ? (
          <ButtonLink
            href={location.mapUrl}
            external
            variant="secondary"
            size="sm"
            icon={<MapPin className="size-4" aria-hidden />}
          >
            Abrir no mapa<span className="sr-only"> ({location.name}, abre em nova aba)</span>
          </ButtonLink>
        ) : (
          <p className="flex items-center gap-2 text-sm text-ink-600">
            <MapPinOff className="size-4" aria-hidden />
            Link de mapa ainda não informado.
          </p>
        )}
      </div>
    </Card>
  );
}
