#!/bin/sh
# Prova EXECUTADA do gate `usuarios_teste` do deploy (run
# 20260925-1836-usuarios-teste-dev-homolog).
#
# POR QUE ESTE ARQUIVO EXISTE
# O gate é shell dentro de um `script:` de workflow, e os critérios 5, 6, 9,
# 10 e 11 são shell — não há como prová-los com pytest semMENTIR sobre o que
# está sendo testado. A suíte Python de `backend/identidade/tests/` trava o
# comando Django; o gate em si (qual valor liga o bloco, o que sai em argv, o
# que o log afirma) só é provável rodando o script. Este harness roda o
# script do job `deploy` LITERAL, extraído do YAML, no mesmo shell da VPS
# (`/bin/sh` = dash), e afirma o comportamento.
#
# NÃO É UM TESTE DE STRING. Nada aqui procura texto no YAML: o script é
# executado de ponta a ponta, com um `backend/.env` de verdade, e a asserção é
# sobre o que o `manage.py` recebeu (`criar_usuario_carga` gravou argv real) e
# sobre o que o log afirma. Se alguém mover a validação, renomear a variável
# ou religar a leitura do `.env`, este harness acusa.
#
# O QUE ESTE HARNESS PROVA DO FINDING 1 (major/security)
#   O `set -a; . ./.env` da VPS é um arquivo `chmod 600` do usuário de deploy,
#   criado uma única vez e nunca sobrescrito, e ele atribui ao shell QUALQUER
#   chave que exista nele. Com o input do workflow em `false` e uma linha
#   `USUARIOS_TESTE=true` nesse arquivo, a versão ANTERIOR do deploy.yml ligava
#   o gate e criava superuser em PROD. Aqui isso é reproduzido de verdade.
#
# COMO RODAR
#   scripts/verificar-gate-usuarios-teste.sh            # contra o deploy.yml do repo
#   scripts/verificar-gate-usuarios-teste.sh OUTRO.yml  # contra outra versão
#                                                      # (ex.: a de antes do fix,
#                                                      #  para provar que a prova
#                                                      #  reprova a versão ruim)
#   AUTOMUTACAO=1 scripts/verificar-gate-usuarios-teste.sh
#                                                      # além dos cenários, remove
#                                                      # o selo de uma cópia do
#                                                      # workflow e exige que o
#                                                      # cenário do exploit REPROVE
#                                                      # (a prova de que a prova
#                                                      #  tem dente — roda ~40 s a
#                                                      #  mais)
#
# REQUISITOS: dash, um interpretador Python com PyYAML e o coreutils. PyYAML é
# dependência de TESTE declarada em `backend/requirements-dev.txt` (`pyyaml`),
# que o job `backend-tests` do `ci.yml` instala — logo, no CI, este requisito é
# satisfeito pelo manifesto, e não por acaso do interpretador da máquina.
# `GATE_PY_YAML=/caminho/do/python` força um interpretador específico (é o que
# o pytest faz, com `sys.executable`). Nada é escrito fora de um diretório
# temporário — os binários que o deploy chamaria de verdade (git, npm, pip,
# pm2, python) são stubs locais, e o `mkdir /home/apps` do script é
# interceptado para não criar diretório na máquina de quem roda.
#
# EXIT: 0 = todos os cenários passaram; 1 = algum cenário reprovou; 2 = o harness
# não pôde rodar (workflow ausente, sem dash, sem PyYAML).

set -u

RAIZ="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
DEPLOY_YML="${1:-$RAIZ/.github/workflows/deploy.yml}"
SHELL_ALVO="${SHELL_ALVO:-dash}"

[ -f "$DEPLOY_YML" ] || { echo "ERRO: workflow não encontrado: $DEPLOY_YML"; exit 2; }
[ -n "${TMPDIR:-}" ] || TMPDIR=/tmp
BASE="$(mktemp -d "$TMPDIR/gate-usuarios-teste.XXXXXX")"
trap 'rm -rf "$BASE"' EXIT INT TERM

# O shell do step na VPS é `/bin/sh`, que lá é dash. Rodar em dash é o que
# reproduz a review; o harness não aceita bash como substituto silencioso.
if [ "$SHELL_ALVO" = dash ] && ! command -v dash >/dev/null 2>&1; then
  echo "ERRO: 'dash' não encontrado (o step roda sob /bin/sh = dash na VPS)"; exit 2
fi
command -v "$SHELL_ALVO" >/dev/null 2>&1 || { echo "ERRO: shell $SHELL_ALVO não encontrado"; exit 2; }

