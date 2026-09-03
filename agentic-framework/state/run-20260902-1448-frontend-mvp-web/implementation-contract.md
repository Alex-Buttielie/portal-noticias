# Implementation Contract — 20260902-1448-frontend-mvp-web

## Metadados
- **run_id:** 20260902-1448-frontend-mvp-web
- **Deriva de:** task-plan.md (20260902-1448-frontend-mvp-web)
- **Versão do contrato:** 1

## O que deve ser construído
Aplicação Next.js (App Router, TypeScript) em `frontend/` consumindo os endpoints de `identidade`, `feed` e `assinatura` já implementados no backend Django. Cliente de API central, contexto de autenticação, layout compartilhado, e as páginas listadas em "Áreas/arquivos esperados".

## Áreas/arquivos esperados
```
frontend/
  package.json, tsconfig.json, next.config.js, .env.local.example
  app/
    layout.tsx, globals.css, page.tsx                     (feed/home)
    cadastro/page.tsx
    login/page.tsx
    verificar-email/page.tsx
    recuperar-senha/page.tsx
    redefinir-senha/page.tsx
    onboarding/page.tsx
    noticia/cluster/[id]/page.tsx
    noticia/item/[id]/page.tsx
    planos/page.tsx
    minha-conta/page.tsx
  lib/
    api.ts             (cliente HTTP central)
    auth-context.tsx    (React Context: token, usuário, papel)
  components/
    Header.tsx, FeedCard.tsx, (outros conforme necessário)
```

## Interfaces afetadas
Nenhuma API nova — consome exclusivamente os endpoints já existentes:
- `identidade`: `/api/auth/cadastro/`, `/api/auth/verificar-email/`, `/api/auth/login/`, `/api/auth/logout/`, `/api/auth/recuperar-senha/`, `/api/auth/redefinir-senha/`, `/api/onboarding/`
- `feed`: `/api/feed/`, `/api/feed/cluster/<id>/`, `/api/feed/item/<id>/`
- `assinatura`: `/api/assinatura/planos/`, `/api/assinatura/assinar/`, `/api/assinatura/cancelar/`, `/api/assinatura/minha/`, `/api/assinatura/historico-pagamentos/`

## Critérios de aceite (técnicos, testáveis)
1. `app/cadastro/page.tsx` envia `POST /api/auth/cadastro/` com e-mail/senha/aceite de termos; exibe mensagem de sucesso pedindo para checar o e-mail.
2. `app/verificar-email/page.tsx` lê o token da query string e envia `POST /api/auth/verificar-email/`, mostrando sucesso/erro.
3. `app/login/page.tsx` autentica via `POST /api/auth/login/`, guarda o token retornado no `auth-context`/`localStorage`, redireciona para a home.
4. `app/onboarding/page.tsx` só é acessível autenticado; envia `PATCH /api/onboarding/` com interesses/localidade/canal, e permite "pular".
5. `app/page.tsx` (feed) lista entradas de `GET /api/feed/`, com campo de busca e filtro de categoria que refazem a requisição com os query params corretos; exibe indicador de publicidade conforme `exibir_publicidade` da resposta.
6. `app/noticia/cluster/[id]/page.tsx` e `.../item/[id]/page.tsx` mostram resumo, categoria e a lista de TODAS as fontes com link para a matéria original; tratam 404 (notícia não encontrada/não publicável) com uma mensagem clara, não uma tela quebrada.
7. `app/planos/page.tsx` lista `GET /api/assinatura/planos/` e permite assinar (`POST /api/assinatura/assinar/`) quando autenticado; redireciona para login quando não autenticado.
8. `app/minha-conta/page.tsx` mostra o status atual (`GET /api/assinatura/minha/`), o histórico de pagamentos (`GET /api/assinatura/historico-pagamentos/`), e um botão de cancelar (`POST /api/assinatura/cancelar/`) com confirmação antes de enviar.
9. `auth-context` mantém o estado de login entre navegações (recarrega do `localStorage` ao montar), e todas as chamadas autenticadas enviam `Authorization: Token <token>`.
10. Qualquer chamada de API que falhe (erro de rede, 4xx/5xx) mostra uma mensagem de erro visível ao usuário — nenhuma tela deve ficar em branco/travada silenciosamente.

## Não-objetivos
- Login social real (Google) — botão pode existir desabilitado/com aviso "em breve".
- Publicidade real (anúncios de terceiros) — só o indicador/estado, não integração com um ad network.
- Qualquer página para módulos do BRD ainda sem backend.
- Otimização de performance/SEO avançada, testes automatizados de frontend.
- Design visual final de marca.

## Restrições técnicas
- **Performance:** N/A para meta definida.
- **Segurança/privacidade:** nunca logar/expor o token em lugar visível além do armazenamento local necessário; sempre validar que uma resposta de erro da API é tratada antes de tentar acessar campos do payload (evitar erro de runtime ao acessar propriedade de `undefined`).
- **Dependências permitidas:** `next`, `react`, `react-dom`, `typescript`, `@types/react`, `@types/node`, `@types/react-dom` — nenhuma biblioteca de UI/CSS adicional (ver task-plan.md, "Suposições assumidas").
- **Estilo/convenções:** componentes funcionais React com hooks; TypeScript com tipos explícitos para as respostas de API (interfaces em `lib/api.ts`); nomes de campos em português, consistente com o backend.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Revisão manual cuidadosa de cada arquivo (sem execução disponível — ver task-plan.md, riscos)
- [ ] `implementation-history.md` completo, sinalizando claramente que build/execução não foram validados
- [ ] Documentação atualizada (documenter) — README com instruções de "como rodar o frontend"
