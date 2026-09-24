# Relatório final — P2-5 Frontend

**Run:** `20260924-1000-p2-5-frontend`
**Status:** entregue (`approve_with_comments` na re-revisão da iteração 2)
**Escopo:** otimizações de frontend da Home, telemetria de notícias, consentimento de publicidade e padronização de datas.

## Objetivo

Reduzir tráfego e trabalho repetidos no frontend sem mudar contratos de backend, sem criar uma nova camada de cache e sem reintroduzir o React Query removido pela P1-6. A execução também deveria preservar SSR/hidratação, UX, telemetria e a política de consentimento.

## Entregas

- **Colunistas no servidor/ISR:** `frontend/app/page.tsx` passou a carregar `carregarColunistas(4)` no Server Component e passou os dados por props para a Home. `SecaoColunistas` ficou apresentacional, sem `useEffect`/`useState` de rede; a cascata client-side de publicações em destaque, fallback e perfis deixou de ocorrer por visita. Falhas continuam degradando a seção opcional para lista vazia, sem dados inventados.
- **Polling de últimas notícias:** a frequência foi reduzida, com o intervalo padrão passando de 90 s para 180 s; valores positivos persistidos são normalizados para a faixa de 180–600 s e a guarda de aba oculta foi preservada. O botão de atualização manual continua disponível e usa o mesmo caminho de `obterFeed`.
- **AdSense com consentimento:** `AdsScript` e `AdsSlot` condicionam a publicidade à categoria `personalizacao`, escutam alterações de preferências, e o script usa `lazyOnload`. Sem publisher ID, slot ou autorização, não há chamada externa e o placeholder é preservado. A copy de consentimento explicita “publicidade de terceiros, como AdSense”.
- **Fonte única de `news_view`:** `NoticiaReporter` é a única fonte do evento `news_view`, preservando `entry_tipo`, `entry_id`, categoria, tempo de leitura e scroll. A duplicação derivada do pathname no `AnalyticsTracker` foi removida; as demais métricas e o clique de notícia foram preservados.
- **Helper central de datas/hora:** `frontend/lib/datas.ts` centraliza os formatos com locale `pt-BR` e fuso editorial fixo `America/Sao_Paulo`, evitando divergência de SSR/hidratação. A centralização foi aplicada a **23 arquivos de apresentação de data/hora**; os usos numéricos de métricas também receberam locale explícita.
- **Resiliência dos colunistas:** a listagem de publicações recebeu deadline de 5 s para o ISR e cada perfil recebeu timeout/abort independente de 2 s. Uma falha de listagem retorna `[]`; um perfil lento apenas degrada os campos opcionais do card, sem cancelar os demais perfis nem bloquear indefinidamente a Home.

## Validações

- `frontend/npx tsc --noEmit`: exit code 0.
- `frontend/npm run build`: exit code 0; Next.js 14.2.15 gerou **59/59 páginas**.
- Smoke standalone HTTP registrado na execução: `/`, `/noticia/1` e `/comunidade` responderam HTTP 200; as respostas não continham `Application error`, `Module not found`, `Cannot find module` nem URL do AdSense no build sem publisher ID.
- `frontend/scripts/verificar-datas-tz.mjs` foi executado com Node 24 e `--experimental-strip-types` sob `TZ=UTC`, `TZ=Asia/Tokyo` e `TZ=America/Sao_Paulo`. As três saídas JSON foram idênticas e o `cmp` entre os arquivos retornou igualdade nos três fusos.
- `git diff --check` e o inventário final de formatadores passaram; não houve chamada temporal direta fora do helper central.

## Revisão e remediação

1. A revisão inicial retornou `changes_requested`: foi identificado um `major` de mismatch de data de colunista no SSR/hidratação, além de notas de consentimento e payload/latência.
2. Na **remediação da iteração 1**, o date formatter do colunista foi fixado em `America/Sao_Paulo`, a copy de consentimento foi alinhada e a carga recebeu paginação/normalização e timeouts. O finding original de data foi resolvido, mas a re-revisão independente encontrou um `major` sistêmico: os demais formatadores compartilhados ainda dependiam do fuso.
3. Na **remediação da iteração 2**, `frontend/lib/datas.ts` passou a ser a implementação única e os 23 arquivos de apresentação de data/hora foram migrados. Também foi ajustado o orçamento de publicações/perfis. A re-revisão da iteração 2 confirmou a correção do problema sistêmico e retornou **`approve_with_comments`**, com um residual menor do Radar e limitações de projeção/validação registradas como follow-up.

## Documentação e histórico

- `documentation-update.md` registra a verificação e as alterações de documentação do produto.
- O `README.md` agora orienta o uso do helper central de datas/horas com fuso editorial fixo e documenta que o AdSense só é carregado após consentimento em `personalizacao`.
- Nenhum código-fonte foi alterado pelo documenter/historian nesta etapa; nenhuma dependência, backend ou infraestrutura foi modificada.

## Follow-ups

1. **Radar (minor):** `p.dia` é uma data civil `YYYY-MM-DD`; a conversão atual pode ser interpretada como UTC e exibir o dia anterior. Corrigir com parsing de data civil, sem depender do fuso do processo.
2. **Smoke de timezone:** `frontend/scripts/verificar-datas-tz.mjs` depende de Node 24 e `--experimental-strip-types`, e hoje é um check manual, não um gate de CI. Pode ser tornado portátil/assertivo e adicionado ao CI.
3. **payload completo do perfil de autor:** o endpoint de perfil ainda pode devolver a lista pública completa de publicações; uma future run de API deve avaliar projeção/limite dos campos necessários à Home.
4. **React Query:** a camada foi removida deliberadamente nesta frente. Se o React Query voltar em uma decisão futura, ele precisará ser reintroduzido explicitamente, com consumidor, dependências e estratégia de cache coerentes; não deve ser ressuscitado por herança incidental.
