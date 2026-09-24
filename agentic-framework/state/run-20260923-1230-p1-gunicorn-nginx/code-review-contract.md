<!--
CONTRACT: code-review-contract
DONO: reviewer
QUANDO E CRIADO: reconciliação da run 20260923-1230-p1-gunicorn-nginx; a revisão anterior não foi delegada e não conta como evidência.
-->

# Code Review Contract — 20260923-1230-p1-gunicorn-nginx

## Metadados

- **run_id:** `20260923-1230-p1-gunicorn-nginx`
- **escopo revisado:** commit `93b919dc0233d22294bccd5d8341c64377adf9be` (`feat(P1-3/P1-4): gunicorn gthread config + nginx cache e limit_req`)
- **contrato de referência:** `implementation-contract.md` da própria run
- **artefatos lidos:** `implementation-contract.md`, `implementation-history.md`, `task-plan.md` e `agentic-framework/prompts/review-triggers.md`
- **gatilhos aplicados:** diff acima de ~300 linhas (460 inserções e 52 remoções); caminho de API pública em produção; exposição/autorização de mídia pessoal; credenciamento de jornalistas
- **método:** leitura do diff e dos arquivos completos; leitura do código-fonte do Gunicorn 23.0.0 e do PM2; reprodução com `gunicorn --print-config`; `nginx -t` real nos três confs em `nginx:alpine`/Nginx 1.31.6; normalização comparativa dos três ambientes; inspeção de Docker/Compose/Caddy e das rotas de mídia
- **isolamento:** mudanças não commitadas existentes na working tree (`robos_views.py`, frontend e `HISTORY.md`) não foram tratadas como parte do commit `93b919d`; a ausência da mudança assíncrona foi verificada no próprio objeto do commit

## Findings

### Finding 1 — blocker — `security/privacy`: o alias público de `/media/` expõe documentos de credenciamento sem autorização

- **Arquivos/linhas:** `infra/nginx/portal-dev.conf:88-98`, `infra/nginx/portal-homolog.conf:88-98`, `infra/nginx/portal-prod.conf:88-98`
- **Evidência concreta:** o location faz `alias .../backend/media/` para toda a árvore e ainda adiciona `Cache-Control "public, max-age=604800"`; o regex aninhado bloqueia somente `.py|.sh|.php|.pl|.cgi`, não PDFs, imagens, DOCX ou HTML. `backend/credenciamento/models.py:39-42` grava `documento` em `media/credenciamento/<user_id>/ARQUIVO` e declara que ele **nunca** deve ser exposto por URL pública. `backend/credenciamento/views.py:56-78` confirma que a autorização deve existir apenas no `DocumentoView` (dono ou admin). O alias do Nginx contorna completamente essa view.
- **O que acontece em produção:** qualquer pessoa que descubra o path — ele é retornado pelo serializer a um usuário autorizado e usa user id + nome original — consegue baixar o diploma/documento sem token, sessão ou papel admin; `public` ainda autoriza cache por browser/proxy. Isso é exposição de dado pessoal e de credenciamento, não apenas uma política de cache incorreta.
- **Correção sugerida:** não servir `media/credenciamento/` pelo alias genérico; bloquear esse subtree com um location `^~` mais específico e manter o download pelo `DocumentoView`, ou, preferencialmente, separar storage público de storage privado. Se fotos de perfil precisarem ser públicas, armazená-las em subárvore pública separada. A proteção por extensão não deve ser usada como controle de autorização.

### Finding 2 — blocker — `correctness/operability`: as zones usadas ativamente não existem no conjunto versionado, então `nginx -t`/reload falha