# O YAML é lido com PyYAML de propósito (é a biblioteca que o projeto já usa
# nos scripts de apoio): recortar o `script:` na mão seria o teste frágil que
# este harness existe para não ser.
#
# `pyyaml` é dependência de TESTE DECLARADA em `backend/requirements-dev.txt`
# (`pyyaml==6.0.3`), que é justamente o arquivo que o job `backend-tests` do
# `ci.yml` instala. Sem essa declaração o pytest deste harness era PULADO no
# CI (Finding R1), porque o `python3` do PATH do runner é o do
# `actions/setup-python`, que só tem o que o CI instala.
#
# `GATE_PY_YAML` deixa o pytest passar o PRÓPRIO interpretador da suíte. Sem
# isso, o `command -v python3` abaixo achava o python do SISTEMA — que costuma
# ter PyYAML de apt — e o passe local virava ilusão enquanto o CI pulava o
# teste. É o mesmo mecanismo que produziu o Finding R1, fechado agora pela
# direção certa: o harness usa o interpretador que o chamador sabe ter a
# dependência, e se não tiver, ele falha em vez de pular.
PY_YAML="${GATE_PY_YAML:-}"
if [ -z "$PY_YAML" ]; then
  for candidato in python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 && "$candidato" -c "import yaml" >/dev/null 2>&1; then
      PY_YAML="$candidato"; break
    fi
  done
fi
if [ -z "$PY_YAML" ]; then
  echo "ERRO: nenhum interpretador Python com PyYAML. Instale as dependências de teste do projeto:"
  echo "      (cd backend && pip install -r requirements-dev.txt)"
  echo "      PyYAML está DECLARADO em backend/requirements-dev.txt; se este harness foi invocado"
  echo "      por outro caminho, aponte o interpretador com GATE_PY_YAML=/caminho/do/python."
  exit 2
fi
if ! "$PY_YAML" -c "import yaml" >/dev/null 2>&1; then
  echo "ERRO: o interpretador informado em GATE_PY_YAML ($PY_YAML) não tem PyYAML."
  echo "      (cd backend && pip install -r requirements-dev.txt)"
  exit 2
fi

SHA_FALSO=0123456789abcdef0123456789abcdef01234567
FALHAS=0
CENARIOS=0

# ---------------------------------------------------------------------------
# 1. Renderização do script real do job `deploy`
# ---------------------------------------------------------------------------
# Recebe o caminho do YAML, o destino e pares nome=valor dos 17 inputs. Falha
# ALTO se sobrar qualquer `${{ }}` sem renderizar ou se o YAML passar a usar
# um input novo: um harness que renderiza string vazia no lugar do input
# testaria outra coisa, não o deploy.
renderizar() {
  destino="$1"; shift
  "$PY_YAML" - "${YML_ALVO:-$DEPLOY_YML}" "$destino" "$@" <<'PY' || exit 2
import re, sys
import yaml

caminho, destino, pares = sys.argv[1], sys.argv[2], sys.argv[3:]
valores = {}
for par in pares:
    nome, _, valor = par.partition("=")
    valores[nome] = valor

doc = yaml.safe_load(open(caminho, encoding="utf-8"))
passos = [p for p in doc["jobs"]["deploy"]["steps"] if "script" in (p.get("with") or {})]
if len(passos) != 1:
    sys.exit("ERRO: esperado 1 step com script no job deploy, achei %d" % len(passos))
script = passos[0]["with"]["script"]

usados = set(re.findall(r"inputs\.([a-z0-9_]+)", script))
faltando = sorted(usados - set(valores))
if faltando:
    sys.exit("ERRO: inputs do deploy.yml sem valor no harness: %s" % ", ".join(faltando))

texto = re.sub(
    r"\$\{\{\s*inputs\.([a-z0-9_]+)\s*\}\}",
    lambda m: valores[m.group(1)],
    script,
)
sobrou = re.findall(r"\$\{\{[^}]*\}\}", texto)
if sobrou:
    sys.exit("ERRO: expressões não renderizadas: %s" % ", ".join(sorted(set(sobrou))))
open(destino, "w", encoding="utf-8").write(texto)
PY
}

