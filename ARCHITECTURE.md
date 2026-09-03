# Arquitetura Técnica — Portal de Notícias

Documento complementar ao `BRD_portal_noticias_versao_1.docx`. Traduz as decisões de negócio em decisões técnicas transversais que orientam todas as specs em `agentic-framework/specs/` e, por consequência, todo `implementation-contract.md` gerado pelo `orchestrator`.

Este documento cobre o recorte **MVP + Assinatura Premium** (ver seção 31 do BRD). Comunidade/Credenciamento de Jornalistas, B2B e Radar avançado ficam para fases posteriores e terão seu próprio documento de arquitetura incremental quando entrarem em escopo.

## 1. Decisões de stack

| Camada | Decisão | Justificativa |
|---|---|---|
| Backend | Python — **Django + Django REST Framework** | O BRD exige um painel administrativo pesado desde o MVP (preços configuráveis, parametrização de limites Free/Premium, fila de decisões). O admin nativo do Django reduz drasticamente esse esforço. Alternativa considerada: FastAPI (mais leve, melhor para API pura), descartada por exigir construir o admin do zero. **Decisão em aberto:** confirmar Django+DRF ou preferência explícita por FastAPI + admin próprio. |
| Jobs assíncronos | Celery + Redis | Necessário para ingestão periódica de fontes de notícias, chamadas ao provedor de LLM (resumo/classificação) e envio de e-mails (onboarding, renovação), sem bloquear requisições HTTP. |
| Frontend | React (Next.js recomendado) | Escolha do usuário. Next.js dá SSR/SEO, importante para um portal de conteúdo. |
| Banco de dados | PostgreSQL | Escolha do usuário. Usar JSONB para metadados de notícias/fontes e para armazenar snapshots de decisões de dedup/classificação (auditoria). |
| Cache/fila | Redis | Suporta Celery e cache de feed/resumos. |
| Hospedagem | Cloud gerenciada (AWS ou GCP) | Escolha do usuário. **Decisão em aberto:** provedor específico — indicamos AWS (RDS Postgres, SQS/ElastiCache, ECS/Fargate) como referência até confirmação. |
| Autenticação | E-mail/senha + OAuth social (Google no mínimo) | Escolha do usuário. Usar biblioteca madura (ex: `django-allauth`) em vez de implementação própria de OAuth. |
| IA (resumo/classificação/dedup) | API de LLM de terceiros, atrás de uma interface abstrata (`SummarizationProvider`) | Escolha do usuário. Interface desacoplada permite trocar de provedor sem reescrever o pipeline de curadoria — mitiga o risco "Custo de IA/infraestrutura" listado na seção 30 do BRD. |
| Pagamento | Gateway abstrato (`PaymentGatewayProvider`), provedor concreto a definir | Escolha do usuário. Ver seção 6 abaixo — o desenho já isola estados de assinatura da implementação do gateway. |

## 2. Módulos macro (bounded contexts)

```
identidade/          cadastro, login, sessão, onboarding, perfil básico
catalogo-noticias/   ingestão de fontes, normalização, deduplicação, agrupamento
curadoria/           classificação de relevância, priorização, revisão humana
consumo/             feed, busca, categorias, resumo exibido, linha do tempo
assinatura/          planos, ciclo de vida, cobrança, histórico de pagamentos
gating/              matriz de recursos Free x Premium, limites parametrizáveis
admin/               parametrização (preços, limites), fila de revisão editorial
```

Cada módulo deve poder evoluir e ser implantado de forma desacoplada dos módulos de fases futuras (comunidade, credenciamento, B2B) — não introduzir dependência direta de código para features que ainda não existem.

## 3. Modelo de dados macro (não exaustivo)

Cada spec detalha os campos necessários ao seu escopo; aqui só as entidades que atravessam múltiplos módulos.

- **User** — id, email, senha (hash) ou provider OAuth, nome, papel (`free` \| `premium` \| `admin`), data de cadastro, preferências de onboarding (interesses, localidade, canal preferido).
- **Subscription** — id, user_id, plano, status (`teste`\|`ativa`\|`pagamento_pendente`\|`inadimplente`\|`cancelada`\|`expirada`\|`encerrada`), início, vencimento, gateway_reference (id externo opaco).
- **Plan** — id, nome, preço, periodicidade, ativo, parametrizado via admin (sem alteração de código, conforme seção 6 do BRD).
- **NewsItem** — id, título, resumo próprio, fonte(s) de origem, url original, categoria(s), timestamp, cluster_id (agrupamento de cobertura do mesmo acontecimento), flag urgente/normal, status de revisão humana.
- **NewsCluster** — id, acontecimento, lista de NewsItem relacionados, categoria dominante.
- **FeatureLimit** — chave, valor, plano aplicável — parametrização dos limites Free/Premium (seção 7 do BRD) via admin, sem deploy.

