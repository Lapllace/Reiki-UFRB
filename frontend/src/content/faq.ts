export interface FaqItem {
  question: string;
  answer: string;
  /** `true` quando a resposta depende de definição da coordenação. */
  provisional?: boolean;
}

export const faq: FaqItem[] = [
  {
    question: "O que é o Reiki?",
    answer:
      "É uma prática complementar de bem-estar de origem japonesa, na qual a pessoa que conduz a sessão posiciona as mãos suavemente sobre ou próximo ao corpo de quem recebe, em um ambiente calmo. A proposta é oferecer um momento de pausa e relaxamento.",
  },
  {
    question: "O Reiki cura doenças?",
    answer:
      "Não. O Reiki não é um tratamento médico e não promete cura. Ele pode ser um momento de relaxamento e cuidado, mas não substitui consultas, exames, medicamentos ou acompanhamento psicológico e psiquiátrico. Continue seus tratamentos normalmente.",
  },
  {
    question: "Como me inscrevo em uma sessão?",
    answer:
      "Consulte a agenda semanal, escolha uma sessão com vaga, revise os detalhes e confirme a inscrição. A vaga só é considerada confirmada depois que o sistema responder. Para se inscrever é necessário entrar na sua conta.",
  },
  {
    question: "O que acontece se a sessão estiver lotada?",
    answer:
      "Quando houver fila de espera para a sessão, você poderá entrar nela. Se uma vaga for liberada, o sistema atualiza a sua situação e você pode acompanhar tudo na sua área pessoal.",
  },
  {
    question: "E se a sessão for cancelada ou o ministrante mudar?",
    answer:
      "Imprevistos acontecem. Quando houver cancelamento, mudança de ministrante ou reorganização de participantes, a alteração será comunicada na sua área pessoal. Os detalhes de cada caso dependem das regras definidas pela coordenação.",
  },
  {
    question: "Posso cancelar minha inscrição?",
    answer:
      "Sim, quando o sistema permitir. Na sua área pessoal, a opção de cancelar aparece junto de cada inscrição; se não for possível cancelar, a tela explica o motivo.",
  },
  {
    question: "Quanto tempo dura uma sessão e quem pode participar?",
    answer:
      "Essas informações ainda serão confirmadas pela coordenação. Assim que forem definidas, serão publicadas aqui e na agenda.",
    provisional: true,
  },
];
