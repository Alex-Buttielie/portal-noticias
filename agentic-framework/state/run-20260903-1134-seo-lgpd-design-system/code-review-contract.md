<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: sempre que review-triggers.md indicar revisao obrigatoria, ou sob demanda (skill agentic-review).
PARA ONDE VAI A INSTANCIA: agentic-framework/state/run-<run_id>/code-review-contract.md
-->

# Code Review Contract - 20260903-1134-seo-lgpd-design-system

## Metadados
- run_id: 20260903-1134-seo-lgpd-design-system
- Escopo revisado: diff completo das 3 iteracoes registradas em implementation-history.md (executor + tester + remediator), com foco nos gatilhos abaixo.
- Contrato de referencia: implementation-contract.md (20260903-1134-seo-lgpd-design-system), versao 1
- Gatilhos aplicados (de review-triggers.md): mudanca que altera dados pessoais de usuarios (novo campo/endpoint preferencias_cookies em identidade); migracao de schema de banco de dados (0002_user_preferencias_cookies_and_more.py); mudanca em API publica (novo endpoint GET/PUT /api/preferencias-cookies/).

## Findings

### Finding 1
- Arquivo: backend/config/settings.py (bloco CACHES) e backend/config/throttling.py
- Linha: CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True
- Categoria: security
- Severidade: major
- Resumo: o throttle de escrita publica usa o mesmo cache Redis default que tem IGNORE_EXCEPTIONS=True sem log/alerta configurado; se o Redis cair em producao, o rate limiting desliga silenciosamente.
- Cenario de falha: Redis fica indisponivel em producao. AnonRateThrottle.allow_request chama cache.get(chave); com IGNORE_EXCEPTIONS=True e sem log de excecao, a falha e engolida e tratada como "sem historico" -- toda requisicao passa a ser aceita como se fosse a primeira. POST /api/auth/cadastro/, POST /api/landing/lista-espera/ e POST /api/comunidade/publicacoes/ aceitam volume ilimitado sem nenhum 500, log ou metrica indicando degradacao. O tester ja identificou esse mecanismo (por isso testou com DJANGO_CACHE_BACKEND=locmem) mas isso nao foi tratado como bloqueio nem documentado como risco aceito com plano de monitoramento nesta run.
- Sugestao: adicionar log de warning/metrica quando o cache do throttle lancar excecao (ex.: DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS + handler de logging, ou cache dedicado ao throttle), ou registrar explicitamente esse risco como trade-off aceito em report.md.

### Finding 2
- Arquivo: frontend/lib/cookie-consent.ts (funcao importarPreferenciasDoBackendSeNecessario); frontend/lib/auth-context.tsx; frontend/app/privacidade/preferencias-cookies/PreferenciasCookiesConteudo.tsx
- Linha: N/A (ausencia de chamada -- confirmado por busca em todo frontend, unico resultado e a propria definicao da funcao)
- Categoria: correctness
- Severidade: major
- Resumo: a funcao que deveria trazer de volta a preferencia de cookies ja registrada no backend para um usuario autenticado em um dispositivo novo nunca e chamada em nenhum lugar do app.
- Cenario de falha: usuario autenticado escolhe "Aceitar todos" no Dispositivo A -- persistido em localStorage do A e replicado via PUT /api/preferencias-cookies/ no backend. O mesmo usuario faz login no Dispositivo B com localStorage vazio; consentimentoRespondido() em B retorna false, entao o banner aparece de novo em B mesmo com preferencia ja registrada na conta. Se o usuario responder diferente em B, o valor do backend vindo do Dispositivo A e sobrescrito silenciosamente, sem nunca ter sido lido. Isso contraria o comentario do proprio arquivo, a copia mostrada ao usuario em PreferenciasCookiesConteudo.tsx ("se voce estiver conectado a sua conta, tambem e salva no seu perfil") e o criterio de negocio do task-plan.md numero 3 ("a escolha e lembrada em visitas futuras"), que falha no caso de troca de dispositivo para usuario autenticado. Nao e falha de privacidade (o padrao seguro de negar continua valendo), mas e um defeito real na feature de dados pessoais que motivou esta revisao ser obrigatoria.
- Sugestao: chamar importarPreferenciasDoBackendSeNecessario(token) em auth-context.tsx logo apos persistirSessao no fazerLogin.

