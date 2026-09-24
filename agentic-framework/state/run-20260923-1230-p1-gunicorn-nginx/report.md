# Report — 20260923-1230-p1-gunicorn-nginx

## Objetivo

Proteger a API contra requisições lentas sem eliminar a capacidade de I/O
concorrente e reduzir o custo de serving por pageview com compressão, cache de
borda local, keepalive e entrega direta de arquivos estáticos. A entrega também
precisava preservar a privacidade dos documentos de credenciamento e produzir
uma ativação Nginx que não quebre o reload.

## Entregas

### Gunicorn e caminhos de deploy

- `backend/gunicorn.conf.py` centraliza a configuração: `worker_class =
  gthread`, **2 workers × 4 threads** e **timeout 60 s** por padrão, com
  overrides por `GUNICORN_WORKERS`, `GUNICORN_THREADS`, `GUNICORN_TIMEOUT` e
  `GUNICORN_BIND`.
- `backend/Dockerfile` usa o conf único e mantém apenas o bind do container;
  `.github/workflows/deploy.yml` passa o caminho absoluto do mesmo conf ao
  PM2, fixa o timeout seguro de 60 s e não repete flags divergentes.
- `proxy_read_timeout` dos três sites Nginx foi alinhado em 60 s.

### Nginx

- Gzip para JSON, CSS, JavaScript, HTML, SVG e XML nos três ambientes.
- Upstream com `keepalive 32`, HTTP/1.1 e `Connection ""`, inclusive nas
  locations de autenticação e health.
- Cache curto (45 s) para allowlist de GET/HEADs públicos, sem chave de
  cookie/Authorization, com bypass/no-cache para requisições autenticadas,
  cache lock e stale em erros de upstream.
- `limit_req` para escrita pública (20/min) e autenticação sensível (10/min),
  com cadastro e interações mantidos no limite correto de escrita.
- `/static/` servido no edge e mídia separada: somente `/media/public/` recebe
  alias; `/media/credenciamento/` fica fora do edge e continua atrás do
  `DocumentoView` autenticado.
- Includes opcionais versionados: `http-cache.conf` no contexto global
  `http {}` e `portal-location-{cache,auth,write}.conf` nas locations. Os sites
  permanecem sintaticamente válidos se os arquivos opcionais não existirem,
  com cache/rate explicitamente inativos.

## Reconciliação da revisão

A run foi inicialmente encerrada de forma prematura: o reviewer delegado
falhou por rate limit e o orchestrator produziu o veredito como fallback. Esse
caminho não constitui revisão válida para o framework. A run foi reaberta e
submetida a um reviewer delegado real, que encontrou:

- **2 blockers:** alias público de `/media/` expunha documentos de
  credenciamento; zones de cache/rate comentadas faziam `nginx -t`/reload
  falhar.
- **2 majors:** timeout de 45 s dependia do endpoint 202 ainda não commitado;
  regex de cache capturava o POST público de interações.
- **3 minors:** descoberta do conf PM2 dependia do cwd; auth/health não tinham
  keepalive explícito; cadastro recebia 10/min em vez de 20/min.

A iteração 1 de remediação tratou **7/7 findings**. A re-revisão delegada
confirmou independentemente a resolução dos dois blockers e de todos os demais
achados, com veredito final **approve**, zero finding residual e contagem final
`blocker 0 / major 0 / minor 0 / nit 0 / resolved 7`.

## Testes e validações

- `gunicorn --check-config --config gunicorn.conf.py
  config.wsgi:application`: exit 0; `--print-config` reportou
  `gthread`, 2 workers, 4 threads e timeout 60.
- `nginx -t` real em `nginx:alpine` (Nginx 1.31.6): passou nos dois conjuntos —
  três sites standalone sem zones/snippets e ativação completa com
  `http-cache.conf`, três snippets e três sites.
- Teste comportamental do Nginx: documentos/fotos de `media/credenciamento`
  retornaram 404, inclusive tentativas de path traversal; apenas
  `/media/public/` retornou 200. Interações ficaram fora do cache e receberam
  `429` no limite de escrita.
- `.github/workflows/deploy.yml`: parse com `yaml.safe_load`, chaves `guard`,
  `deploy` e `validate` presentes.
- `python3 -m py_compile backend/gunicorn.conf.py`: exit 0.
- `git diff --check`: sem erros de whitespace nos artefatos da remediação.

## Documentação

- `infra/DEPLOY.md` agora fornece a ordem operacional completa: instalar
  `http-cache.conf` dentro do `http {}`, instalar snippets/site, executar
  `nginx -t`, recarregar somente se válido e reiniciar a API PM2.
- `CI-CD.md` aponta a mesma sequência e a proteção fail-closed de
  `media/credenciamento`.
- `README.md` ganhou uma seção de deploy/infra com Gunicorn `gthread`,
  2 workers × 4 threads, timeout 60 e a política `/media/public/` versus
  `/media/credenciamento/`.
- `documentation-update.md` registra as verificações e todas as mudanças com
  arquivo:linha e antes → depois.

## Follow-ups

1. **Passo manual na VPS:** instalar `http-cache.conf` e incluí-lo uma vez no
   bloco `http {}` global; instalar os snippets/sites; executar `nginx -t`;
   recarregar o Nginx; reiniciar e salvar os processos API no PM2.
2. **Topologia Caddy:** `Caddyfile:41-44` ainda serve `/media/*` inteiro. Ela
   precisa da mesma separação de storage antes de qualquer uso com
   credenciamento: somente `/media/public/*` no edge e documentos privados
   somente pela view autenticada.
3. **Pré-condição do timeout 45:** a redução depende do commit do endpoint 202
   em `backend/catalogo_noticias/robos_views.py`, que estava não commitado no
   registro desta run. Confirmar ancestralidade do commit no ref implantado.
4. **Redução para 45 s:** fazer somente quando o endpoint 202+background
   estiver em produção, alterando atomicamente `GUNICORN_TIMEOUT=45` e
   `proxy_read_timeout 45s` nos três sites, seguido de nova validação
   `nginx -t`, reload e restart PM2.

## Veredito

**Entregue e aprovada.** A implementação e a documentação da iteração 1 estão
reconciliadas; a ativação operacional e a correção da topologia Caddy são
follow-ups explícitos, não omissões do escopo entregue.