# ---------------------------------------------------------------------------
# 2. Estubos
# ---------------------------------------------------------------------------
criar_estubos() {
  BIN="$1"
  mkdir -p "$BIN"

  # `nvm use 20` não existe fora da VPS; o script aborta em `command not
  # found` sem isto, e o aborta no lugar errado.
  cat > "$BIN/nvm" <<'EOF'
#!/bin/sh
exit 0
EOF

  # O `git` da VPS não é chamado de verdade (nada de rede): o objetivo é só o
  # script seguir adiante. `rev-parse` precisa devolver o MESMO sha nos dois
  # pontos onde o script compara commit esperado x checkout.
  cat > "$BIN/git" <<EOF
#!/bin/sh
case "\$1" in
  rev-parse) echo "$SHA_FALSO" ;;
esac
exit 0
EOF

  cat > "$BIN/npm" <<'EOF'
#!/bin/sh
exit 0
EOF

  cat > "$BIN/pip" <<'EOF'
#!/bin/sh
exit 0
EOF

  # `python` é o `manage.py`. Aqui está a prova: cada invocação do comando de
  # carga grava o argv REAL em arquivo, e o harness afirma sobre esse arquivo.
  # `FALHAR_QUANDO` permite reproduzir a falha por perfil (critério 9).
  cat > "$BIN/python" <<'EOF'
#!/bin/sh
if [ -n "${GATE_ARGV_LOG:-}" ]; then
  printf '%s\n' "$*" >> "$GATE_ARGV_LOG"
  printf 'PROD_SEED_PASSWORD=%s\n' "${PROD_SEED_PASSWORD:+PRESENTE}" >> "$GATE_ARGV_LOG"
fi
case "$*" in
  *criar_usuario_carga*"${FALHAR_QUANDO:-__nada__}"*) exit 3 ;;
  *criar_usuario_carga*) exit 0 ;;
esac
exit 0
EOF

  # `python3` é usado em dois lugares: `pm2 jlist` precisa do interpretador de
  # verdade (o script valida o JSON), e `python3 -m venv` é dispensável aqui.
  REAL_PY3="$(command -v python3 || true)"
  cat > "$BIN/python3" <<EOF
#!/bin/sh
if [ "\$1" = "-m" ] && [ "\$2" = "venv" ]; then exit 0; fi
if [ "\$1" = "-c" ] && [ -n "$REAL_PY3" ]; then exec "$REAL_PY3" "\$@"; fi
exit 0
EOF

  # `pm2 jlist` responde "online" logo de primeira, para o harness não entrar
  # no laço de retry com `sleep` (o comportamento do PM2 não é o que se testa).
  # O sufixo do ambiente vem em GATE_PM_SUF porque `SUF` é uma variável do
  # shell do deploy, não exportada — e o nome do processo depende dele.
  cat > "$BIN/pm2" <<'EOF'
#!/bin/sh
if [ "$1" = "jlist" ]; then
  printf '[{"name":"portal-web-%s","pm2_env":{"status":"online"}},' "${GATE_PM_SUF:?harness sem GATE_PM_SUF}"
  printf '{"name":"portal-api-%s","pm2_env":{"status":"online"}}]\n' "${GATE_PM_SUF:?harness sem GATE_PM_SUF}"
fi
exit 0
EOF

  # O script roda `mkdir -p /home/apps` sem guarda. Interceptado para não criar
  # diretório na máquina de quem roda o harness; todo o resto vai para o mkdir
  # de verdade, porque o harness precisa de diretório real em APP_DIR.
  MKDIR_REAL="$(command -v mkdir)"
  cat > "$BIN/mkdir" <<EOF
#!/bin/sh
interceptado=0
so_opcoes=1
restante=""
for a in "\$@"; do
  case "\$a" in
    /home/apps) interceptado=1 ;;
    -*) restante="\$restante \$a" ;;
    *) so_opcoes=0; restante="\$restante \$a" ;;
  esac
