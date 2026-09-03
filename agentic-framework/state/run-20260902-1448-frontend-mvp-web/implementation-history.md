<!--
CONTRACT: implementation-history
DONO: executor (cria e adiciona entradas) / tester, remediator, historian (adicionam entradas)
QUANDO É CRIADO: junto com a primeira ação do executor sobre o implementation-contract.md.
PARA ONDE VAI A INSTÂNCIA: agentic-framework/state/run-<run_id>/implementation-history.md
NATUREZA: append-only durante a execução — cada entrada é uma iteração, nunca se edita uma entrada anterior.
-->

# Implementation History — 20260902-1448-frontend-mvp-web

## Iteração 1 — 2026-09-02 — orchestrator agindo como executor (ferramentas de execução/build/preview ainda indisponíveis)

**Quem implementou e por quê:** mesma situação dos 4 runs de backend anteriores nesta sessão — `Agent`/`Bash`/preview do navegador seguem indisponíveis (testado explicitamente antes de começar: `mcp__Claude_Browser__navigate` também recusado pelo mesmo classificador). Diferente do backend Python, este é o primeiro código **frontend** (TypeScript/JSX) da sessão — risco estrutural maior, pois erros de sintaxe/tipo só apareceriam ao rodar `npm install`/`next build`, que não pude executar.

**O que foi feito:** scaffold completo de um app Next.js 14 (App Router, TypeScript, sem framework de CSS) em `frontend/`, consumindo os 3 módulos de backend já implementados: `identidade` (cadastro, login, verificação de e-mail, recuperação/redefinição de senha, onboarding), `feed` (listagem, busca, categoria, detalhe de cluster/item), `assinatura` (planos, assinar, cancelar, status, histórico de pagamentos).

### Estrutura de pastas criada

```
frontend/
  package.json, tsconfig.json, next.config.js, next-env.d.ts
  .env.local.example, .gitignore
  lib/
    api.ts               # cliente HTTP central, tipado, 1 função por endpoint
    auth-context.tsx      # React Context: token/usuário em localStorage
  components/
    Header.tsx             # navegação + estado de login/plano
    DetalheNoticia.tsx      # compartilhado entre as 2 rotas de detalhe (cluster/item)
  app/
    layout.tsx, globals.css, page.tsx                       (feed/home)
    cadastro/page.tsx
    login/page.tsx
    verificar-email/page.tsx + VerificarEmailConteudo.tsx    (Suspense — useSearchParams)
    recuperar-senha/page.tsx
    redefinir-senha/page.tsx + RedefinirSenhaConteudo.tsx    (Suspense — useSearchParams)
    onboarding/page.tsx
    noticia/cluster/[id]/page.tsx
    noticia/item/[id]/page.tsx
    planos/page.tsx
    minha-conta/page.tsx
```

### Decisões técnicas (dentro da liberdade deixada pelo contrato)

1. **Antes de escrever qualquer chamada de API, li `identidade/serializers.py` e `identidade/views.py` inteiros** para confirmar os nomes EXATOS de campo esperados pelo backend (`senha` não `password`, `aceite_termos`, `nova_senha`, `uid`+`token` separados para redefinição) — não adivinhei nenhum payload. `feed`/`assinatura` já estavam frescos na memória desta sessão (implementados por mim mesmo nas execuções anteriores).
2. **Descoberta de bug real durante essa leitura: CORS não estava configurado no backend.** O frontend (`localhost:3000`) chamando o backend (`localhost:8000`) via `fetch()` do navegador seria bloqueado pela política de mesma origem sem cabeçalhos CORS. Adicionei `django-cors-headers` ao backend (`config/settings.py`: `INSTALLED_APPS`, `MIDDLEWARE` — `CorsMiddleware` antes de `CommonMiddleware`, conforme documentação da lib — e `CORS_ALLOWED_ORIGINS = [FRONTEND_BASE_URL]`) e ao `requirements.txt`. **Isso é uma mudança no backend, fora do escopo nominal deste contrato de frontend, mas sem ela o frontend inteiro não funcionaria** — sinalizado aqui com transparência, não escondido.
3. **Rotas de e-mail já ditavam a URL do frontend:** `identidade/emails.py` já linkava para `{FRONTEND_BASE_URL}/verificar-email?token=...` e `{FRONTEND_BASE_URL}/redefinir-senha?uid=...&token=...` (escrito na execução de `identidade`, antes de qualquer frontend existir) — as rotas `app/verificar-email/` e `app/redefinir-senha/` foram criadas com esses nomes exatos para bater com os links que o backend já envia por e-mail.
4. **`useSearchParams` exige um limite de `Suspense`** no App Router do Next.js (o `next build` falha sem isso, conhecimento de framework, não pude confirmar rodando) — por isso `verificar-email` e `redefinir-senha` foram divididos em um `page.tsx` fino (Suspense) + um componente de conteúdo separado.
5. **Sem Tailwind/framework de CSS** (task-plan.md, suposição já registrada) — `app/globals.css` com CSS puro, para não introduzir um passo de build (PostCSS) que não posso validar nesta sessão.
6. **Token em `localStorage`**, não cookie httpOnly — mais simples sem um backend-for-frontend; risco de XSS registrado como follow-up de segurança para quando o produto crescer (mesma nota do task-plan.md).
7. **`DetalheNoticia.tsx` compartilhado** entre as rotas de cluster e item (mesmo formato de resposta `FeedDetalhe`, só muda qual função de `lib/api.ts` é chamada) — evita duplicar a lógica de carregamento/erro/404 em 2 arquivos quase idênticos.

### Validação: **NÃO REALIZADA — risco mais alto de toda a sessão**

Nenhum comando de execução funcionou (`npm install`, `next build`, `next dev`, nem a preview do navegador). Diferente do backend Python (onde erros de sintaxe são relativamente raros em código bem estruturado e a maior parte do risco era lógica de negócio), **código TypeScript/JSX tem uma superfície de erro muito maior que só aparece em tempo de build/execução**: erros de tipo, imports quebrados, sintaxe JSX malformada, incompatibilidade de versão entre pacotes. Fiz uma revisão manual cuidadosa (conferindo cada import contra o que de fato é exportado, tipos de retorno consistentes entre `lib/api.ts` e os componentes que os consomem, uso de `Suspense` onde o framework exige), mas isso é qualitativamente menos confiável do que rodar `next build` de verdade.

**Ação necessária antes de considerar este módulo pronto — MAIS IMPORTANTE do que para qualquer módulo de backend:**
```
cd C:\alex\brd_portal_noticias\frontend
npm install
npm run build
npm run dev   # depois, para testar manualmente contra o backend rodando em outra aba/terminal
```
Também é necessário, no backend, rodar `pip install -r requirements.txt` (para instalar `django-cors-headers`, recém-adicionado) e reiniciar o `manage.py runserver` antes de testar a integração de ponta a ponta.

**Arquivos tocados:**
- `frontend/` inteiro (novo — ver estrutura acima)
- `backend/config/settings.py` (modificado — `INSTALLED_APPS`, `MIDDLEWARE`, `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS`)
- `backend/requirements.txt` (modificado — `django-cors-headers==4.9.0`, versão não confirmada por instalação real)
