/**
 * Informações INSTITUCIONAIS do projeto.
 *
 * Nada aqui foi confirmado ainda. Enquanto `value` for `null`, as páginas exibem
 * "A confirmar pela coordenação" em vez de inventar o dado. Para publicar uma
 * informação, preencha `value` e mude `status` para "confirmed".
 */
export type InstitutionalStatus = "confirmed" | "pending";

export interface InstitutionalField {
  label: string;
  value: string | null;
  status: InstitutionalStatus;
}

export const institutional = {
  sessionDuration: {
    label: "Duração de cada sessão",
    value: null,
    status: "pending",
  },
  sessionFormat: {
    label: "Formato do atendimento (individual ou em grupo)",
    value: null,
    status: "pending",
  },
  participantsPerSession: {
    label: "Número de participantes por sessão",
    value: null,
    status: "pending",
  },
  eligibility: {
    label: "Quem pode participar",
    value: null,
    status: "pending",
  },
  arrivalGuidance: {
    label: "Orientação de chegada e atrasos",
    value: null,
    status: "pending",
  },
  contactEmail: {
    label: "E-mail de contato",
    value: null,
    status: "pending",
  },
  contactPhone: {
    label: "Telefone / WhatsApp",
    value: null,
    status: "pending",
  },
} satisfies Record<string, InstitutionalField>;