- **Arquivos/linhas:** `infra/nginx/portal-dev.conf:17-30,109,125,158`; o mesmo em `portal-homolog.conf` e `portal-prod.conf`; ausência da atualização exigida em `infra/DEPLOY.md`
- **Evidência concreta:** `map`, `limit_req_zone auth`, `limit_req_zone escrita_publica` e `proxy_cache_path` estão todos comentados, enquanto `limit_req zone=auth`, `proxy_cache feed_cache` e `limit_req zone=escrita_publica` estão ativos. Testei os três sites juntos em Nginx 1.31.6: sem zones, o teste termina com **`[emerg] "proxy_cache" zone "feed_cache" is unknown`**; mantendo apenas `proxy_cache_path`, o teste termina com **`[emerg] zero size shared memory zone "auth"`**. Adicionando o bloco global completo em `http {}`, o mesmo conjunto passa em `nginx -t`.
- **O que acontece em produção:** copiar os arquivos e recarregar não ativa a run: o reload é rejeitado pelo parser. Um Nginx já em execução normalmente continua com a configuração antiga, portanto a API não cai, mas cache e rate limit novos permanecem inativos; se a operação depender apenas do reload sem `nginx -t`, o operador verá a ativação falhar. O contrato exige que o runbook de zonas/invalidação esteja em `infra/DEPLOY.md`, e ele não foi alterado.
- **Correção sugerida:** versionar um include global (ou outro artefato instalável) com `map`, as duas `limit_req_zone` e `proxy_cache_path`; incluir esse arquivo uma única vez no `http {}` antes dos sites, documentar a ordem de instalação e validar os três ambientes com `nginx -t` antes do reload. As quatro peças devem ser ativadas juntas; sem o `map`, `$limit_post` também fica desconhecida. Para invalidar cache existente, documentar remoção/purge dos arquivos — reload sozinho não os apaga.

### Finding 3 — major — `correctness/availability`: o timeout de 45 s depende de uma mudança de `catalogo_noticias` que não existe no commit revisado

- **Arquivos/linhas:** `backend/gunicorn.conf.py:37-43`; `infra/nginx/portal-prod.conf:165-171` (equivalentes dev/homolog)
- **Evidência concreta:** o comentário justifica 45 s afirmando que `POST /api/admin/robos/executar/` responde 202 em background, mas em `93b919d:backend/catalogo_noticias/robos_views.py:114-140` o endpoint chama `executar_ingestao()` sincronamente e só responde 201 depois de terminá-lo. A própria `implementation-history.md:118-122` reconhece que a mudança para background está em stash não commitado e ordena que ela seja commitada antes da ativação.
- **O que acontece em produção:** uma ingestão que não responda dentro de 45 s faz o Nginx devolver 504. O Django não garante cancelamento quando o cliente desconecta, então a tarefa pode continuar consumindo uma thread; tentativas/reenvios podem ocupar as 8 threads (`2 workers x 4`) e multiplicar o trabalho. Em `gthread`, o timeout do Gunicorn é principalmente de silêncio do processo e não garante que uma única requisição longa seja cancelada em 45 s.
- **Correção sugerida:** não ativar este commit até que a mudança assíncrona seja um ancestral comprovado do ref implantado; alternativamente, manter timeout de 180 s para o endpoint/enquanto a dependência não existir. Isso pode ser resolvido na ordem de merges/deploy, sem violar o escopo deste commit.

### Finding 4 — major — `security/rate-limit`: POST público em `/api/feed/interacoes/` não passa pelo `limit_req`

- **Arquivos/linhas:** `infra/nginx/portal-prod.conf:124-152,157-176`; equivalentes em dev/homolog; `backend/feed/urls.py:19` e `backend/feed/views.py:387-394` como evidência da rota
- **Evidência concreta:** o regex `location ~ ^/api/(feed/|radar/tendencias/)` também casa `/api/feed/interacoes/`. No Nginx, uma regex vencedora substitui o location de prefixo `/api/`; `proxy_cache_methods GET` impede cache do POST, mas não faz o request voltar ao location `/api/`. Portanto o `limit_req zone=escrita_publica` da linha 158 não é herdado pelo location regex. `InteracaoView` é `AllowAny`, aceita POST e não declara throttle DRF.
- **O que acontece em produção:** um cliente pode enviar interações ilimitadas; cada request chega ao Gunicorn e consulta/cria dados no banco, anulando a defesa de borda justamente na rota que gera escritas.
- **Correção sugerida:** replicar `limit_req zone=escrita_publica ...` e `limit_req_status 429` no location de cache (a key fica vazia em GET), ou criar um location exato para `/api/feed/interacoes/` com o limite e sem cache.

### Finding 5 — minor — `robustness`: no PM2 o conf é encontrado hoje pelo cwd, não pelo `--chdir`; os comentários afirmam o contrário

