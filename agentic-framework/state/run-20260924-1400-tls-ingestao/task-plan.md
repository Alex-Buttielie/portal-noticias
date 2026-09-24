<!--
CONTRACT: task-plan
DONO: orchestrator
QUANDO É CRIADO: início da execução 20260924-1400-tls-ingestao
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-20260924-1400-tls-ingestao/
-->

# Task Plan — 20260924-1400-tls-ingestao

## Metadados
- **run_id:** 20260924-1400-tls-ingestao
- **Data de abertura:** 2026-09-24
- **Solicitado por:** humano (Alex), via sessão orquestradora
- **Spec de origem:** `ANALISE_CUSTO_PERFORMANCE.md` §6 (E1 e topologia), §7 (P0-3 e P2-7), complementado pelo pedido desta run

## Objetivo
Deixar a topologia PM2 + Nginx preparada para TLS com Certbot, sem ativar
HTTPS prematuramente, e registrar uma decisão operacional fundamentada sobre
o microserviço de ingestão, preservando o código existente e a decisão final
do humano.

## Escopo
### Dentro do escopo
- Adicionar HTTP→HTTPS, `listen 443 ssl` e caminhos de certificado Certbot
  parametrizados aos sites DEV/HOMOLOG/PROD, com exceção ACME HTTP-01 e
  health check interno que não Sofre redirect indevido.
- Atualizar o workflow reutilizável e os callers DEV/HOMOLOG/PROD para que os
  três flags de TLS só sejam gerados/validados como `true` quando a entrada
  `tls_enabled` for explicitamente habilitada após a ativação do edge.
- Tornar o exemplo `.env.production.example` coerente com TLS real na
  variante Caddy e documentar a sequência segura de bootstrapping.
- Acrescentar o runbook “Ativando TLS” em `infra/DEPLOY.md`, incluindo
  instalação/renovação do Certbot, renderização de domínio, `nginx -t`,
  reload, testes, ordem de ativação do Django e Cloudflare opcional.
- Produzir análise e recomendação do `ingestao-service/` em
  `PROD_DECISOES.md` e uma nota de status em `ingestao-service/README.md`.
- Criar e manter os artefatos desta execução e registrar decisões/evidências
  em `implementation-history.md`.

### Fora do escopo (explicitamente)
- Não emitir certificado, alterar DNS, instalar pacotes na VPS, recarregar
  Nginx, ativar Cloudflare ou alterar `.env` real: são passos humanos.
- Não tocar código Python/TypeScript de aplicação, nem o código do
  `ingestao-service/`.
- Não apagar, arquivar automaticamente, ativar ou composear o microserviço.
- Não escolher um domínio real, email de Certbot, IP, alias, conta Cloudflare
  ou regra de cache que o solicitante ainda não forneceu.
- Não prometer ganho de performance/custo sem medição.

## Suposições assumidas
- O domínio público e o certificado ainda não são conhecidos — motivo: o pedido
  exige parametrização e a ativação depende de DNS/valores da VPS; todos os
  marcadores ficam documentados para substituição humana.
- A topologia ativa é PM2 + Nginx e o frontend e a API compartilham o mesmo
  host via `/api/` — motivo: contexto fornecido e `CI-CD.md`; `DOMAIN_API`
  fica reservado à variante Docker/Caddy.
- O `.env` existente na VPS deve continuar sendo preservado — motivo: o
  workflow atual o cria uma vez; a ativação será uma edição explícita e um
  redeploy, não uma sobrescrita automática.
- Certbot/Let's Encrypt é a escolha técnica de origem — motivo: já é o
  padrão Debian/Ubuntu, funciona com ou sem Cloudflare e não exige trocar a
  CA quando a conta Cloudflare for opcional.

## Restrições
- Somente configuração, workflows e documentação; nenhum commit.
- Não introduzir domínio fictício nem segredo no repositório.
- `DJANGO_SECURE_SSL_REDIRECT=true` só pode ser ativado depois de o
  certificado existir, o vhost 443 passar `nginx -t`, o reload ser concluído
  e HTTPS ser testado.
- O challenge ACME precisa continuar acessível por HTTP; o probe interno de
  `/healthz` não pode depender de um redirect público nem falhar por causa
  do `SECURE_SSL_REDIRECT`.
- Preservar os ajustes P1-4 já presentes nos três sites e a proteção fail-
  closed de `media/credenciamento`.

## Divisão de trabalho
| Etapa | Agente responsável | Entrada esperada | Saída esperada |
|---|---|---|---|
| 1 | executor | implementation-contract.md | configuração/documentos + implementation-history.md |
| 2 | tester | implementation-contract.md e artefatos | veredito passed/failed/blocked + evidências |
| 3 | reviewer (gatilho de segurança/volume) | diff e contrato | code-review-contract.md |
| 4 | remediator (se necessário) | code-review-contract.md | correções + revalidação |
| 5 | documenter | histórico e contrato | documentation-update.md + documentação revisada |
| 6 | historian | todos os artefatos | report.md + entrada em HISTORY.md |

## Critérios de aceite (nível de negócio/produto)
1. Com os domínios e certificado reais fornecidos pelo operador, cada
   ambiente pode ser instalado no Nginx com HTTPS real, redirect do tráfego
   normal e renovação automatizada, sem suposição de um domínio específico.
2. O challenge HTTP-01 e o health check interno continuam operáveis durante
   a migração; o tráfego normal HTTP é redirecionado para HTTPS.
3. Um novo `.env` só recebe redirect e cookies `Secure` quando TLS foi
   explicitamente habilitado; um `.env` existente não é sobrescrito nem fica
   silenciosamente incoerente.
4. O operador encontra um runbook executável para instalar Certbot, obter o
   certificado, validar/recarregar o Nginx, ativar os flags, redeployar e
   verificar a renovação.
5. A documentação deixa claro que Cloudflare é opcional, requer conta do
   usuário e tem ganhos condicionais a medições.
6. A recomendação sobre `ingestao-service/` compara honestamente o pipeline
   Django atual com o microserviço, reconhece o painel HTML como diferencial,
   registra riscos e mantém o serviço desligado sem apagar o diretório.
7. Nenhum arquivo de código de aplicação é alterado por esta execução.

## Riscos identificados
| Risco | Impacto | Mitigação |
|---|---|---|
| Ativar redirect antes do certificado | alto | gate `tls_enabled`, ordem explícita e `.env` não sobrescrito |
| Marcadores de domínio esquecidos na VPS | alto | runbook de renderização, verificação de marcadores e `nginx -t` |
| ACME bloqueado pelo redirect | alto | location `^~ /.well-known/acme-challenge/` no vhost 80 |
| Health check interno redirecionado/indisponível | médio | location HTTP loopback + `X-Forwarded-Proto: https`; probe do workflow |
| Cloudflare ligado antes da origem | alto | seção opcional depois do TLS e modo Full (strict) |
| Ativar microserviço sem fonte de verdade definida | alto | recomendação de manter desligado e decisão humana explícita |
| MongoDB exposto ao host | alto | registrar risco; não subir o compose e exigir bind privado em futura run |

## Dependências
- Domínio real, alias opcional, email de Certbot, DNS e acesso SSH à VPS.
- `DOMAIN_API` só é necessário se a variante Docker/Caddy for realmente
  usada; na topologia PM2 o host é único e a API fica em `/api/`.
- Decisão humana sobre quando trocar `tls_enabled` para `true` em cada
  caller e sobre o destino futuro do `ingestao-service/`.
- Revisão formal deve ser considerada porque a mudança altera a superfície
  HTTP/TLS e o diff é maior que o limiar de volume de `review-triggers.md`.