### Finding 3
- Arquivo: backend/identidade/tests/ (ausencia de teste)
- Linha: N/A
- Categoria: test-coverage
- Severidade: major
- Resumo: nao existe nenhum teste automatizado para PreferenciasCookiesView (GET/PUT /api/preferencias-cookies/) nem para services.atualizar_preferencias_cookies -- confirmado por busca em backend/identidade/tests/ (0 ocorrencias) e pela suite completa de 221 testes nao incluir nenhum teste com esse nome.
- Cenario de falha: uma futura alteracao em PreferenciasCookiesView (ex.: aceitar um user_id no corpo por engano, ou remover permission_classes = [IsAuthenticated] durante refatoracao) nao teria nenhum teste para quebrar e sinalizar a regressao. Como este e exatamente o endpoint novo que grava dado pessoal de usuario autenticado -- o gatilho que tornou esta revisao obrigatoria -- a ausencia de cobertura automatizada e uma lacuna concreta.
- Sugestao: adicionar testes cobrindo (1) GET/PUT sem autenticacao retorna 401; (2) PUT de um usuario so afeta o proprio request.user; (3) PUT com payload invalido nao grava campo fora do allow-list CATEGORIAS_OPCIONAIS.

## Resumo quantitativo
| Severidade | Quantidade |
|---|---|
| blocker | 0 |
| major | 3 |
| minor | 0 |
| nit | 0 |

## Veredito
**changes_requested**

O gate de consentimento em si esta correto (nega por padrao sem resposta registrada, permiteCategoria e o unico ponto de checagem, nenhum script de analytics real existe ainda no projeto para violar o gate), a migracao e puramente aditiva, a mutacao de preferencias passa por services.py e e corretamente restrita a request.user (sem parametro de usuario na URL, sem risco de escrita cross-user), e o JSON-LD nao expoe nenhum dado alem do que ja e publico em endpoints pre-existentes. Nao ha blocker. Porem ha 3 findings major que devem ser resolvidos antes de fechar esta run: (1) o rate limiting pode desligar silenciosamente em producao se o Redis cair, sem nenhum log/alerta -- risco real para o proprio escopo C desta run; (2) a sincronizacao de preferencias de cookies entre dispositivos para usuario autenticado esta incompleta (funcao de importacao nunca e chamada), contrariando a documentacao do proprio codigo, a copia mostrada ao usuario e o criterio de negocio "a escolha e lembrada em visitas futuras"; (3) o endpoint novo que grava dado pessoal -- o motivo desta revisao ser obrigatoria -- nao tem nenhum teste automatizado. Nenhum dos tres exige reverter trabalho feito; sao correcoes pontuais e razoavelmente pequenas (recomenda-se voltar para executor/remediator antes de seguir para documenter).

---

## Reverificacao pos-remediacao (Iteracao 4 do remediator) - 2026-09-03

Reverificacao feita pelo reviewer com evidencia real e independente (reproducao
propria, nao apenas leitura do relato do remediator em implementation-history.md).

### Finding 1 (throttle Redis silencioso) - CONFIRMADO RESOLVIDO

- Leitura direta de `backend/config/settings.py`: `DJANGO_REDIS_LOG_IGNORED_EXCEPTIONS = True`
  esta presente logo apos `CACHES["default"]["OPTIONS"]["IGNORE_EXCEPTIONS"] = True`, no ramo
  Redis (nao no ramo `locmem`).
- Reproduzi eu mesmo (nao confiei so no relato) o comando do remediator, apontando
  `DJANGO_CACHE_REDIS_URL=redis://localhost:1/0` (porta sem servico nenhum escutando):
  `cache._ignore_exceptions == True`, `cache._log_ignored_exceptions == True`, e o
  log efetivamente disparou: linha `ERROR django_redis.cache [cache] Exception ignored`
  com traceback completo de `ConnectionRefusedError`/`ConnectionInterrupted`, e a chamada
  `cache.get(...)` retornou `None` (degradacao graciosa mantida, sem 500). Confirma que a
  falha de Redis agora deixa rastro no log em vez de desaparecer em silencio total.
- Veredito do finding: resolvido de fato, com evidencia de execucao real (nao so leitura
  de codigo), tanto pelo remediator quanto por mim de forma independente.

### Finding 2 (sync de preferencias de cookies nunca chamada) - CONFIRMADO RESOLVIDO

- Leitura de `frontend/lib/auth-context.tsx`: `importarPreferenciasDoBackendSeNecessario`
  agora e chamada em dois pontos: (1) dentro de `fazerLogin`, apos `persistirSessao`,
  usando `resposta.token` (o token que acabou de vir da resposta de login, nao o `token`
  do estado do React, que so seria atualizado no proximo render) - sem risco de usar um
  valor stale/undefined; (2) no `useEffect` de restauracao de sessao, usando `tokenSalvo`
  (a variavel local recem-lida do `localStorage`, nao o estado `token`, pela mesma razao).
  Os dois pontos de chamada fazem sentido e evitam o problema classico de usar estado
  React desatualizado dentro do mesmo ciclo de execucao.
