# Decisões do solicitante — 2026-09-28

Registradas na ordem em que foram tomadas. Todas já aplicadas ou em execução.

## 1. Escopo e publicação

| Decisão | Efeito |
|---|---|
| Publicar até `main`; PROD **só** com R-1 assinado | A tag `v*` é o único gatilho de PROD e não sai sem o termo assinado |
| Nenhuma credencial nesta rodada | As 7 validações com credencial seguem **marcadas como pendentes**, nunca como verde |
| Cancelar **não** corta o período pago | Comportamento mantido e fixado em teste. Mais protetivo do pagante |
| Retenção de métricas: **90 dias** | Afeta custo e o documentado nos painéis |
| Provisionar os 2 pingeres **antes** de cadastrar os monitores | Monitor sem pinger paga sem avisar e treina o time a ignorar o canal |

## 2. Domínio

`portal-noticias.com` foi **comprado pelo solicitante** — o que explica
resolver para `162.240.81.81`, um IP que não responde. A decisão D-01
anterior (`.com`) está correta e a realidade instalada (`.com.br`) está
errada. Migrar.

| Autorizado | Estado |
|---|---|
| Migrar nginx e os 3 `.env` de `.com.br` para `.com` | pendente |
| Registrar também o `.com.br` | depende do solicitante, no registrador |
| Redirecionar `.com.br` → `.com` | pendente, depois da migração |
| Preparar tudo e **aguardar o DNS** | é o que está sendo feito |

**Hipótese a testar no painel:** `162.240.81.81` é provavelmente o **IP
anterior desta mesma VPS** (o hostname é
`vpsbr-15768701.vpshostgator.com.br`, padrão Hostgator). Se for, a correção
é **um registro A** e não há nada a configurar no servidor.

## 3. Infraestrutura — todas as correções autorizadas, na ordem proposta

| # | Correção | Estado |
|---|---|---|
| 1 | Fechar as portas expostas | **FEITO e verificado de fora** |
| 2 | Desligar senha e root login | **BLOQUEADO** — o `deploy.yml` usa `VPS_PASSWORD` |
| 3 | Backup | **3 quebras diagnosticadas**, em execução |
| 4 | TLS com certbot | bloqueado pelo DNS |
| 5 | Remover a regra da porta 22 | **FEITO** por consequência do reset do `ufw` |

Backup externo: **Cloudflare R2** — o `aws s3 cp` já existe no script
(`pg_backup.sh:70-71`) com `--endpoint-url`.

## 4. Pendências de código escolhidas

| Item | Estado |
|---|---|
| `picsum` sair do consentimento | Comentário falso **removido**; a correção em si é decisão de produto (o executor recusou escolher). **42 conexões na home**, não 6 |
| `b2b` contorna o gate de e-mail | em execução |
| Auditoria de incidente do `SocialAccount` | **FEITA — limpa** |
| Retenção após descadastro | em execução |

## 5. Revisão

O revisor independente **pode corrigir e reportar**, desde que a suíte e o
gate fiquem verdes de novo antes de entrar em `main`.

## 6. Auditoria de incidente — resultado

**Zero contas sociais em DEV, HOMOLOG e PROD.** A tabela
`socialaccount_socialaccount` existe e está **vazia nos três bancos**. O
blocker de sequestro de conta **não foi explorado** — nenhuma conta foi
vinculada pelo código vulnerável.

| Banco | Contas | Papéis | E-mail verificado |
|---|---|---|---|
| `brd_portal_dev` | 5 | 3 admin, 1 premium, 1 free | todos verificados |
| `brd_portal_homolog` | 5 | 3 admin, 1 premium, 1 free | todos verificados |
| `brd_portal_prod` | **2** | 2 admin | ambos verificados |

Leitura honesta: **zero linhas** quer dizer que não há evidência de
exploração nos dados. Não prova que nenhuma tentativa foi feita — o
endpoint era anônimo e `csrf_exempt`, e a exposição seria por requisição
direta. O que o dado diz é que **nenhuma conta foi comprometida**.

---

# Pendências que dependem do solicitante

| # | Pendência | Por quê |
|---|---|---|
| 1 | **O que é `162.240.81.81`** no painel da Hostgator | Define se a correção de DNS é um registro A ou algo mais. Bloqueia TLS, que bloqueia PROD |
| 2 | **Autorizar a 6ª mudança em `.github/`**: `VPS_SSH_KEY` e trocar `password:` por `key:` | Sem isso, desligar a senha do SSH **quebra o pipeline de deploy** |
| 3 | **`8080` e `8443`**: o Caddy do `plataforma-educacao`, outro aplicativo | Deixadas abertas. `8080` devolve `308`, cara de entrada pública real. Fechar pode derrubar outro sistema |
| 4 | **A chave do Firebase em `/tmp`**: `/tmp/backup-prod/secrets/firebase-service-account.prod.json`, 2.418 B, de 21 de setembro, **não é do portal** | Não toquei — é evidência e pode ser de outro sistema. É risco de credencial |
| 5 | **Credenciais** quando decidir retomá-las | `RESEND_API_KEY` é a urgente: **o cadastro responde 503** |
| 6 | **Assinar R-1** | Único portão de PROD |
| 7 | **Rotacionar a senha da VPS** | Ela está no histórico do chat desta sessão. Não a gravei em lugar nenhum |
