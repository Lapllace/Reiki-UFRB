# Reiki UFRB

Plataforma de apresentação informativa sobre Reiki e organização de sessões semanais.

**O nome "Reiki UFRB" é provisório.** O vínculo institucional e a identidade oficial do projeto precisam ser confirmados antes da publicação definitiva. UFRB refere-se à Universidade Federal do Recôncavo da Bahia, mas a aprovação ou adoção institucional ainda não foi confirmada.

## Estrutura do repositório

### Frontend (implementado)

O frontend da aplicação está localizado na pasta `frontend/`. É uma aplicação Next.js com React, TypeScript e Tailwind CSS, já implementada e testada com dados de demonstração.

Para documentação detalhada do frontend, incluindo tecnologias, comandos de execução, testes e arquitetura, consulte:

- **[frontend/README.md](frontend/README.md)**

### Backend (implementado em validação)

O backend está implementado em Python com FastAPI, SQLAlchemy e Alembic. Inclui
autenticação, disponibilidade, inscrições/fila, cobertura, reorganização,
sessões extras e consultas persistentes para as áreas do produto. A migração e
a concorrência PostgreSQL ainda precisam ser validadas em um banco real.

## Estado atual

### Frontend

- ✅ Implementação concluída
- ✅ Testes estáticos aprovados (TypeScript, ESLint, build)
- ✅ Testes de navegador aprovados (98/98 verificações)
- ✅ Teste de produção aprovado (5/5 verificações)
- ✅ Teste de fumaça de rotas aprovado (18 rotas válidas)
- ⏳ Integração com API real (pendente de definição)
- ✅ Autenticação e permissões implementadas no backend

### Backend

- ✅ Fundação FastAPI, autenticação e autorização
- ✅ Disponibilidade, inscrições, fila e cobertura
- ✅ Reorganização, sessões extras, notificações e eventos auditáveis
- ⏳ Migração/concorrência PostgreSQL e regras institucionais pendentes

## Como executar o frontend

Consulte [frontend/README.md](frontend/README.md) para instruções completas.

Resumo rápido:

```bash
cd frontend
npm install
npm run dev
```

Acesse `http://localhost:3000`.

## Pendências para publicação

- Confirmar o nome e a identidade institucional
- Executar e validar a API real com PostgreSQL
- Validar a autenticação, as permissões e a persistência PostgreSQL
- Definir as regras institucionais pendentes
- Realizar revisão visual final em múltiplos dispositivos
- Configurar HTTPS, variáveis de produção e mecanismos de proteção de dados

## Licença

A ser definida.