- **Arquivos/linhas:** `.github/workflows/deploy.yml:182-191`; `backend/gunicorn.conf.py:10-14`; `implementation-history.md:73-74,116-117`
- **Evidência concreta:** a linha 182 executa `cd "$APP_DIR/backend"` antes do PM2, e o PM2 captura `process.cwd()`/`pm_cwd` ao iniciar e o persiste no dump; nesse caminho, o processo Gunicorn começa no backend e encontra `/backend/gunicorn.conf.py`. Reproduzi a resolução real com Gunicorn 23.0.0: executando de `backend`, `--print-config` retorna `workers=2`, `threads=4`, `worker_class=gthread`, `timeout=45`; executando de `/tmp/opencode` com apenas `--chdir /.../backend`, retorna `workers=1`, `threads=1`, `worker_class=sync`, `timeout=30`. No Gunicorn 23, a busca automática do conf ocorre antes de o `--chdir` ser aplicado ao config final.
- **O que acontece em produção:** no workflow atual, não há fallback para defaults — o conf é encontrado. Porém qualquer invocação futura de PM2 feita fora de `backend`, ou uma mudança no cwd persistido, faria o Gunicorn silenciosamente usar defaults sync/1/30; `--chdir` sozinho não protege esse caso.
- **Correção sugerida:** passar explicitamente `--config "$APP_DIR/backend/gunicorn.conf.py"` no PM2 (e, opcionalmente, `--config gunicorn.conf.py` no Docker), corrigindo os comentários para não atribuir essa garantia ao `--chdir`.

### Finding 6 — minor — `performance`: o location de autenticação não aproveita o keepalive do upstream

- **Arquivos/linhas:** `infra/nginx/portal-dev.conf:101-116`; equivalentes em homolog/prod
- **Evidência concreta:** `/healthz` e, especialmente, `/api/auth/` são locations irmãos de `/api/`, não descendentes; por isso não herdam `proxy_http_version 1.1` e `Connection ""` declarados no prefixo. Nginx 1.29.7+ usa HTTP/1.1 por default, mas versões anteriores usam HTTP/1.0; como a versão da VPS não foi comprovada, o comportamento de keepalive ficou dependente do default do build. O location também usa os timeouts default de 60 s.
- **O que acontece em produção:** continua funcional em qualquer das versões, mas o location deixa de cumprir a configuração explícita de keepalive do contrato e, em Nginx anterior a 1.29.7, paga uma conexão por request; não é causa de queda da API. `/healthz`, de baixo volume, é aceitável sem keepalive.
- **Correção sugerida:** extrair os knobs comuns de proxy para um include usado por `/api/`, `/api/auth/` e `/healthz`, ou duplicar `proxy_http_version 1.1` + `Connection ""` e timeouts explícitos no location de auth.

### Finding 7 — minor — `correctness/rate-limit`: cadastro recebe 10 req/min no Nginx, mas o contrato do DRF lhe atribui 20/min

- **Arquivos/linhas:** `infra/nginx/portal-dev.conf:29,108-110`; equivalentes em homolog/prod; `backend/identidade/urls.py:8` e `backend/identidade/views.py:43-50` como evidência
- **Evidência concreta:** `POST /api/auth/cadastro/` fica sob o location mais específico `/api/auth/`, que usa `zone=auth` a `10r/m`; `CadastroView`, entretanto, usa `EscritaPublicaAnonThrottle`, cujo default em `backend/config/settings.py:370` é `20/min`. O comment/history do commit trata toda a subtree como `auth_sensivel`/`10/min`, mas cadastro é o único POST dessa subtree classificado como `escrita_publica`.
- **O que acontece em produção:** a borda começa a devolver 429 antes do limite da aplicação; isso pode bloquear cadastros legítimos adicionais em IP compartilhado/NAT, enquanto o contrato promete 20/min para esse fluxo. É uma rejeição antecipada, não queda da API.
- **Correção sugerida:** dar a `/api/auth/cadastro/` um location exato com `zone=escrita_publica` e manter `zone=auth` nos demais endpoints sensíveis; se 10/min for uma decisão consciente de produto, documentar o override e seu impacto em vez de alegar alinhamento exato ao DRF.

## Verificações de escopo e pontos pedidos sem finding adicional

### Gunicorn nos dois caminhos

