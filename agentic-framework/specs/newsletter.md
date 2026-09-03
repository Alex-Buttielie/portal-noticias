# Spec: Newsletter

## Contexto de negócio
BRD seção 27 (Newsletter) e seção 8 (retenção Premium — "resumo personalizado entregue no horário escolhido").

## Problema / oportunidade
Sem newsletter, o produto perde um canal de retenção/reengajamento citado explicitamente na estratégia de conteúdo (BRD §22) e no onboarding (`identidade/` já captura `canal_preferido`, incluindo e-mail).

## Histórias de usuário
- Como usuário, eu quero receber um resumo da manhã/noite por e-mail, para me atualizar sem abrir o app.
- Como usuário Premium, eu quero uma newsletter personalizada pelos meus interesses, não um resumo genérico.
- Como usuário, eu quero me descadastrar facilmente.

## Requisitos funcionais
1. Newsletter padrão (resumo da manhã, resumo da noite) — principais acontecimentos do período, reaproveitando `NewsCluster`/`NewsItem` já publicáveis.
2. Newsletter por categoria (usuário escolhe categorias de interesse).
3. Newsletter personalizada (Premium — usa `interesses`/`localidade` do onboarding) vs. edição padrão (Free, limitada — integrar com `gating-free-premium.md`, chave `newsletter_personalizada` já prevista no seed).
4. Links para fontes originais em cada item da newsletter (mesma regra de atribuição de `catalogo_noticias`).
5. CTA para cadastro/upgrade Premium no rodapé.
6. Descadastro simples (link direto, sem exigir login).
7. Envio via task periódica (Celery, mesmo padrão de `catalogo_noticias`/`assinatura`) — usa o `EMAIL_BACKEND` já configurado (console em dev).

## Requisitos não-funcionais
- Descadastro deve funcionar mesmo se o usuário não estiver logado (token de descadastro na URL, análogo aos tokens de `identidade/`).
- Nunca enviar para usuário sem consentimento de comunicação (reaproveita `consentimento_aceito_em`/canal preferido de `identidade/`).

## Fora de escopo
- Editor visual de template de e-mail (HTML de e-mail simples/texto é suficiente no MVP).
- A/B testing de assunto/conteúdo.
- Integração com provedor de e-mail transacional real em massa (mesma decisão em aberto de `identidade/` — `EMAIL_BACKEND`).

## Critérios de sucesso
- Um usuário consegue optar por receber a newsletter e, de fato, um envio de teste chega (via backend de console em dev) com o conteúdo esperado.
- Descadastro funciona sem exigir login.

## Questões em aberto
- Horário(s) exato(s) de disparo (manhã/noite) — parametrizável, valor inicial a definir com produto.
