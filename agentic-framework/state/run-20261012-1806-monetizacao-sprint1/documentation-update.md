# Documentation Update — 20261012-1806-monetizacao-sprint1

## Metadados
- **run_id:** 20261012-1806-monetizacao-sprint1
- **Baseado em:** implementation-history.md (20261012-1806-monetizacao-sprint1), Iterações 1-13 (executor M-01..M-10, tester, remediator — 3 findings corrigidos), code-review-contract.md (veredito `changes_requested`, resolvido), implementation-contract.md.

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `docs/monetizacao/RESULTADOS.md` | Novo documento | Criado conforme pedido explícito da seção 6 do `PLANO_MONETIZACAO.md`. Lista os 10 itens (M-01 a M-10) com status real (todos concluídos), os 3 achados de revisão já corrigidos (resumidos em linguagem de negócio, sem repetir o `code-review-contract.md`), e as pendências reais fora de escopo deste sprint (preço/tabela comercial de patrocínio, patrocínio na newsletter, dependência de aprovação da conta Google AdSense para M-04 "ligar" de verdade, contraste marginal do selo em `CartaoPremium`, conformidade de consentimento para tráfego UE/UK/CH). |
| `README.md` (raiz) | Atualização | 3 mudanças: (1) seção "SEO técnico" — bullet de `sitemap.xml`/`robots.txt`/`rss.xml` passou a descrever corretamente que o sitemap consome o endpoint dedicado `GET /api/feed/sitemap/` (novo, M-02), não mais genericamente `/api/feed/`; (2) seção "Privacidade e cookies (LGPD)" — bullet de AdSense corrigido: não é mais verdade que "os slots permanecem placeholders antes da autorização" em produção (M-05 mudou isso — em produção some o texto técnico e aparece o cartão de assinatura do M-09); placeholder textual continua só em desenvolvimento; (3) mesma seção — novo bullet descrevendo o patrocínio direto (M-10): rótulo/link sempre visíveis mesmo sem consentimento, só o registro do evento depende de consentimento de `analytics`; (4) nova tabela "Endpoints disponíveis (módulo `patrocinio`)", no mesmo formato já usado para os outros 11 módulos documentados no README, cobrindo o endpoint novo `GET /api/patrocinio/ativo/`. |

## Sem impacto em documentação?
Não aplicável integralmente — ver decisões abaixo sobre o que **não** foi alterado e por quê, para que não pareça uma etapa pulada:

- **API pública de notícias (`GET /api/noticias/.../detalhe`, remoção do campo `conteudo` por M-01):** o `README.md` nunca documentou os endpoints do módulo `feed` em tabela (diferente de `identidade`, `assinatura`, `gating` etc. — é uma lacuna pré-existente, não introduzida por este sprint). Como nenhuma documentação existente menciona o campo `conteudo` como disponível, não há nada contraditório a corrigir. Não criei uma tabela nova e completa para o módulo `feed` nesta run — isso expandiria o escopo da documentação muito além do que M-01/M-02 exigem (seria documentar ~13 endpoints não tocados por este sprint); registrado aqui como lacuna conhecida e pré-existente, não como pendência desta run.
- **Documentação formal de API (OpenAPI/Swagger/schema):** confirmado que o projeto não usa `drf-yasg`, `drf-spectacular` nem qualquer gerador de schema (`grep` em `backend/config/settings.py` e `backend/requirements.txt` sem resultado) e não há nenhum arquivo de spec (`*.yaml`/openapi/swagger) em `backend/`. A única "documentação de API" do projeto são as tabelas manuais em `README.md`, por módulo. Por isso as mudanças de API deste sprint (M-01, M-02, M-10) foram refletidas ali, no formato já estabelecido (tabela nova para `patrocinio`; ajuste de texto para o sitemap), em vez de inventar um documento formal que o projeto não usa.
- **CHANGELOG:** não existe `CHANGELOG.md` na raiz, em `frontend/` nem em `backend/` (busca confirmada, nenhum resultado). Não criei um do zero — está fora do escopo desta run manter um changelog que o projeto nunca adotou.
- **`ARCHITECTURE.md`:** revisado (seções 2-10, RBAC, integrações) — as menções a "publicidade" ali (ex. "Visitante: ... ver publicidade"; "Premium: ... sem publicidade") são de nível de regra de negócio/permissão, continuam verdadeiras depois deste sprint (a regra não mudou: quem não é Premium continua podendo ver anúncio/patrocínio, quem é Premium continua sem ver nenhum dos dois). Nenhuma mudança necessária.
- **`.claude/skills/frontend-portal/SKILL.md`:** revisado; não describe comportamento de anúncio/placeholder que ficasse contraditório com M-04/M-05/M-06/M-09. Nenhuma mudança necessária.
- **`docs/monetizacao/AUDITORIA_ADSENSE.md`:** existe em outro worktree paralelo (`adsense-compliance`), não está mergeado nesta branch nem em `develop`/`main` até este momento. Por instrução explícita, não referenciei esse documento como fato consumado em `RESULTADOS.md` — mencionei a conformidade de consentimento para tráfego UE/UK/CH apenas como "está sendo avaliada separadamente", sem citar o arquivo.

## Exemplos/snippets novos ou atualizados
- `README.md`, bloco já existente de `permiteCategoria("analytics")` — não precisou de exemplo novo (o padrão de uso de consentimento já documentado se aplica sem alteração ao `PatrocinioSlot`/`trackPatrocinioView`/`trackPatrocinioClick`).
- Nenhum snippet de código novo foi necessário em `RESULTADOS.md` — é um documento de resultado de sprint, não um guia de uso de API.

## Entrada de changelog
Não aplicável — o projeto não mantém `CHANGELOG.md` em nenhum diretório (verificado, ausência confirmada). Nenhum arquivo criado para isso, conforme instrução de não inventar um changelog que o projeto não usa.

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — os 2 pontos identificados como potencialmente contraditórios (`sitemap.xml` descrito como consumindo só `/api/feed/` genérico; placeholder de AdSense descrito como sempre visível antes de "autorização", sem distinguir dev/produção pós-M-05) foram corrigidos no `README.md`.
- [ ] Build/lint de documentação rodado (se o projeto tiver um) — não aplicável: o projeto não tem linter de markdown nem build de documentação configurado (confirmado: nenhum `markdownlint`/`remark`/pipeline de docs em `package.json` de `frontend/` nem em workflows de CI relacionados a markdown).
