# Atualização de documentação — 20260924-1000-p2-5-frontend

## Verificação

- `frontend/lib/datas.ts:1-10` foi confirmado como o helper central dos formatos editoriais, com `LOCALE_EDITORIAL = "pt-BR"` e `FUSO_EDITORIAL = "America/Sao_Paulo"`.
- `frontend/scripts/verificar-datas-tz.mjs:1-29` foi confirmado como smoke manual do helper; importa os formatadores reais e imprime uma saída JSON comparável entre processos com `TZ` diferente.
- O `README.md` já tinha uma seção de padrões de frontend (`## Design system`) e uma seção de privacidade/consentimento. A regra do AdSense foi colocada em privacidade, onde o gate de consentimento e os placeholders são explicados; a seção de rate limiting não precisava de alteração.
- Nenhum arquivo de código-fonte foi alterado nesta etapa.

## Alterações no README

- `README.md:323` (antes → depois): removida a afirmação obsoleta “nenhum script desse tipo existe no projeto hoje”; a regra geral de negar scripts não essenciais por padrão foi preservada e passou a refletir o AdSense existente.
- `README.md:323-324` (antes → depois): incluída a regra de que o script do Google AdSense só é carregado após consentimento em `personalizacao`, reage a mudanças de preferência, usa `lazyOnload` e mantém os slots como placeholders antes da autorização.
- `README.md:349-353` → `README.md:350-360` (antes → depois): a introdução da seção `## Design system` foi preservada; a orientação para novos componentes passou a incluir o uso do helper central de datas/horas. A subseção nova ocupa `README.md:354-358` e os tokens passaram a começar em `README.md:360`.
- `README.md:353-358` (antes → depois): adicionada a subseção `### Datas e horas (frontend/lib/datas.ts)`, com a regra de locale `pt-BR`, fuso fixo `America/Sao_Paulo` e prevenção de hydration mismatch; também registra o smoke manual `frontend/scripts/verificar-datas-tz.mjs` com Node 24/`--experimental-strip-types`.

## Resultado

O README agora fornece uma regra reutilizável para componentes futuros e documenta o comportamento de privacidade do AdSense sem misturá-lo com rate limiting. A verificação documental e as evidências de implementação permanecem nos artefatos da run.
