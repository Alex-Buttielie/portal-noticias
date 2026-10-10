#!/bin/sh
# Smoke pos-deploy de UM ambiente (DEV/HOMOLOG/PROD): dois probes HTTP e a
# promocao do marker `.deployed-sha`. Executado por
# `appleboy/ssh-action@v1.2.0` via `script_path: infra/deploy/validate.sh`.
#
# ATUALIZACAO (cutover Docker — CI-CD.md): mesma situacao do `deploy.sh`
# vizinho — o `deploy.yml` desta branch (`cutover-docker-dev`) deixou de ter
# `script_path` apontando pra aqui, e este arquivo so continua vivo porque
# `scripts/verificar-gate-usuarios-teste.sh` ainda le ele do disco pra
# exercer o gate `usuarios_teste` antigo (teste em `xfail` explicito ate o
# porte pra Docker). Nao apagar antes disso.
#
# POR QUE O SHELL SAIU DO WORKFLOW
# Mesma razao do `deploy.sh` vizinho: o `script:` inline estava no mesmo arquivo
# que o GitHub recusava (0 jobs, conclusion=failure, 0 s) e nao da para continuar
# medindo "quantas linhas o GitHub aguenta" sem depender do numero. Ver o
# cabecalho de `infra/deploy/deploy.sh` para a medicao completa.
#
# MAPA input do workflow -> variavel de ambiente (step `env:` do job `validate`)
#   env_label            -> ENV_LABEL             usado direto nos echoes
#   app_dir              -> APP_DIR               chega pronto do ambiente
#   web_port             -> WEB_PORT              chega pronto do ambiente
#   api_port             -> API_PORT              chega pronto do ambiente
#   host                 -> HOST                  chega pronto do ambiente
#   tls_enabled          -> TLS_ENABLED           chega pronto do ambiente
#   strict_validate      -> STRICT_VALIDATE       lido em STRICT="$STRICT_VALIDATE"
#   verify_ref           -> VERIFY_REF            lido em
#                                                 EXPECTED_SHA="$VERIFY_REF"
#   pm_suffix            -> PM_SUFFIX             usado direto no `pm2 logs`
#   needs.deploy.result  -> DEPLOY_RESULT         chega pronto do ambiente
#   environment_name     -> NAO usado por este script (so no campo `environment:`)
#
# `needs.deploy.result` e o unico valor que nao vem de `inputs.*` e ainda assim
# nao pode ser uma expressao do GitHub dentro do arquivo: chega por `env:` como
# DEPLOY_RESULT, e o `grep -c` do padrao de chaves duplas tem que dar 0 aqui
# tanto quanto no `deploy.sh`.
#
# SHELL: /bin/sh (dash) na VPS.
set -e
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; nvm use 20
STRICT="$STRICT_VALIDATE"
EXPECTED_SHA="$VERIFY_REF"
# app_dir, web_port, api_port, host, tls_enabled e needs.deploy.result chegam
# prontos no ambiente; verify_ref e strict_validate sao lidos logo acima, sob
# os nomes que este script ja usava (EXPECTED_SHA e STRICT).
DEPLOYED_SHA_FILE="$APP_DIR/.deployed-sha"
API_OK=0
WEB_OK=0
API_CURL_RC=1
WEB_CURL_RC=1
API_HTTP_CODE=000
WEB_HTTP_CODE=000
write_deployed_sha() {
  local sha="$1"
  local marker_tmp="$DEPLOYED_SHA_FILE.tmp.$$"
  if ! (umask 077; printf '%s\n' "$sha" > "$marker_tmp"); then
    rm -f -- "$marker_tmp" || true
    return 1
  fi
  if ! chmod 600 -- "$marker_tmp" || ! mv -f -- "$marker_tmp" "$DEPLOYED_SHA_FILE"; then
    rm -f -- "$marker_tmp" || true
    return 1
  fi
}
probe_http() {
  local url="$1"
  local resolve_target="${2:-}"
  if [ -n "$resolve_target" ]; then
    curl -sS -o /dev/null -w "%{http_code}" --resolve "$resolve_target" "$url"
  else
    curl -sS -o /dev/null -w "%{http_code}" "$url"
  fi
}
sleep 5
# O probe é local. Antes do TLS ele fala direto com o Gunicorn;
# depois ele percorre o vhost HTTPS real, sem depender do DNS
# externo nem enviar um header de proxy diretamente ao Gunicorn.
# curl fica dentro de `if` para capturar o rc sem desligar `set -e`;
# HTTP 200 com transferência incompleta (rc != 0) continua falhando.
if [ "$TLS_ENABLED" = "true" ]; then
  if API_HTTP_CODE="$(probe_http "https://$HOST/healthz" "$HOST:443:127.0.0.1")"; then
    API_CURL_RC=0
  else
    API_CURL_RC=$?
  fi