done
if [ "\$interceptado" -eq 0 ]; then exec $MKDIR_REAL "\$@"; fi
if [ "\$so_opcoes" -eq 1 ]; then exit 0; fi
exec $MKDIR_REAL \$restante
EOF

  chmod +x "$BIN"/*
}

# ---------------------------------------------------------------------------
# 3. Montagem de uma "VPS" descartável + execução do script real
# ---------------------------------------------------------------------------
# $1 = nome do cenário, $2 = sufixo, $3 = usuarios_teste, $4 = linhas extras
# do backend/.env (exploit), $5 = perfil que deve falhar (vazio = nenhum)
montar_e_rodar() {
  CEN="$1"; SUF="$2"; GATE="$3"; ENV_EXPLOIT="$4"; FALHAR_QUANDO="${5:-}"
  APP="$BASE/$CEN"
  BIN="$BASE/$CEN/bin"
  ARGV_LOG="$BASE/$CEN/argv.log"
  OUT="$BASE/$CEN/saida.log"
  SCRIPT="$BASE/$CEN/deploy.sh"

  mkdir -p "$APP/.git" "$APP/frontend" "$APP/backend/.venv/bin"
  : > "$APP/backend/.venv/bin/activate"
  : > "$ARGV_LOG"

  {
    # Linhas que o próprio deploy exige e valida (`tls_enabled=false`).
    printf 'DJANGO_SECRET_KEY=harness\nDJANGO_DEBUG=false\n'
    printf 'DJANGO_ALLOWED_HOSTS=harness\n'
    printf 'DJANGO_SECURE_SSL_REDIRECT=false\n'
    printf 'DJANGO_SESSION_COOKIE_SECURE=false\nDJANGO_CSRF_COOKIE_SECURE=false\n'
    printf 'DJANGO_DB_ENGINE=postgresql\nDJANGO_DB_NAME=brd\nDJANGO_DB_USER=postgres\n'
    printf 'DJANGO_DB_PASSWORD=senha-do-harness\nDJANGO_DB_HOST=localhost\nDJANGO_DB_PORT=5432\n'
    printf 'FRONTEND_BASE_URL=http://harness\n'
    [ -n "$ENV_EXPLOIT" ] && printf '%s\n' "$ENV_EXPLOIT"
  } > "$APP/backend/.env"
  chmod 600 "$APP/backend/.env"

  renderizar "$SCRIPT" \
    "env_label=$SUF" "environment_name=env-$SUF" "app_dir=$APP" \
    "git_mode=branch" "git_ref=main" "verify_ref=$SHA_FALSO" "pr_number=" \
    "pm_suffix=$SUF" "web_port=8080" "api_port=8081" "host=harness.local" \
    "tls_enabled=false" "allowed_hosts_extra=" "db_name=brd" "db_user=postgres" \
    "strict_validate=false" "web_runtime=npm" "celery_systemd=false" \
    "sentry_exigido=false" "usuarios_teste=$GATE" || return 2

  criar_estubos "$BIN"
  # shellcheck disable=SC2086
  if env -i \
      PATH="$BIN:/usr/bin:/bin" \
      HOME="$BASE/$CEN/home" \
      GATE_ARGV_LOG="$ARGV_LOG" \
      GATE_PM_SUF="$SUF" \
      FALHAR_QUANDO="$FALHAR_QUANDO" \
      "$SHELL_ALVO" "$SCRIPT" > "$OUT" 2>&1; then
    RC=0
  else
    RC=$?
  fi
  mkdir -p "$BASE/$CEN/home"
  # `grep -c` imprime 0 e sai 1 quando não acha; o `|| true` impede o `0` extra
  # que um `|| echo 0` acrescentaria (viraria "0\n0" e quebraria o `-ne`).
  INVOCACOES="$(grep -c 'criar_usuario_carga' "$ARGV_LOG" 2>/dev/null || true)"
  case "${INVOCACOES:-}" in
    ''|*[!0-9]*) INVOCACOES=0 ;;
  esac
}

ok() { CENARIOS=$((CENARIOS + 1)); printf '  ok   %s\n' "$1"; }
reprova() {
  CENARIOS=$((CENARIOS + 1)); FALHAS=$((FALHAS + 1))
  printf '  FALHA %s\n' "$1"
  [ -f "$OUT" ] && sed -n '1,200p' "$OUT" | sed 's/^/       | /'
  return 0
}

# ===========================================================================
# CENÁRIO 1 — o exploit do Finding 1 (o que a review reproduziu)
#   Input do workflow = false (o que o deploy-prod.yml manda), backend/.env da
#   VPS com o gate ligado por variável de ambiente, em VARIOS nomes — porque
#   trocar o nome da variável não resolve, o `.env` é arbitrário.
# ===========================================================================
EXPLOIT='USUARIOS_TESTE=true
PORTAL_USUARIOS_TESTE=true
USUARIOS_TESTE_INPUT=true
USUARIOS_TESTE_GATE=true
TEST_USUARIOS=true
DJANGO_CREATE_TEST_USERS=true'

echo "== gate usuarios_teste: prova executada =="
echo "workflow: $DEPLOY_YML"
echo "shell:    $SHELL_ALVO"
echo "yaml:     $PY_YAML"

# O cenário do exploit, isolado em função porque ele é usado duas vezes: contra
# o workflow como está, e contra uma cópia com o selo removido (ver
# AUTOMUTACAO no fim). Retorna 0 se a proteção segurou, 1 se o `.env` venceu.
cenario_exploit() {
  montar_e_rodar prod-env-liga-o-gate prod false "$EXPLOIT"
  if [ "$RC" -ne 0 ]; then
    reprova "PROD com USUARIOS_TESTE=true no .env: deploy abortou (exit=$RC) — o gate nem precisa ligar para isso ser falha"
    return 1
  fi
  if [ "$INVOCACOES" -ne 0 ]; then
    reprova "PROD com USUARIOS_TESTE=true no .env: o gate RODOU ($INVOCACOES invocações). O .env sobrepôs o input do workflow."
    return 1
  fi
  ok "PROD + .env com USUARIOS_TESTE=true (e 5 nomes equivalentes): 0 invocações — o input do workflow é o único que decide"
  if ! grep -q 'Usuarios de teste: usuarios_teste=false' "$OUT"; then
    reprova "PROD: o log não registrou o gate desligado"
    return 1
  fi
  ok "  …e o log diz que o gate está desligado"
  return 0
}

cenario_exploit

# ===========================================================================
# CENÁRIO 2 — DEV: ligado de propósito, argv conferido (critérios 5 e 11)
# ===========================================================================
montar_e_rodar dev-ligado dev true ""
if [ "$RC" -ne 0 ]; then
  reprova "DEV com o gate ligado: o deploy abortou (exit=$RC)"
elif [ "$INVOCACOES" -ne 3 ]; then
  reprova "DEV com o gate ligado: esperado 3 invocações, veio $INVOCACOES"
else
  ok "DEV com o gate ligado: 3 invocações de criar_usuario_carga"
  grep -q -- '--email teste-free@dev.portal-noticias.com.br --sem-senha --papel free$' "$ARGV_LOG" \
    && ok "  free:   --email teste-free@dev… --sem-senha --papel free" \
    || reprova "  free: argv inesperado"
  grep -q -- '--email teste-premium@dev.portal-noticias.com.br --sem-senha --papel premium$' "$ARGV_LOG" \
    && ok "  premium: --email teste-premium@dev… --sem-senha --papel premium" \
    || reprova "  premium: argv inesperado"
  grep -q -- '--email teste-admin@dev.portal-noticias.com.br --sem-senha --papel admin --superuser$' "$ARGV_LOG" \
    && ok "  admin:  --superuser só no admin" \
    || reprova "  admin: argv inesperado"
  SUPERUSERS="$(grep -c -- '--superuser' "$ARGV_LOG")"
  [ "$SUPERUSERS" -eq 1 ] \
    && ok "  --superuser aparece em exatamente 1 das 3 chamadas" \
    || reprova "  --superuser aparece $SUPERUSERS vezes (esperado 1)"
  grep -q -- '--password' "$ARGV_LOG" \
    && reprova "  --password apareceu no argv" \
    || ok "  nenhum --password no argv"
  grep -q 'PROD_SEED_PASSWORD=PRESENTE' "$ARGV_LOG" \
    && reprova "  PROD_SEED_PASSWORD estava no ambiente" \
    || ok "  PROD_SEED_PASSWORD ausente do ambiente"
fi

# ===========================================================================
# CENÁRIO 3 — HOMOLOG
# ===========================================================================
montar_e_rodar homolog-ligado homolog true ""
if [ "$RC" -eq 0 ] && [ "$INVOCACOES" -eq 3 ]; then
  ok "HOMOLOG com o gate ligado: 3 invocações"
else
  reprova "HOMOLOG: exit=$RC, invocações=$INVOCACOES (esperado 0 e 3)"
fi

# ===========================================================================
# CENÁRIO 4 — o `.env` não desliga o gate em DEV (mesma proteção, sentido inverso)
# ===========================================================================
montar_e_rodar dev-env-tenta-desligar dev true 'USUARIOS_TESTE=false
PORTAL_USUARIOS_TESTE=false'
if [ "$RC" -eq 0 ] && [ "$INVOCACOES" -eq 3 ]; then
  ok "DEV + .env com USUARIOS_TESTE=false: o gate continua ligado (3 invocações) — o .env não manda em nenhum dos dois sentidos"
else
  reprova "DEV + .env com USUARIOS_TESTE=false: exit=$RC, invocações=$INVOCACOES (esperado 0 e 3)"
fi

# ===========================================================================
# CENÁRIO 5 — valor fora de true/false aborta (critério 10)
# ===========================================================================
montar_e_rodar valor-invalido dev sim ""
if [ "$RC" -eq 1 ] && [ "$INVOCACOES" -eq 0 ]; then
  ok "usuarios_teste=sim: exit=1 e 0 invocações (falha-closed)"
else
  reprova "usuarios_teste=sim: exit=$RC, invocações=$INVOCACOES (esperado 1 e 0)"
fi
# O `.env` com valor inválido também não pode escapar da revalidação: aqui o
# input é válido, o `.env` é lixo, e o deploy precisa seguir com o input.
montar_e_rodar dev-env-lixo dev true 'USUARIOS_TESTE=talvez
PORTAL_USUARIOS_TESTE='
if [ "$RC" -eq 0 ] && [ "$INVOCACOES" -eq 3 ]; then
  ok "DEV + .env com USUARIOS_TESTE=talvez: o input válido manda e o deploy segue"
else
  reprova "DEV + .env com USUARIOS_TESTE=talvez: exit=$RC, invocações=$INVOCACOES (esperado 0 e 3)"
fi

# ===========================================================================
# CENÁRIO 6 — falha por perfil não derruba o deploy (critério 9) e o aviso
# com a receita manual é impresso (o `if !` da chamada deixou de ser morto)
# ===========================================================================
montar_e_rodar falha-por-perfil homolog true "" "teste-admin@"
if [ "$RC" -ne 0 ]; then
  reprova "só o admin falhando: o deploy abortou (exit=$RC) — o set -e matou o job"
elif [ "$INVOCACOES" -ne 3 ]; then
  reprova "só o admin falhando: esperado 3 invocações, veio $INVOCACOES"
else
  ok "só o admin falhando: exit=0 e as 3 chamadas feitas (o deploy não caiu)"
fi
grep -q 'AVISO: falha ao criar/atualizar teste-admin@homolog.portal-noticias.com.br' "$OUT" \
  && ok "  o AVISO por perfil saiu" \
  || reprova "  o AVISO por perfil não saiu"
grep -q '2 de 3 contas prontas' "$OUT" \
  && ok "  o resumo diz 2 de 3" \
  || reprova "  o resumo não diz 2 de 3"
grep -q 'Crie as contas a mao' "$OUT" \
  && ok "  a receita manual saiu (o if-not da chamada está vivo)" \
  || reprova "  a receita manual NÃO saiu — o ramo da chamada é código morto de novo"

# ===========================================================================
# CENÁRIO 7 — o log diz a verdade sobre a entrega do e-mail (Finding 2)
# ===========================================================================
montar_e_rodar email-console dev true "DJANGO_EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend"
if grep -q 'NAO chega em nenhum inbox' "$OUT" && grep -q "pm2 logs portal-api-dev" "$OUT"; then
  ok "console backend: o log avisa que o e-mail não chega e diz onde ele sai (pm2 logs portal-api-dev)"
else
  reprova "console backend: o log continua afirmando que /recuperar-senha está pronto"
fi
grep -q 'uid/token, que e credencial' "$OUT" \
  && ok "  o log avisa que o uid/token do e-mail é credencial" \
  || reprova "  o log não avisa sobre o token no log da VPS"

montar_e_rodar email-real dev true "DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend"
if grep -q 'Entrega do e-mail de recuperacao: DJANGO_EMAIL_BACKEND=config.email_resend.ResendEmailBackend' "$OUT"; then
  ok "backend real: o log diz qual backend está em uso e não inventa o problema"
else
  reprova "backend real: o log não informou o backend de e-mail em uso"
fi

montar_e_rodar email-ausente dev true ""
if grep -q 'ausente ou console' "$OUT"; then
  ok "backend ausente: o log cai no aviso do console (que é o default do Django)"
else
  reprova "backend ausente: o log não avitou o default console"
fi

# ===========================================================================
# CENÁRIO 8 — o `.env` não decide o SUFIXO (Finding R3)
#   Mesmo formato do Finding 1, 30 linhas mais abaixo: `SUF` também era lido do
#   `.env` depois do source, e é o que monta o domínio do e-mail das contas.
#   Com `SUF=prod` no `.env` de DEV o gate criava `teste-admin@prod.…` — os
#   MESMOS endereços de produção (numa base de DEV). Este cenário é
#   COMPORTAMENTAL: afirma o argv que o `manage.py` recebeu, e não o texto do
#   bloco que faz o lacre.
# ===========================================================================
montar_e_rodar dev-env-troca-sufixo dev true 'SUF=prod'
if [ "$INVOCACOES" -eq 3 ]; then
  ok "DEV + .env com SUF=prod: as 3 contas são criadas (o gate não é afetado pelo .env)"
else
  reprova "DEV + .env com SUF=prod: esperado 3 invocações, veio $INVOCACOES (exit=$RC)"
fi
DOMINIOS_ERRADOS="$(grep -c '@prod.portal-noticias.com.br' "$ARGV_LOG" 2>/dev/null || true)"
case "${DOMINIOS_ERRADOS:-}" in
  ''|*[!0-9]*) DOMINIOS_ERRADOS=0 ;;
esac
if [ "$DOMINIOS_ERRADOS" -ne 0 ]; then
  reprova "DEV + .env com SUF=prod: $DOMINIOS_ERRADOS e-mail(s) criados no domínio de PROD — o .env escolheu o sufixo"
else
  ok "  nenhum e-mail no domínio de PROD: o sufixo veio do input do workflow"
fi
for papel in free premium admin; do
  if ! grep -q -- "--email teste-$papel@dev.portal-noticias.com.br " "$ARGV_LOG"; then
    reprova "  e-mail do perfil $papel não saiu com o domínio de DEV (argv: $(grep 'criar_usuario_carga' "$ARGV_LOG" | tr '\n' ' '))"
  fi
done
grep -q 'pm2 logs portal-api-dev' "$OUT" \
  && ok "  os 3 e-mails saíram com @dev.portal-noticias.com.br e o log aponta o processo do ambiente certo" \
  || reprova "  o log aponta para o processo de outro ambiente — o \$SUF do .env vazou para o log do gate"
# Consequência do mesmo lacre, registrada aqui porque é a consequência mais
# grave: com o `SUF` do `.env`, o bloco de PM2 (que é de outra run e NÃO foi
# tocado) chamava `restart_or_start "portal-web-prod"` num deploy de DEV — ou
# seja, reiniciar o processo de produção com o código de DEV. O bloco de PM2
# continua lendo `$SUF`; o que mudou é de onde `$SUF` vem. O follow-up
# (blindar os outros knobs lidos depois do `.env`) fica registrado no
# implementation-history.md.
if grep -qE 'portal-(web|api)-prod' "$OUT"; then
  reprova "DEV + .env com SUF=prod: o deploy tentou mexer em processo de PROD (restart/delete fora do ambiente)"
else
  ok "  nenhum processo de PROD foi tocado por um deploy de DEV com SUF=prod no .env"
fi

echo
echo "== $((CENARIOS - FALHAS))/$CENARIOS asserções passaram =="

# ---------------------------------------------------------------------------
# AUTOMUTACAO=1 — a prova de que a prova tem dente
# ---------------------------------------------------------------------------
# Remove, de uma CÓPIA do workflow, o bloco que reatribui o input do workflow
# DEPOIS do `set -a; . ./.env` (o selo) e exige que o cenário do exploit
# REPROVE. Sem esta checagem, um harness que passasse por acidente — ou que
# tivesse parado de rodar o script de verdade — continuaria "verde".
#
# POR QUE A MUTAÇÃO PROCURA ESTRUTURA E NÃO A STRING DO FIX (Finding R2)
# A versão anterior procurava a literal `USUARIOS_TESTE="${{ inputs.usuarios_teste }}"`
# e, se não achasse, saía com rc=2 — punindo um fix ALTERNATIVO e igualmente
# correto (por exemplo, passar o input por parâmetro de função depois do
# source, que nenhum `.env` alcança). O comportamento do gate seria idêntico e
# o CI ficaria vermelho: falso positivo barulhento.
#
# Agora a busca é estrutural: "a primeira linha Effectively executada depois do
# source do `.env` que volta a mencionar o input `usuarios_teste`", mais o
# bloco `case … esac` ou as atribuições imediatamente seguintes. Isso cobre o
# fix atual, o `GATE_USUARIOS_TESTE="…"; USUARIOS_TESTE="$GATE_USUARIOS_TESTE"`
# e a forma por parâmetro de função. E, se NENHUMA forma for encontrada, o
# resultado é **NÃO APLICÁVEL**, que é um desfecho distinto de reprovação: o
# selo sumiu de vez, e nesse caso quem acusa é o cenário do exploit, que é
# comportamental e roda sempre.
if [ -n "${AUTOMUTACAO:-}" ]; then
  echo
  echo "== AUTOMUTACAO: removendo o selo pós-.env e exigindo que o exploit volte =="
  MUTADO="$BASE/deploy-sem-selo.yml"
  MUTACAO_MSG="$("$PY_YAML" - "$DEPLOY_YML" "$MUTADO" <<'PY'
import re
import sys

caminho, saida = sys.argv[1], sys.argv[2]
linhas = open(caminho, encoding="utf-8").read().split("\n")
RE_ATRIB = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MARCA_INPUT = "inputs.usuarios_teste"


def proxima_util(i):
    """Próxima linha a partir de i+1 que seja código (ignora vazio/comentário)."""
    for j in range(i + 1, len(linhas)):
        s = linhas[j].strip()
        if s and not s.startswith("#"):
            return j
    return None


fonte = next((i for i, l in enumerate(linhas) if "set -a; . ./.env; set +a" in l), None)
if fonte is None:
    sys.exit("ERRO: não achei o `set -a; . ./.env; set +a` para usar de referência.")

inicio = next(
    (i for i in range(fonte + 1, len(linhas))
     if linhas[i].strip() and not linhas[i].strip().startswith("#") and MARCA_INPUT in linhas[i]),
    None,
)
if inicio is None:
    # Desfecho 3 = "não aplicável", e NÃO é erro: o selo pode ter sido
    # implementado de uma forma que este harness não reconhece, ou não existir
    # (e aí quem falha é o cenário do exploit, comportamental).
    sys.exit(3)

fim = inicio
if RE_ATRIB.match(linhas[inicio].strip()):
    # Atribuições encadeadas do mesmo bloco (ex.: um valor intermediário).
    j = proxima_util(inicio)
    while j is not None and RE_ATRIB.match(linhas[j].strip()):
        fim = j
        j = proxima_util(j)
j = proxima_util(fim)
if j is not None and linhas[j].strip().startswith("case "):
    for k in range(j, len(linhas)):
        if linhas[k].strip() == "esac":
            fim = k
            break

removido = "\n".join(linhas[inicio:fim + 1])
open(saida, "w", encoding="utf-8").write(
    "\n".join(linhas[:inicio] + linhas[fim + 1:])
)
print("removido do workflow copiado:\n%s" % removido)
PY
)"
  MUT_RC=$?
  if [ "$MUT_RC" -eq 0 ]; then
    printf '%s\n' "$MUTACAO_MSG"
    YML_ALVO="$MUTADO"
    FALHAS_ANTES="$FALHAS"
    CENARIOS_ANTES="$CENARIOS"
    if cenario_exploit; then
      echo
      echo "RESULTADO: REPROVADO — o cenário do exploit NÃO detectou a remoção do selo."
      echo "A prova acima não serve para nada; corrija o harness antes de confiar nela."
      exit 1
    fi
    # A mutação só podia falhar pelo motivo certo: o gate ter criado conta de
    # PROD (o sufixo `prod` no log). Outro motivo de reprovação seria um bug do
    # harness, e não contaria como prova.
    FALHAS="$FALHAS_ANTES"
    CENARIOS="$CENARIOS_ANTES"
    if grep -q 'teste-admin@prod.portal-noticias.com.br pronto' "$BASE/prod-env-liga-o-gate/saida.log"; then
      ok "  sem o selo, o exploit volta: PROD criaria teste-admin (papel=admin) por .env — o cenário detecta a remoção, a prova tem dente"
    else
      reprova "  sem o selo, o exploit falhou por outro motivo que não ser o gate ter rodado; a mutação não provou nada"
    fi
  elif [ "$MUT_RC" -eq 3 ]; then
    # NÃO reprova: um fix correto com outra forma não pode deixar o CI vermelho.
    # A proteção de regressão continua sendo o cenário do exploit, que é
    # comportamental e roda em toda execução deste harness.
    CENARIOS=$((CENARIOS + 1))
    echo "MUTAÇÃO: NÃO APLICÁVEL — nenhuma linha depois do \`set -a; . ./.env\` volta a"
    echo "           mencionar o input \`usuarios_teste\`. Isto NÃO é uma falha: se o selo"
    echo "           foi implementado de outra forma, a mutação por string não tem o que"
    echo "           remover. O que protege a regressão é o cenário do exploit acima"
    echo "           (comportamental, roda sempre). Se a intenção era remover o selo de"
    echo "           verdade, a forma nova do selo precisa ser reconhecida aqui."
  else
    echo "ERRO: a mutação falhou (rc=$MUT_RC):"
    printf '%s\n' "$MUTACAO_MSG"
    exit 2
  fi
fi

if [ "$FALHAS" -ne 0 ]; then
  echo "RESULTADO: REPROVADO ($FALHAS)"
  exit 1
fi
echo "RESULTADO: OK"
exit 0
