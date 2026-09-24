# Documentation Update — 20260923-1500-p1-6-react-query

Documenter da run `20260923-1500-p1-6-react-query`. O escopo foi verificar a documentação do produto após a remoção da camada React Query morta e das dependências órfãs. Nenhum arquivo de código-fonte foi alterado nesta etapa.

## Documentos verificados

- `README.md`, incluindo a seção **Observabilidade (Sentry opcional)** e a descrição da stack em **Como rodar o frontend**: não há menção a React Query, `@tanstack/react-query`, `@tanstack/react-table`, `embla-carousel-react`, `QueryClientProvider` ou aos hooks removidos. A stack de frontendcontinua correta como Next.js 14, TypeScript, Tailwind CSS e shadcn/ui/Radix; portanto, não foi necessária edição.
- `ARCHITECTURE.md`, especialmente a §1 **Decisões de stack**: o frontend é descrito somente como React/Next.js e não lista React Query nem as três dependências removidas. Não foi necessária edição.
- `frontend/package.json` e `frontend/package-lock.json`: as três dependências (`@tanstack/react-query`, `@tanstack/react-table` e `embla-carousel-react`) já estão ausentes do manifesto e do lockfile. A documentação de instalação (`npm install`/`npm ci`) permanece válida e não precisa listar dependências opcionais removidas.
- Demais documentos Markdown do produto: as referências restantes a React Query em `ANALISE_CUSTO_PERFORMANCE.md` descrevem o achado F1/P1-6 e o backlog que originou a run; são registros diagnósticos vivos, não documentação da stack atual, e foram preservadas. Referências em pastas de runs anteriores são histórico imutável.

## Alterações aplicadas

1. `implementation-history.md:86-87`: o follow-up da alternativa A foi tornado explícito. Uma futura migração dos 22 sites precisará reintroduzir `@tanstack/react-query`, reconstruir/reintroduzir o `QueryClientProvider` e o cliente correspondente, e reavaliar os 64 hooks apagados de `frontend/lib/queries.ts`; o texto também deixa claro que esses hooks não são contrato de API. Isso resolve o nit não bloqueante do reviewer sem reintroduzir código morto nesta run.
2. `documentation-update.md` (este artefato): registra as verificações acima e a decisão de não alterar `README.md` ou `ARCHITECTURE.md`.

## Resultado

Nenhuma documentação de produto precisou de ajuste. A única alteração documental foi o follow-up do artefato de implementação desta run. O código-fonte, o manifesto e o lockfile permanecem fora das alterações feitas pelo documenter.
