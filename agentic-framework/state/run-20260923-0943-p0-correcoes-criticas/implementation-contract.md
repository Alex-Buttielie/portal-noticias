# Implementation Contract — 20260923-0943-p0-correcoes-criticas

## Metadados
- **run_id:** 20260923-0943-p0-correcoes-criticas
- **Deriva de:** task-plan.md (20260923-0943-p0-correcoes-criticas)
- **Versão do contrato:** 1

## O que deve ser construído

### Parte A — P0-1: corrigir preço estimado do LLM
Trocar o default de `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS` de
`0.15` para `0.0003` em `backend/config/settings.py` (manter leitura via
env e fallback para `ConfiguracaoRobo`, como hoje em
`backend/catalogo_noticias/providers/summarization.py:136-149`), e
reescrever o comentário em `settings.py:855-866` com a derivação do valor
(gpt-4o-mini: entrada $0.15/1M = $0.00015/1k; saída $0.60/1M = $0.0006/1k;
lote típico de 10 itens ≈ 5000 in + 2200 out ≈ $0.00029/1k → `0.0003`
conservador; revisar quando o provedor de produção for escolhido).
Atualizar todos os lugares que repetem o valor antigo: `backend/.env.example`,
`README.md` (seção "Teto de gasto diário"), e qualquer teste que fixe `0.15`.

### Parte B — P0-4: diagnosticar ISR vs SSR
Rodar o build de produção do frontend (`npm ci` se necessário + `npm run
build` em `frontend/`) e capturar os marcadores de rota do Next para `/`,
`/noticia/item/[id]`, `/noticia/cluster/[id]`, `/categoria/[slug]`,
`/ao-vivo`, `/buscar`. Se as rotas de conteúdo aparecerem como `ƒ`
(Dynamic) por causa do `headers()` em `frontend/app/layout.tsx:48-53`,
mover a detecção de UA (`perfilPorUserAgent`) para um client component
isolado (o `DeviceProvider` já corrige pós-hidratação) de modo que o root
layout volte a ser estático e as rotas voltem a `●` (ISR, `revalidate`
respectivo). Se já forem ISR, nenhuma mudança de código — só registrar a
evidência.

## Áreas/arquivos esperados
- `backend/config/settings.py` (default + comentário)
- `backend/.env.example` (valor documentado)
- `backend/catalogo_noticias/providers/summarization.py` (leitura apenas — só mexer se o default estiver duplicado lá)
- `backend/catalogo_noticias/tests/` + `backend/metricas/tests/` (ajustar/fixar asserções de custo)
- `README.md` (seção "Teto de gasto diário com o provedor de LLM")
- `frontend/app/layout.tsx` + `frontend/components/dispositivos/*` (apenas se o diagnóstico confirmar SSR indevido)
- Qualquer mudança fora desta lista deve ser justificada em `implementation-history.md`.

## Interfaces afetadas
- Variável `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS`: mesmo nome, mesma unidade — só muda o default. Sem quebra para quem já definiu valor próprio.
- `GET /api/metricas/painel/` (`custo_llm_hoje_usd`, `teto_llm_excedido_hoje`): passam a refletir ordem de grandeza real; o teto passa a ser atingido muito mais tarde (comportamento intencional desta correção).
- Nenhuma mudança de schema de banco.

## Critérios de aceite (técnicos, testáveis)
1. Dado settings sem env definida, quando ler `CATALOGO_NOTICIAS_LLM_PRECO_USD_POR_1K_TOKENS`, então vale `0.0003` (tol. float).
2. Dado um `ResultadoResumo` com `tokens_utilizados=10000`, quando calculado `custo_estimado_usd`, então vale `0.003` (= 10 × 0.0003), não `1.5`.
3. Dado o teto default de $5/dia, quando estimado o volume suportado, então é da ordem de ~16M tokens/dia (documentado), não ~33k.
4. `pytest` nos módulos afetados (`catalogo_noticias`, `metricas`, e suíte completa se viável) passa, incluindo cobertura mínima do CI quando aplicável.
5. Evidência de `next build` anexada ao `implementation-history.md` (trecho dos marcadores de rota); se houve correção, build posterior mostra `●` nas rotas de conteúdo e o site continua sem flash de layout (detecção de UA preservada no cliente).

## Não-objetivos
- Trocar de provedor de LLM, separar preço de entrada/saída, ou mudar a fórmula de estimativa.
- P0-2/P0-3 (VPS), itens P1/P2, e qualquer refatoração não exigida pelos dois itens acima.
- `NEXT_PUBLIC_*` de build, SEO, ou dependências do frontend.

## Restrições técnicas
- **Performance:** nenhuma regressão mensurável (mudança de constante + diagnóstico; eventual refatoração de layout não pode adicionar fetch bloqueante).
- **Segurança/privacidade:** nenhum dado de usuário tocado; sem LGPD aplicável.
- **Dependências permitidas:** nenhuma nova (usar toolchain já instalada; `npm ci` só se `node_modules` ausente).
- **Estilo/convenções:** comentários no padrão do projeto (português, referência a arquivo/linha e motivo); docs em `README.md` seguem o tom existente.
- **Revisão:** `review-triggers.md` consultado — nenhum gatilho obrigatório se aplica (sem auth/billing/dados pessoais/migração/API pública/moderação/dependência nova; diff esperado < 300 linhas). Revisão formal só se o diff final estourar esse volume ou tocar área sensível.

## Definição de pronto (Definition of Done)
- [ ] Critérios de aceite implementados
- [ ] Testes escritos e passando (tester)
- [ ] Revisão de código aprovada, se exigida por `review-triggers.md` (reviewer)
- [ ] Documentação atualizada (documenter)
- [ ] `implementation-history.md` completo e coerente
