# Reiki UFRB

Plataforma de apresentação informativa sobre Reiki e organização de sessões semanais.

**O nome "Reiki UFRB" é provisório.** O vínculo institucional e a identidade oficial do projeto precisam ser confirmados antes da publicação definitiva. UFRB refere-se à Universidade Federal do Recôncavo da Bahia, mas a aprovação ou adoção institucional ainda não foi confirmada.

## Estrutura do repositório

### Frontend (implementado)

O frontend da aplicação está localizado na pasta `frontend/`. É uma aplicação Next.js com React, TypeScript e Tailwind CSS, já implementada e testada com dados de demonstração.

Para documentação detalhada do frontend, incluindo tecnologias, comandos de execução, testes e arquitetura, consulte:

- **[frontend/README.md](frontend/README.md)**

### Backend (planejado)

O backend será desenvolvido em Python com FastAPI e PostgreSQL. A implementação ainda não foi iniciada.

Os contratos de API propostos no frontend precisam ser confirmados antes da integração oficial.

## Estado atual

### Frontend

- ✅ Implementação concluída
- ✅ Testes estáticos aprovados (TypeScript, ESLint, build)
- ✅ Testes de navegador aprovados (98/98 verificações)
- ✅ Teste de produção aprovado (5/5 verificações)
- ✅ Teste de fumaça de rotas aprovado (18 rotas válidas)
- ⏳ Integração com API real (pendente de definição)
- ⏳ Autenticação e permissões (pendentes de implementação no backend)

### Backend

- ❌ Não implementado
- ⏳ Planejado: FastAPI + PostgreSQL
- ⏳ Contratos de API a definir

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
- Implementar e integrar a API real (backend)
- Validar a autenticação, as permissões e a persistência PostgreSQL
- Definir as regras institucionais pendentes
- Realizar revisão visual final em múltiplos dispositivos
- Configurar HTTPS, variáveis de produção e mecanismos de proteção de dados

## Licença

A ser definida.