- **Docker — conf encontrado:** `backend/Dockerfile:9,21,36-41` usa `WORKDIR /app`, o build context de `docker-compose.yml:46-48` é `./backend`, `COPY . .` traz `gunicorn.conf.py` para `/app/gunicorn.conf.py` (não está excluído por `backend/.dockerignore`) e o entrypoint termina em `exec "$@"`, sem trocar de diretório. O default documentado do Gunicorn 23 (`./gunicorn.conf.py`) é portanto atendido; o `--bind` explícito sobrescreve apenas o bind.
- **PM2 — conf encontrado no caminho efetivo atual:** `deploy.yml:182` já deixa o cwd em `backend` antes do `pm2 start`, e o PM2 inicia o filho com esse `pm_cwd`; a resolução real é gthread/2x4/45. A fragilidade do `--chdir` isolado está no Finding 5. Se o arquivo não fosse encontrado, o Gunicorn 23 não falharia: ele carregaria defaults `sync`, 1 worker/thread e timeout 30.

### Nginx — semântica dos blocos e cache

- **Sem zonas:** não é “apenas não cacheia” nem “somente limit_req ignorado”; no conjunto testado, ambos os usos criam shared-memory zones sem tamanho/definição e o parser aborta com `emerg` (Finding 2).
- **`map`:** a diretiva é válida apenas em contexto `http`; ela não é válida dentro de `server {}`. No arquivo atual ela está comentada e fora do `server`. O wrapper com `map` + zones no `http {}` passou em `nginx -t`, confirmando que o conjunto comentado é sintaticamente válido quando instalado no contexto certo.
- **`alias`:** as duas barras finais em `/static/` e `/media/` estão corretas para a rewriting pretendida. O problema do `/media/` é de autorização/privacidade (Finding 1), não de path syntax.
- **Chave/bypass:** `$scheme$request_method$host$request_uri` não inclui credenciais; `proxy_cache_bypass` e `proxy_no_cache` reagem a qualquer Authorization, `sessionid` ou `csrf_token` não vazio. Isso é coerente para as rotas públicas e para endpoints de feed personalizados; `Set-Cookie` também impede cache pelo comportamento padrão do Nginx. Não identifiquei vazamento entre usuário autenticado/anônimo nas rotas cobertas pelo regex.
- **`/healthz` e `/api/auth/`:** funcionalmente funcionam sem HTTP/1.1/keepalive; apenas o desvio de performance/contrato de auth está no Finding 6.

### Drift dev/homolog/prod e stack

- Após normalizar ambiente, os três Nginx diferem apenas em nome de upstream, `server_name`, portas e `/home/apps/portal-{dev,homolog,prod}`: dev 3101/5101, homolog 3102/5102 e prod 3103/5103, consistentes com os callers. Não há `DJANGO_DEBUG`, cookie ou taxa de dev vazada no conf de PROD; as taxas são idênticas entre os ambientes (20r/m + burst 20 para escrita e 10r/m + burst 10 para auth), com apenas o desalinhamento de cadastro do Finding 7. O diff também não alterou a criação de `.env`.
- `docker-compose.yml` e `Caddyfile` não foram tocados. O `Dockerfile` continua coerente: `web` usa o CMD Gunicorn; `celery-worker` e `celery-beat` sobrescrevem entrypoint/command e não entram no caminho do conf. A exposição ampla de mídia já presente no Caddy alternativo é pré-existente e fora deste commit, mas a nova stack Nginx não deve copiá-la sem separar mídia privada.
- O commit toca somente os seis arquivos esperados: `deploy.yml`, `Dockerfile`, `gunicorn.conf.py` e os três Nginx. `settings.py`, `feed/`, `gating/`, `catalogo_noticias/`, `docker-compose.yml` e `Caddyfile` não fazem parte do diff. A única lacuna de escopo é `infra/DEPLOY.md`, que o próprio contrato exigia atualizar por causa da nova operação e ficou como follow-up (Finding 2).

## Resumo quantitativo

| Severidade | Quantidade |
|---|---:|
| blocker | 2 |
| major | 2 |
| minor | 3 |
| nit | 0 |

## Veredito

**changes_requested**

O caminho Gunicorn está correto no Docker e correto no PM2 atual por causa do `cd` prévio, mas essa garantia está implícita e pode cair silenciosamente para defaults se o cwd mudar. O Nginx, porém, não está aprovável: os sites versionados falham em `nginx -t` sem zones globais e, se forem corrigidos isoladamente, o alias público de mídia passa a expor documentos privados de credenciamento; além disso, há um POST público sem rate limit e uma justificativa de timeout baseada em código que não pertence ao commit. Corrigir os Findings 1–4 e revisar os testes de ativação antes de qualquer reload; Findings 5–7 são endurecimentos recomendados na mesma correção.