else
  if API_HTTP_CODE="$(probe_http "http://127.0.0.1:$API_PORT/healthz")"; then
    API_CURL_RC=0
  else
    API_CURL_RC=$?
  fi
fi
[ -n "$API_HTTP_CODE" ] || API_HTTP_CODE=000
echo "$ENV_LABEL api: curl_rc=$API_CURL_RC http_code=$API_HTTP_CODE"
if [ "$API_CURL_RC" -eq 0 ] && [ "$API_HTTP_CODE" = "200" ]; then
  API_OK=1
  echo "$ENV_LABEL api ok"
elif [ "$STRICT" = "true" ]; then
  echo "$ENV_LABEL api FAIL curl_rc=$API_CURL_RC http_code=$API_HTTP_CODE"
  pm2 logs "portal-api-$PM_SUFFIX" --lines 30 --nostream 2>/dev/null || pm2 logs --lines 30 --nostream
  exit 1
else
  echo "$ENV_LABEL api warn curl_rc=$API_CURL_RC http_code=$API_HTTP_CODE"
fi
if WEB_HTTP_CODE="$(probe_http "http://127.0.0.1:$WEB_PORT/")"; then
  WEB_CURL_RC=0
else
  WEB_CURL_RC=$?
fi
[ -n "$WEB_HTTP_CODE" ] || WEB_HTTP_CODE=000
echo "$ENV_LABEL web: curl_rc=$WEB_CURL_RC http_code=$WEB_HTTP_CODE"
if [ "$WEB_CURL_RC" -eq 0 ] && [ "$WEB_HTTP_CODE" = "200" ]; then
  WEB_OK=1
  echo "$ENV_LABEL web ok"
elif [ "$STRICT" = "true" ]; then
  echo "$ENV_LABEL web FAIL curl_rc=$WEB_CURL_RC http_code=$WEB_HTTP_CODE"
  exit 1
else
  echo "$ENV_LABEL web warn curl_rc=$WEB_CURL_RC http_code=$WEB_HTTP_CODE"
fi

# `.deployed-sha` é a fronteira de recuperação. Um probe verde
# não é suficiente se o job SSH de deploy falhou, foi cancelado
# ou se o checkout não é exatamente o SHA verificado.
if [ "$API_OK" -eq 1 ] && [ "$WEB_OK" -eq 1 ]; then
  if [ "$DEPLOY_RESULT" != "success" ]; then
    echo "Marker preservado: deploy não terminou com sucesso (result=$DEPLOY_RESULT)."
  elif [ ! -d "$APP_DIR/.git" ]; then
    echo "Marker preservado: checkout $APP_DIR não existe após o deploy."
    [ "$STRICT" = "true" ] && exit 1
  else
    ACTUAL_SHA="$(git -C "$APP_DIR" rev-parse HEAD 2>/dev/null || true)"
    EXPECTED_COMMIT="$(git -C "$APP_DIR" rev-parse "$EXPECTED_SHA^{commit}" 2>/dev/null || true)"
    if [ -z "$ACTUAL_SHA" ] || [ "$ACTUAL_SHA" != "$EXPECTED_COMMIT" ]; then
      echo "Marker preservado: smoke verde, mas checkout não é o SHA verificado ($ACTUAL_SHA != $EXPECTED_COMMIT)."
      [ "$STRICT" = "true" ] && exit 1
    elif ! write_deployed_sha "$ACTUAL_SHA"; then
      echo "ERRO: smoke verde, mas não foi possível promover $DEPLOYED_SHA_FILE."
      [ "$STRICT" = "true" ] && exit 1
    else
      echo "SHA Deploy registrado após smoke: $ACTUAL_SHA"
    fi
  fi
else
  echo "Marker anterior preservado: pelo menos um probe não retornou rc=0 e HTTP 200; não promova um deploy parcial."
fi
pm2 status | grep portal || pm2 status
