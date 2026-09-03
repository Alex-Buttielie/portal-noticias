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
