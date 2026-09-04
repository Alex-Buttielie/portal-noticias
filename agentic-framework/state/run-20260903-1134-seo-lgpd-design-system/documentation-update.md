<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20260903-1134-seo-lgpd-design-system

## Metadados
- **run_id:** 20260903-1134-seo-lgpd-design-system
- **Baseado em:** implementation-history.md (20260903-1134-seo-lgpd-design-system), 4 iterações (executor → tester → remediator × 2), e code-review-contract.md (veredito final `approve_with_comments`, 0 blocker/major pendente)

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` | Nova seção + atualização de tabelas existentes | Nova seção "SEO técnico" (metadata, JSON-LD, sitemap/robots/RSS, canonical, como estender em novas páginas); nova seção "Privacidade e cookies (LGPD)" (banner, página de preferências, sincronização entre dispositivos, endpoint novo, aviso de rascunho jurídico bem visível); nova seção "Rate limiting" (throttle configurado, variável de ambiente, log de warning do Redis); nova seção "Design system" (tokens estendidos, os 7 componentes novos, regra explícita de nunca hardcodar cor/espaçamento); tabela "Endpoints disponíveis (módulo identidade)" ganhou a linha de `GET/PUT /api/preferencias-cookies/`; tabela "Páginas disponíveis" ganhou `/privacidade/politica` e `/privacidade/preferencias-cookies`. |
| `ARCHITECTURE.md` | Atualização de seção existente | Seção 7 (Requisitos não-funcionais transversais), item LGPD: acrescentada uma frase objetiva registrando que o consentimento de cookies (visitante e usuário autenticado) já está implementado, com o mesmo aviso de rascunho jurídico da política de privacidade, sem duplicar o conteúdo detalhado (que fica no README). |
| `agentic-framework/specs/README.md` | Nova seção | Seção nova ("Camada transversal fora do BRD original") explicando que SEO/LGPD/design system não vieram de nenhuma spec do BRD, existem agora como base compartilhada, e que futuras runs do backlog de UX/produto devem reutilizá-los em vez de reimplementar. |
| `agentic-framework/state/run-20260903-1134-seo-lgpd-design-system/implementation-history.md` | Verificação (sem edição) | As duas imprecisões numéricas apontadas como nit pelo reviewer ("9 testes"/"255 passed") **já não existem no arquivo** — a Iteração 4 já registra corretamente "10 testes" (linha ~615) e "256 passed" (linha ~654). Confirmado por grep (`9 test`, `255 passed`: zero ocorrências) antes de decidir não editar, para não gerar um diff artificial num arquivo compartilhado. Nenhuma alteração foi necessária. |

## Sem impacto em documentação?
Não se aplica — todos os documentos acima precisaram de atualização real (ver seção acima). O único item que teoricamente exigiria uma mudança (as duas imprecisões numéricas do `implementation-history.md`) já estava correto no momento em que esta verificação foi feita.

## Exemplos/snippets novos ou atualizados
- README.md, seção "SEO técnico": exemplo de `generateMetadata` + JSON-LD ao criar uma nova página de conteúdo, com referência a `frontend/lib/schema.ts`/`frontend/components/JsonLd.tsx`.
- README.md, seção "Design system": exemplo mínimo de uso de `Modal` e `Tabs`, e a lista dos tokens disponíveis por categoria (cor, espaçamento, tipografia, raio, sombra, z-index, dimensão de componente) com a convenção "todo valor novo de cor/espaçamento em CSS vira token em `globals.css`, nunca um literal solto".
- README.md, seção "Privacidade e cookies": trecho mostrando como consultar `permiteCategoria("analytics")` antes de inicializar qualquer script não essencial.

## Entrada de changelog
Não aplicável — o projeto não mantém um `CHANGELOG.md` próprio (busca por `CHANGELOG*` na raiz e nos subprojetos só encontra arquivos de dependências em `node_modules`, que não são deste projeto). Não foi criado um `CHANGELOG.md` novo porque isso seria uma decisão de processo maior que o escopo desta run (nenhuma outra parte do projeto usa esse padrão hoje); se o usuário quiser adotar changelog, é uma decisão a ser tomada explicitamente, não inferida aqui.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — revisão específica: a tabela "Páginas disponíveis" do README e a lista de módulos com endpoint do backend foram checadas contra o código real (`frontend/app/`, `backend/identidade/urls.py`) antes de editar, não coladas de memória.
- [x] Build/lint de documentação rodado (se o projeto tiver um) — o projeto não tem linter de Markdown nem build de docs configurado (nenhum `.markdownlint*`, nenhum script de docs em `package.json`/`pytest.ini`); nada para rodar.