## 4. Papéis e permissões (RBAC deste recorte)

| Papel | Pode |
|---|---|
| Visitante (não autenticado) | Ver feed público, ler notícias, ver publicidade |
| Free | Tudo do visitante + busca, resumo, personalização limitada, alertas limitados |
| Premium | Tudo do Free + sem publicidade, personalização completa, alertas/resumo/newsletter/radar (básico) e histórico completos, conforme `FeatureLimit` |
| Admin | Parametrizar preços e limites de plano, ver fila de status de pagamento, sem acesso a funções de credenciamento/moderação (fora de escopo aqui) |

Papéis de Jornalista, Moderador e usuário B2B **não existem neste recorte** — não modelar tabelas/permissões para eles ainda; evitar overengineering para fases que ainda não têm spec.

## 5. Eventos de domínio (para desacoplamento entre módulos)

Publicados internamente (fila/pubsub, pode começar como sinais Django + Celery task antes de precisar de um broker de eventos dedicado):

- `noticia.ingerida`, `noticia.classificada`, `noticia.agrupada`
- `usuario.cadastrado`, `usuario.onboarding_concluido`
- `assinatura.ativada`, `assinatura.pagamento_recusado`, `assinatura.renovada`, `assinatura.cancelada`, `assinatura.expirada`
- `plano.preco_alterado` (para invalidar caches de preço exibido)

## 6. Integrações externas — contratos abstratos

Nenhuma spec de feature deve amarrar código de negócio diretamente a um SDK de terceiro. Definir interface própria e implementação concreta plugável:

- `NewsSourceProvider` — ingestão via RSS/API por fonte, deve preservar URL e identificação da fonte original (obrigatório pelo BRD §18).
- `SummarizationProvider` — resumo, classificação de relevância, deduplicação semântica.
- `PaymentGatewayProvider` — criar cobrança recorrente, consultar status, processar webhook, cancelar. Provedor concreto (Mercado Pago, Stripe, Pagar.me/Iugu) é decisão em aberto — a interface não deve vazar detalhes específicos de um provedor para o resto do sistema.

## 7. Requisitos não-funcionais transversais

- **LGPD:** consentimento explícito no cadastro/onboarding; direito de exclusão de dados do usuário mesmo com assinatura ativa/expirada (BRD §9, §18).
- **Direitos autorais:** todo `NewsItem` deve manter referência rastreável à fonte original; resumo deve ser conteúdo próprio, não cópia integral (BRD §18) — validar isso como critério de aceite em qualquer feature de ingestão/resumo.
- **Custo de IA controlado:** chamadas ao `SummarizationProvider` devem ser observáveis (contagem/custo por execução) desde o MVP — risco alto listado no BRD §30.
- **Auditoria:** alteração de preço/limite pelo admin deve ficar registrada (quem, quando, valor anterior/novo) — decorre da seção 17 do BRD (auditoria de alterações relevantes), mesmo estando fora do escopo de governança editorial completa.

## 8. Decisões em aberto (precisam de resposta humana antes ou durante a implementação)

1. ~~Django+DRF vs. outra combinação Python~~ — **resolvido**: mantido Django+DRF (ver seção 9).
2. Provedor concreto de gateway de pagamento — ainda em aberto.
3. Provedor concreto de LLM para resumo/classificação — ainda em aberto (interface `SummarizationProvider` já pronta para receber a chave real).
4. ~~Provedor de cloud específico~~ — **resolvido**: self-hosted na VPS HostGator já contratada, sem serviços gerenciados pagos adicionais (ver seção 9).
5. Fontes de notícia iniciais — **resolvido**: G1, UOL, CNN Brasil, Folha (RSS público), configuradas em `CATALOGO_NOTICIAS_FONTES_RSS`.

## 9. Nova arquitetura de infraestrutura (2026-09-03)

Análise disparada pelo pedido explícito do responsável do projeto para
repensar a arquitetura visando **menor custo, mais performance, segurança e
garantia de persistência dos dados**, motivado pelo risco "Custo de
IA/infraestrutura" (BRD seção 30, impacto Alto) — o ticket do plano Premium
é baixo (R$20/6 meses, R$30/12 meses), então o custo por usuário precisa
ficar próximo de zero para a margem sobreviver antes da fase de escala.