- Ambas as chamadas sao `void <chamada>` (fire-and-forget) e a propria funcao chamada
  (`importarPreferenciasDoBackendSeNecessario`, ja lida na revisao original) e no-op se
  `consentimentoRespondido()` ja for `true` localmente, e engole qualquer erro de rede via
  `try/catch` - confirmado por leitura de codigo que isso nao pode travar nem quebrar o
  fluxo de login/carregamento da sessao, e que nao sobrescreve uma escolha local ja feita
  neste navegador.
- Rodei eu mesmo `npx tsc --noEmit` em `frontend/` (nao so confiei no relato do
  remediator): saida limpa, exit code 0, sem nenhum erro de tipo.
- Veredito do finding: resolvido de fato. Os pontos de chamada sao coerentes e seguros.

### Finding 3 (zero testes para o endpoint de preferencias de cookies) - CONFIRMADO RESOLVIDO

- Rodei eu mesmo (nao apenas confiei no relato):
  `cd backend && DJANGO_DB_ENGINE=sqlite3 DJANGO_CACHE_BACKEND=locmem .venv/Scripts/python.exe -m pytest identidade/tests/test_preferencias_cookies.py -v`
  -> 10 passed (o remediator relatou "9 testes" na narrativa do implementation-history.md,
  mas o arquivo de fato tem 10 metodos de teste e todos os 10 coletam e passam - discrepancia
  de contagem no relato, nao um problema funcional; ver nota abaixo).
  `cd backend && ... -m pytest identidade -q` -> 54 passed (bate com o numero relatado).
  `cd backend && ... -m pytest -q` (suite completa) -> 256 passed (o remediator relatou
  "255 passed"; diferenca de 1 teste, plausivelmente por edicao concorrente de outra sessao
  no mesmo repositorio, padrao ja documentado varias vezes nesta run - nao ha nenhuma falha,
  so uma contagem total levemente diferente do momento em que o remediator rodou).
- Li o arquivo `backend/identidade/tests/test_preferencias_cookies.py` linha a linha e
  confirmo que os testes cobrem exatamente o que o finding pedia, nao so "existem e passam":
  - `TestPreferenciasCookiesAutenticacao`: GET/PUT sem autenticacao retornam 401/403.
  - `TestPreferenciasCookiesGet`: GET reflete o estado real persistido via
    `services.atualizar_preferencias_cookies` (nao um mock).
  - `TestPreferenciasCookiesPut::test_put_autenticado_persiste_via_service_layer`: confirma
    persistencia real no banco com `user.refresh_from_db()`, nao so a resposta HTTP.
  - `TestPreferenciasCookiesPut::test_put_so_afeta_o_proprio_usuario_autenticado_request_user`:
    isolamento cross-user testado de forma adversarial de verdade - injeta `id`/`user_id` de
    um segundo usuario (`usuario_b`) no payload de um PUT autenticado como `usuario_a`, e
    confirma que `usuario_b` continua com o valor anterior (`refresh_from_db` nos dois lados).
    Isso prova que a view ignora qualquer identificador vindo do corpo da requisicao e sempre
    opera sobre `request.user`, exatamente o que o finding original pedia para cobrir.
  - `TestPreferenciasCookiesPut::test_put_so_grava_chaves_do_allow_list_categorias_opcionais`:
    injeta `"essenciais"` e um `"campo_arbitrario"` no payload e confirma que
    `user.preferencias_cookies` so contem as chaves de `services.CATEGORIAS_OPCIONAIS` -
    cobre o allow-list do service layer.
  - `TestServiceAtualizarPreferenciasCookies`: cobertura direta do service (chave ausente
    vira `False`, timestamp sempre atualizado).
- Veredito do finding: resolvido de fato, com cobertura que testa autenticacao, persistencia
  via service layer e isolamento cross-user de forma concreta e adversarial (nao superficial).

### Veredito final atualizado

**approve_with_comments**

Os 3 findings `major` do veredito anterior (`changes_requested`) foram corrigidos e
reverificados de forma independente, com execucao real (nao so leitura do relato do
remediator): reproduzi o log de excecao do Redis com um Redis genuinamente inacessivel,
li os dois pontos de chamada novos em `auth-context.tsx` e confirmei que sao seguros
(sem race condition de estado, sem risco de travar o login), e rodei eu mesmo a suite de
testes nova e completa do backend (256 passed, sem falhas). Nao ha nenhum `blocker` nem
`major` pendente. Os unicos itens remanescentes sao dois nits de acuracia de relato em
`implementation-history.md` (a Iteracao 4 diz "9 testes" onde ha 10, e "255 passed" onde
a suite completa hoje da 256 passed, provavelmente por edicao concorrente de outra sessao
entre a execucao do remediator e a minha) - nao bloqueiam, nao indicam nenhum problema de
codigo, e podem ser corrigidos pelo `documenter`/`historian` ao registrar os numeros finais
com um novo `pytest -q` no momento do fechamento da run, para nao propagar um numero
desatualizado no `report.md`.

**Esta run pode seguir para o `documenter`.**
