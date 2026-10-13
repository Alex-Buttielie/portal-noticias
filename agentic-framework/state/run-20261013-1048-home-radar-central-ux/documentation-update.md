<!--
CONTRACT: documentation-update
DONO: documenter
QUANDO É CRIADO: depois que testes passam e a revisão (se exigida) está aprovada.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/documentation-update.md
-->

# Documentation Update — 20261013-1048-home-radar-central-ux

## Metadados
- **run_id:** 20261013-1048-home-radar-central-ux
- **Baseado em:** implementation-contract.md, implementation-history.md (Iterações 1-5) e code-review-contract.md (veredito final: approve) do run 20261013-1048-home-radar-central-ux.

## Documentos afetados
| Documento | Tipo de mudança | Resumo |
|---|---|---|
| `README.md` (raiz do projeto) — tabela "Endpoints disponíveis (módulo `radar`)` | atualização + nova linha | `GET /api/radar/tendencias/` e `GET /api/radar/evolucao/`: parâmetro `cidade` removido (nunca era populado de verdade) e documentado que `estado` agora aceita texto livre (sigla UF, nome do estado, nome de cidade, "Cidade, UF") resolvido automaticamente para a UF, e que `lat`/`lon` opcionais ordenam por proximidade. Nova linha para o endpoint novo `GET /api/radar/noticias/` (grid de notícias por região). Nota adicional sobre o limite de requisições anônimas (`EnderecosAnonThrottle`) reaproveitado pelas duas views públicas quando a resolução de `estado` cai no caminho de geocodificação externa. |
| `README.md` — tabela "Páginas disponíveis", linha `/radar` | atualização | Descrição trocada de "Tendências de notícias por localização, evolução histórica (recurso Premium) e localidades salvas" para refletir o redesenho em grade de cards com filtros/busca/ordenação por proximidade ou recência, preservando as abas de Tendências/Evolução/localidades salvas. |

## Sem impacto em documentação?
As mudanças dos Blocos H (Home) e C (Central/Admin) **não exigiram nenhuma edição de documentação do projeto**, pelos seguintes motivos, confirmados por leitura do `README.md`/`ARCHITECTURE.md` antes de editar:

- [x] Confirmado: o Bloco H (slider de manchete, correção de overflow em `NewsCard`, grid 2 colunas mobile, destaque visual, supressão de redundância do aviso de resumo-fallback) é inteiramente comportamento de UI/UX dentro de uma página já documentada de forma genérica ("`/` — Feed de notícias — busca, filtro por categoria, paginação") — o README nunca descreveu o layout interno da Home em detalhe (não há seção sobre `ManchetesGrid`/slider/cards), nem documenta os campos dos serializers do app `feed` (o próprio `/api/feed/` não tem uma tabela de endpoints no README, é só citado de passagem em 2 parágrafos). Criar uma seção nova só para `resumo_e_fallback` seria inconsistente com esse padrão e inflaria o README com um detalhe interno de serializer que não afeta como alguém usa ou mantém o produto.
- [x] Confirmado: o Bloco C (Central/Admin — criação de usuário pelo admin, leitura de `AuditoriaAdmin`/`FeatureLimitAlteracaoLog`, "ativos agora", responsividade em `/admin/robos`) toca exclusivamente o app `painel_admin`, cujo surface de API (16 endpoints, incluindo os pré-existentes de planos/limites/fila/assinaturas/moderação) **nunca foi documentado no README** — não existe seção "Endpoints disponíveis (módulo `painel_admin`)" nem as páginas `/admin`, `/admin/usuarios`, `/admin/robos`, `/admin/limites`, `/admin/configuracoes` aparecem na tabela "Páginas disponíveis" (só `/admin/metricas` aparece, por decisão de uma run anterior não revertida aqui). Documentar agora só os 5 endpoints novos deste run (`POST /api/admin/usuarios/`, `GET /api/admin/usuarios/ativos-agora/`, `GET /api/admin/auditoria/`, `GET /api/admin/limites/historico/`, `GET /api/admin/atividade-recente/`) sem o resto do CRUD já existente ficaria incompleto e confuso; documentar o módulo inteiro seria escopo muito maior que este run (documentar retroativamente endpoints pré-existentes não tocados aqui). Registro esta lacuna pré-existente para o orchestrator considerar como um run de documentação dedicado, se o admin backend algum dia precisar ser consumido por alguém além do próprio frontend `/admin/*` do projeto.
- [x] Confirmado: `ARCHITECTURE.md` é explicitamente um documento de arquitetura "do recorte MVP + Assinatura Premium" (linha 5: "Comunidade/Credenciamento de Jornalistas, B2B e Radar avançado ficam para fases posteriores e terão seu próprio documento de arquitetura incremental quando entrarem em escopo") — já está dessincronizado de propósito com módulos implementados depois dele (comunidade, credenciamento, b2b, moderação já existem e não aparecem na tabela de papéis/RBAC da seção 4). Não é um documento vivo que acompanha cada run; manter essa run alinhada a ele exigiria reescrever uma seção que o próprio projeto já tratou como histórica. Não editado.
- [x] Confirmado: não existe `CHANGELOG.md` neste projeto (busca por `CHANGELOG*` na raiz, `backend/` e `frontend/` não encontrou nenhum arquivo) — não há onde registrar uma entrada de changelog de produto/release.
- [x] Confirmado: não existem `README.md` próprios em `backend/` nem `frontend/` (só o `README.md` da raiz, mais READMEs de ferramentas de terceiros como `.pytest_cache/` e `infra/`, que não são deste projeto).
- [x] Confirmado: as 2 migrações Django novas (`identidade/migrations/0006_user_last_seen.py`, `catalogo_noticias/migrations/0014_registroexecucaoingestao_erro_falha_and_more.py`) são aditivas e não têm, neste projeto, uma seção de README que catalogue migrações individualmente (confirmado por busca — nenhuma migração anterior está listada no README) — não é um padrão deste projeto documentar migrações no README.
- [x] Confirmado: não foram introduzidas novas variáveis de ambiente/configuração por este run (`last_seen`/throttle de 60s são uma constante de código, `LAST_SEEN_THROTTLE_SEGUNDOS`, não uma env var; o throttle do Radar reaproveita a env var `THROTTLE_ENDERECOS_RATE` já existente e já referenciada na nova nota do README).

## Exemplos/snippets novos ou atualizados
Nenhum snippet de código novo adicionado ao README — as mudanças são de descrição de endpoints/páginas existentes em tabelas já estabelecidas (ver diff acima). Não havia exemplo de requisição ao Radar no README antes (só a linha de tabela), então não há exemplo antigo para corrigir.

## Entrada de changelog
Não aplicável — o projeto não mantém `CHANGELOG.md` (ver "Sem impacto em documentação?" acima).

## Verificação
- [x] Nenhum exemplo/trecho de documentação existente ficou contraditório com a mudança — revisado especificamente: a antiga menção a `cidade` na tabela do módulo `radar` foi removida e substituída; a descrição de `/radar` nas páginas disponíveis não promete mais filtro por cidade. Nenhuma outra menção a "Radar"/"cidade" (fora do Radar) no README precisava de ajuste (confirmado por `grep`).
- [x] Build/lint de documentação rodado (se o projeto tiver um) — não aplicável: não há markdownlint/remark/doc-build configurado neste projeto (confirmado por busca em `package.json` da raiz/backend/frontend e por ausência de `.markdownlint*`).