### 9.1 Decisão de stack tecnológico

**Mantido:** Django+DRF, PostgreSQL, Next.js/React. As 13 apps do backend já
implementam a totalidade das regras de negócio do BRD e passam 195 testes
automatizados (`backend/pytest.ini`) — reescrever esse núcleo em outra
stack (Go, Node, etc.) para uma VPS de 4GB+ economizaria uma diferença de
RAM irrelevante ao custo de meses reimplementando regras já testadas
(máquina de estados de assinatura com grace period, heurística de dedup com
falsos-positivos documentados, credenciamento, moderação, gating). O que
estava genuinamente ausente — e que esta seção define — é a **arquitetura
de infraestrutura de produção**, que antes desta mudança não existia.

### 9.2 Topologia (self-hosted, VPS única com Docker)

```
Internet → Cloudflare (CDN + WAF + DDoS + TLS, camada gratuita)
              → Caddy (reverse proxy, TLS automático via Let's Encrypt)
                  → Next.js standalone (frontend/Dockerfile)
                  → Gunicorn/Django (backend/Dockerfile)
                        → Redis (cache de aplicação + broker/result do Celery)
                        → PostgreSQL (dado transacional, com backup off-VPS)
                  → Celery worker + beat (ingestão, e-mails, vencimentos)
```

Toda a stack sobe com `docker compose --env-file .env.production up -d
--build` (ver `docker-compose.yml` na raiz). Sem RDS/ElastiCache/S3: o
único custo recorrente é a VPS já contratada. Detalhamento operacional em
`infra/DEPLOY.md`.

### 9.3 Como cada requisito foi endereçado

| Requisito | Decisão |
|---|---|
| **Custo** | Self-hosted numa VPS já paga; Cloudflare (CDN/WAF/DDoS) e Sentry/UptimeRobot no tier gratuito; mídia em disco local (não S3) até o volume justificar migração; chamadas ao LLM em lote com teto de tokens (já existente) + teto de gasto diário (`CATALOGO_NOTICIAS_LLM_TETO_GASTO_DIARIO_USD`, ver `config/settings.py`). |
| **Performance** | Cache Redis de aplicação (`CACHES` em `config/settings.py`, inexistente antes desta mudança); cache de borda via Cloudflare para conteúdo público (feed é majoritariamente leitura); WhiteNoise comprimido para estático; `CONN_MAX_AGE` para reuso de conexão com o Postgres. |
| **Segurança** | Settings de produção reais (HSTS, cookies seguros, `SECURE_PROXY_SSL_HEADER`, `X_FRAME_OPTIONS`); trava que impede rodar com SQLite ou `SECRET_KEY` fraca quando `DEBUG=False`; firewall (ufw) + fail2ban + atualizações automáticas na VPS (`infra/DEPLOY.md`); containers rodando com usuário não-root; rede Docker isolada — só o Caddy publica porta. |
| **Confiabilidade** | Healthcheck real (`/healthz`, checa conectividade com o banco) usado pelo Docker, pelo Caddy e por um monitor de uptime externo; CI (`.github/workflows/ci.yml`) roda a suíte completa antes de qualquer deploy; Sentry opcional para captura de erro em produção (mitiga a lacuna de validação registrada durante a implementação inicial). |
| **Persistência dos dados** | Backup diário automatizado (Postgres + mídia) enviado para storage externo compatível com S3 (`infra/backup/pg_backup.sh`), com runbook de restore testável (`infra/backup/RESTORE.md`) — volume Docker sozinho não é backup, só protege contra restart de container. |

### 9.4 Limites conscientes (não overengineering)

Decisões que ficam deliberadamente simples nesta escala, com o gatilho de
quando reconsiderar:

- **Mídia em disco local, não object storage:** revisitar quando o volume
  de uploads (diplomas de credenciamento, imagens de comunidade) se
  aproximar do disco disponível da VPS.
- **Um único servidor de aplicação, sem orquestração multi-nó:** revisitar
  quando o tráfego não couber mais em 2-4 vCPU/4GB+ mesmo com cache.
- **Multi-tenancy do B2B via FK + checagem em `services.py`, não
  schema-per-tenant:** revisitar se um cliente B2B Enterprise exigir
  isolamento de dado mais forte que RBAC por organização.
