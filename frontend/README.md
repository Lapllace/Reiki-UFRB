# Reiki UFRB — Frontend

Frontend de uma plataforma de apresentação informativa sobre Reiki e organização de sessões semanais. A interface contempla páginas públicas, consulta à agenda e áreas demonstrativas para participantes, ministrantes e coordenação.

O nome "Reiki UFRB" é provisório. O vínculo institucional e a identidade oficial do projeto precisam ser confirmados antes da publicação definitiva.

**Estado atual**: o frontend está implementado e validado com dados de demonstração. A integração completa com o backend e o PostgreSQL ainda depende da definição e implementação da API oficial.

## Tecnologias

- **Next.js 16.4.2**, com App Router
- **React 19.3.0**
- **TypeScript 5**
- **Tailwind CSS 4** com @theme custom e @tailwindcss/turbopack
- **Lucide React** para ícones
- **Zod 4.6.7** para validação de dados
- **Puppeteer Core**, opcional, para testes automatizados em navegador

A versão exata das dependências deve ser consultada no `package.json` e no `package-lock.json`.

## Como executar

### Requisitos

Node.js compatível com a versão instalada do Next.js e npm.

### Instalação e desenvolvimento

Na pasta `frontend/`:

```bash
npm install
npm run dev
```

Acesse `http://localhost:3000`.

### Build e execução de produção

```bash
npm run build
npm start
```

### Comandos de verificação

```bash
npm run lint
npx tsc --noEmit
```

## Variáveis de ambiente

Consulte `.env.example`:

- `NEXT_PUBLIC_API_URL`: URL-base do backend FastAPI, sem barra final. Deve ser definida quando a API estiver disponível.
- `NEXT_PUBLIC_DEMO_MODE`: controla a ativação do modo demonstrativo durante o desenvolvimento.

**Não publique segredos** em variáveis com prefixo `NEXT_PUBLIC_`. Essas variáveis podem ser expostas no navegador.

O comportamento esperado do modo demonstrativo é permitir testes locais com dados fictícios em memória. Os dados demonstrativos não devem ser confundidos com registros reais nem utilizados como persistência de produção.

## Funcionalidades da interface

### Páginas públicas

- Início
- Sobre o Reiki
- Como funciona
- Locais
- Agenda semanal
- Entrada e autenticação

### Área do participante

- Resumo das próximas sessões
- Consulta de inscrições e histórico
- Notificações
- Cancelamento, conforme as permissões e regras do sistema

### Área do ministrante

- Cadastro de disponibilidade semanal
- Consulta de sessões
- Cancelamento com motivo
- Consulta e resposta a convites de cobertura

### Área da coordenação

- Visão geral dos ciclos semanais
- Consulta de sessões e inscrições
- Acompanhamento de coberturas
- Reorganização de participantes
- Histórico de alterações

As áreas privadas dependem da autenticação e das permissões que serão efetivamente implementadas e verificadas pelo backend.

## Arquitetura do código

- `src/app/(site)/`: páginas públicas.
- `src/app/(painel)/`: páginas dos painéis.
- `src/components/site/`: componentes da área pública.
- `src/components/agenda/`: componentes da agenda.
- `src/components/painel/`: componentes dos painéis de usuário.
- `src/components/ui/`: componentes de interface reutilizáveis.
- `src/lib/api/`: cliente HTTP, contratos e serviços da API.
- `src/lib/demo/`: implementação demonstrativa com dados fictícios.
- `src/lib/hooks/`: hooks reutilizáveis.
- `src/lib/types.ts`: tipos usados no frontend.
- `src/content/`: conteúdo institucional, quando presente no projeto.
- `scripts/`: scripts de verificação e testes.

Confirme os caminhos diretamente no repositório quando reorganizar arquivos.

## Integração com a API

O frontend foi preparado para comunicar-se com um backend Python usando FastAPI e PostgreSQL.

Os endpoints e contratos existentes no código frontend são propostas e precisam ser confirmados antes da integração oficial.

Ainda precisam ser definidos ou validados:

- Contratos de autenticação e sessão.
- Formatos das disponibilidades e sessões.
- Inscrição, cancelamento e fila de espera.
- Convites simultâneos para cobertura de sessões.
- Reorganização de participantes e horários extras.
- Permissões dos participantes, ministrantes e coordenação.
- Regras institucionais de participação.

A estratégia prevista utiliza cookies `HttpOnly` gerenciados pelo servidor, mas o contrato definitivo de autenticação ainda precisa ser acordado.

## Regras importantes

- Não inventar endereços, horários ou dados institucionais.
- Informações ausentes devem permanecer identificadas como pendentes de confirmação.
- Uma inscrição só deve ser apresentada como confirmada após a resposta bem-sucedida do servidor.
- O primeiro ministrante cujo aceite for registrado com sucesso pelo servidor assume a cobertura.
- Dados de demonstração não representam inscrições oficiais.
- Os limites semestrais de participação e os prazos definitivos de cancelamento permanecem pendentes de definição.
- O conteúdo informativo sobre Reiki não deve prometer cura nem sugerir substituição de tratamentos médicos.

## Testes

### Verificação estática

```bash
npx tsc --noEmit
npm run lint
npm run build
```

### Teste de fumaça das rotas

```bash
node scripts/smoke-test.mjs dev
node scripts/smoke-test.mjs start
```

O teste de produção requer uma compilação concluída previamente.

### Testes em navegador real

```bash
npm install --no-save puppeteer-core
node scripts/browser-check.mjs
node scripts/prod-check.mjs
```

Os testes em navegador dependem de Chrome ou Edge instalado e da disponibilidade do servidor local. O script de produção verifica especificamente o comportamento sem uma API configurada.

Resultados anteriores registrados durante o desenvolvimento:

- TypeScript: aprovado.
- ESLint: aprovado.
- Build de produção: aprovado.
- Teste de navegador: 98/98 verificações aprovadas.
- Teste de produção: 5/5 verificações aprovadas.
- Teste de fumaça de produção: 18 rotas válidas com HTTP 200 e uma rota inexistente com HTTP 404.

Esses resultados correspondem à execução anterior. Repita os testes após novas alterações.

## Identidade visual e acessibilidade

A identidade visual utiliza marfim, verde-floresta, verde-sálvia, areia e detalhes em lavanda. Fraunces é utilizada nos títulos e Manrope nos textos.

O projeto inclui foco visível, link para pular ao conteúdo, atenção ao contraste, controles acessíveis por teclado e respeito à preferência por movimento reduzido.

Os testes automatizados não substituem uma auditoria completa de acessibilidade com leitor de tela.

## Antes de publicar

- Confirmar o nome e a identidade institucional.
- Implementar e integrar a API real.
- Validar a autenticação, as permissões e a persistência PostgreSQL.
- Definir as regras institucionais pendentes.
- Realizar revisão visual final em celulares, tablets e desktop.
- Executar novamente os testes.
- Configurar HTTPS, variáveis de produção e os mecanismos necessários de proteção de dados.
