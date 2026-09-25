#!/usr/bin/env bash
#
# Gate determinístico de release / proveniência
# Run 20260925-1433-go-live-producao — lote P0-1 (P0-09), gate "G-gate-P0-1".
#
# USO
#   scripts/release/verificar-proveniencia.sh [--expected-sha <40-hex>] [--repo <dir>] [--json]
#   scripts/release/verificar-proveniencia.sh --help
#
# EXIT CODES
#   0  aprovado: todas as checagens passaram E --expected-sha foi informado e
#      igualou o HEAD
#   1  reprovado: uma ou mais checagens falharam, não puderam ser executadas,
#      ou o resultado ficou incompleto (inclui --expected-sha ausente)
#   2  uso incorreto: flag desconhecida, valor ausente, --expected-sha fora do
#      formato de 40 hex, ou --repo que não existe / não é um repositório Git
#
# O QUE O GATE REPROVA (fail-closed)
#   1. repositório inválido ou ferramenta ausente
#   2. HEAD diferente do SHA de release esperado
#   3. arquivo rastreado modificado, removido ou renomeado
#   4. arquivo não rastreado presente (respeitando .gitignore)
#   5. assume-unchanged / skip-worktree (flags do índice) escondendo estado de
#      arquivo: são lidas do índice com `git ls-files -v`, porque nem `git
#      status` nem `git diff` veem alteração escondida por essas flags
#   6. marcador de conflito de merge em arquivo rastreado
#   7. segredo aparente em arquivo rastreado
#   8. .py rastreado que não faz parse
#   9. .yml/.yaml rastreado que não faz parse
#
# O QUE O GATE NÃO FAZ (e não deve ser lido como se fizesse)
#   - não altera, cria, move ou apaga arquivo algum; não usa arquivo temporário
#   - não executa git add/commit/push/merge/rebase/reset/clean/checkout/switch/
#     stash/restore/apply nem qualquer outro comando git de escrita
#   - não acessa a rede, não consulta remoto, não fala com GitHub
#   - não lê variável de ambiente que possa conter segredo e não exige segredo
#   - não imprime valor de segredo: o achado traz só regra, caminho e linha
#   - não roda em nenhum workflow: o CI/CD existente não foi alterado, então o
#     gate só é efetivo se for invocado por alguém e se a branch protection do
#     GitHub o tiver como required status check (HD-2)
#   - não cobre o caminho de deploy por pull request até a VPS (R-1, aceito e
#     aberto): esse risco NÃO é mitigado nem bloqueado por este gate
#
# Saída determinística: sem timestamp, sem cor, achados ordenados por
# (checagem, caminho, linha, regra), para permitir diff entre execuções.

set -uo pipefail

NOME_GATE="verificar-proveniencia"
VERSAO_GATE="1"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"

REPO=""
ESPERADO=""
SHA_INFORMADO=0
MODO="texto"

imprimir_uso() {
    cat <<'TEXTO_USO_GATE'
Gate determinístico de release / proveniência (read-only, fail-closed).

USO
  verificar-proveniencia.sh [--expected-sha <40-hex>] [--repo <dir>] [--json]
  verificar-proveniencia.sh --help

OPÇÕES
  --expected-sha <40-hex>  SHA de release esperado (40 caracteres hex).
                           Obrigatório para o gate de release: sem esta flag o
                           resultado fica INCOMPLETO e a saída é 1 — ausência da
                           flag nunca é aprovação automática nem por omissão.
                           Formato inválido é uso incorreto (2), não SHA ausente.
  --repo <dir>             repositório a inspecionar
                           (padrão: raiz do repositório onde este script vive).
  --json                   saída estruturada. Nunca inclui valor de segredo.
  --help                   imprime este texto e sai com 0, sem rodar checagem.

EXIT CODES
  0  aprovado
  1  reprovado (checagem falhou, não pôde rodar, ou resultado incompleto)
  2  uso incorreto

CHECAGENS
  repo-valido     repositório Git resolvido e legível
  ferramentas     git e python3 disponíveis (falha fechada se faltar)
  sha-release     HEAD igual ao SHA de release esperado
  arvore-limpa    nenhum arquivo rastreado modificado, removido ou renomeado
  sem-untracked   nenhum arquivo não rastreado (respeitando .gitignore)
  sem-ocultacao   nenhum assume-unchanged / skip-worktree (flags do índice,
                  lidas com `git ls-files -v`; o gate reprova pela presença da
                  flag, mesmo sem divergência de conteúdo)
  sem-conflito    sem marcadores de conflito em arquivo rastreado
  sem-segredos    sem segredo aparente em arquivo rastreado
  python-valido   todo .py rastreado faz parse
  yaml-valido     todo .yml/.yaml rastreado faz parse

LIMITES CONHECIDOS (declarados, não escondidos)
  - a detecção de assume-unchanged/skip-worktree lê as flags do índice com
    `git ls-files -v`, que são case-sensitive: 'H' é o estado normal, 'h'
    minúscula é assume-unchanged, 'S' é skip-worktree e 's' minúscula são as
    duas. Git status e git diff NÃO veem alteração escondida por essas flags
  - a detecção de segredo é heurística; valores de placeholder são filtrados
    por lista explícita e o valor nunca é exibido
  - caminho de arquivo é exibido como está; um arquivo cujo próprio nome
    carregasse segredo exporia o nome, não o conteúdo
  - o gate não é nenhuma barreira por si só: sem branch protection do GitHub
    e sem registro como required status check ele só reprova localmente
  - o gate não cobre o caminho pull request -> VPS de HOMOLOG (R-1), que
    permanece ativo, aceito, aberto, não mitigado e não coberto aqui
TEXTO_USO_GATE
}

erro_uso() {
    # erro_uso <motivo>
    local motivo="$1"
    printf 'erro de uso: %s\n' "$motivo" >&2
    printf 'use --help para ver o contrato desta CLI\n' >&2
    exit 2
}

falha_ferramenta() {
    # falha_ferramenta <motivo> — python3 ausente: não há engine, saída mínima
    local motivo="$1"
    if [ "$MODO" = "json" ]; then
        printf '%s\n' "{\"gate\":\"$NOME_GATE\",\"versao\":\"$VERSAO_GATE\",\"repo\":null,\"sha_esperado\":null,\"resultado\":\"reprovado\",\"resultado_incompleto\":true,\"checagens\":[{\"id\":\"2\",\"nome\":\"ferramentas\",\"status\":\"nao-executada\",\"detalhe\":\"$motivo\",\"achados\":0}],\"achados\":[],\"resumo\":{\"checagens_ok\":0,\"checagens_falha\":0,\"checagens_nao_executadas\":1,\"achados\":0},\"exit_code\":1}"
    else
        printf 'GATE DE PROVENIENCIA (%s)\n' "$NOME_GATE"
        printf 'repo: (nao resolvido)\n'
        printf 'resultado: REPROVADO\n'
        printf 'resultado-incompleto: sim\n\n'
        printf 'CHECAGENS\n'
        printf '[nao-executada] 2 ferramentas — %s\n\n' "$motivo"
        printf 'TOTAIS\nchecagens-ok: 0\nchecagens-falha: 0\nchecagens-nao-executadas: 1\nachados: 0\nexit-code: 1\n'
    fi
    exit 1
}

# ---------------------------------------------------------------- argumentos
while [ "$#" -gt 0 ]; do
    case "$1" in
        --expected-sha)
            if [ "$#" -lt 2 ]; then
                erro_uso "--expected-sha exige um valor (40 caracteres hex)"
            fi
            ESPERADO="$2"
            SHA_INFORMADO=1
            shift 2
            ;;
        --expected-sha=*)
            ESPERADO="${1#--expected-sha=}"
            SHA_INFORMADO=1
            shift
            ;;
        --repo)
            if [ "$#" -lt 2 ]; then
                erro_uso "--repo exige um caminho"
            fi
            REPO="$2"
            shift 2
            ;;
        --repo=*)
            REPO="${1#--repo=}"
            shift
            ;;
        --json)
            MODO="json"
            shift
            ;;
        --help|-h)
            imprimir_uso
            exit 0
            ;;
        *)
            erro_uso "flag desconhecida: $1"
            ;;
    esac
done

if [ "$SHA_INFORMADO" -eq 1 ]; then
    if ! printf '%s' "$ESPERADO" | LC_ALL=C grep -Eq '^[0-9a-fA-F]{40}$'; then
        erro_uso "--expected-sha exige exatamente 40 caracteres hex (recebido: ${#ESPERADO} caracter(es))"
    fi
fi

# ------------------------------------------------------------------ repo
if [ -z "$REPO" ]; then
    if ! command -v git >/dev/null 2>&1; then
        erro_uso "git nao encontrado e --repo nao foi informado: a raiz do repositorio nao pode ser resolvida"
    fi
    REPO="$(GIT_OPTIONAL_LOCKS=0 GIT_PAGER=cat git -C "$SCRIPT_DIR/../.." rev-parse --show-toplevel 2>/dev/null)"
    if [ -z "$REPO" ]; then
        erro_uso "nao foi possivel resolver a raiz do repositorio a partir de $SCRIPT_DIR; informe --repo"
    fi
fi

if [ ! -d "$REPO" ]; then
    erro_uso "--repo aponta para um diretorio inexistente"
fi

if ! command -v git >/dev/null 2>&1; then
    falha_ferramenta "git nao encontrado no PATH (falha fechada: sem git nao ha inventario confiavel)"
fi

if ! command -v python3 >/dev/null 2>&1; then
    falha_ferramenta "python3 nao encontrado no PATH (falha fechada: o parse in-memory e obrigatorio)"
fi

REPO_ABS="$(GIT_OPTIONAL_LOCKS=0 GIT_PAGER=cat git -C "$REPO" rev-parse --show-toplevel 2>/dev/null)"
if [ -z "$REPO_ABS" ]; then
    erro_uso "--repo nao e um repositorio Git valido"
fi

# ------------------------------------------------------------------ engine
# Toda a lógica de conteúdo roda em um único python3 in-memory (stdin), sem
# arquivo temporário e sem gerar __pycache__. Nenhum valor de segredo é lido
# para fora: o engine só devolve regra, caminho, linha e motivo.
PYTHONDONTWRITEBYTECODE=1 python3 - "$REPO_ABS" "$ESPERADO" "$SHA_INFORMADO" "$MODO" <<'PY'
import json
import os
import re
import shutil
import subprocess
import sys

REPO, ESPERADO, SHA_INFORMADO, MODO = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
SHA_INFORMADO = SHA_INFORMADO == "1"

CHECAGENS = [
    ("1", "repo-valido", "repositorio Git resolvido e legivel"),
    ("2", "ferramentas", "git e python3 disponiveis (falha fechada se faltar)"),
    ("3", "sha-release", "HEAD igual ao SHA de release esperado"),
    ("4", "arvore-limpa", "nenhum arquivo rastreado modificado, removido ou renomeado"),
    ("5", "sem-untracked", "nenhum arquivo nao rastreado (respeitando .gitignore)"),
    ("6", "sem-ocultacao", "nenhum assume-unchanged / skip-worktree"),
    ("7", "sem-conflito", "sem marcadores de conflito em arquivo rastreado"),
    ("8", "sem-segredos", "sem segredo aparente em arquivo rastreado"),
    ("9", "python-valido", "todo .py rastreado faz parse"),
    ("10", "yaml-valido", "todo .yml/.yaml rastreado faz parse"),
]
NOMES = {c[1]: c[0] for c in CHECAGENS}

estado = {}          # nome -> {"status": ..., "detalhe": ...}
achados = []         # {"checagem","caminho","linha","regra","mensagem"}


def registrar(nome, status, detalhe=""):
    estado[nome] = {"status": status, "detalhe": detalhe}


def achado(nome, caminho, linha, regra, mensagem):
    achados.append(
        {
            "checagem": nome,
            "id": NOMES[nome],
            "caminho": caminho,
            "linha": linha,
            "regra": regra,
            "mensagem": mensagem,
        }
    )


# --- ambiente git enxuto: sem nenhum GIT_* herdado (evita injetar GIT_DIR /
# --- GIT_WORK_TREE / GIT_INDEX_FILE), sem pager e sem lock de índice.
ENV_GIT = {"PATH": os.environ.get("PATH", ""), "LC_ALL": "C", "LANG": "C",
           "GIT_PAGER": "cat", "PAGER": "cat", "GIT_OPTIONAL_LOCKS": "0"}
if os.environ.get("HOME"):
    ENV_GIT["HOME"] = os.environ["HOME"]


def git(*args):
    proc = subprocess.run(
        ["git", "-C", REPO] + list(args),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV_GIT,
    )
    return proc


def zpaths(dados):
    return [p.decode("utf-8", "surrogateescape") for p in dados.split(b"\0") if p]


# --- guarda de não-vazamento: nenhuma mensagem pode carregar um trecho longo
# --- de conteúdo (uma linha de erro de parser poderia ecoar a linha fonte).
SEGREDO_LONGO = re.compile(r"[A-Za-z0-9_\-+/=.$~]{16,}")


def sanear(mensagem):
    limpo = SEGREDO_LONGO.sub("<omitido>", str(mensagem))
    return limpo.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def falha_interna(motivo):
    """Falha fechada por erro inesperado: nunca imprime traceback, nunca
    aprova por omissao e nunca emite saida invalida."""
    if MODO == "json":
        print(json.dumps({
            "gate": "verificar-proveniencia",
            "versao": "1",
            "repo": REPO,
            "sha_head": None,
            "sha_esperado": ESPERADO if SHA_INFORMADO else None,
            "resultado": "reprovado",
            "resultado_incompleto": True,
            "checagens": [{"id": "0", "nome": "erro-interno", "descricao": "o gate falhou antes de concluir",
                           "status": "nao-executada", "detalhe": motivo, "achados": 0}],
            "achados": [],
            "resumo": {"checagens_ok": 0, "checagens_falha": 0,
                       "checagens_nao_executadas": 1, "checagens_incompletas": 0, "achados": 0},
            "exit_code": 1,
        }, ensure_ascii=False, indent=2))
    else:
        print("GATE DE PROVENIENCIA (verificar-proveniencia)")
        print("repo: %s" % REPO)
        print("resultado: REPROVADO")
        print("resultado-incompleto: sim")
        print("")
        print("CHECAGENS")
        print("[nao-executada] 0 erro-interno — o gate falhou antes de concluir")
        print("                 detalhe: %s" % motivo)
        print("")
        print("TOTAIS")
        print("checagens-ok: 0")
        print("checagens-falha: 0")
        print("checagens-nao-executadas: 1")
        print("checagens-incompletas: 0")
        print("achados: 0")
        print("exit-code: 1")
    sys.exit(1)


def _excepthook(tipo, valor, tb):
    if issubclass(tipo, KeyboardInterrupt):
        sys.__excepthook__(tipo, valor, tb)
        return
    falha_interna("%s: %s" % (tipo.__name__, sanear(valor)))


sys.excepthook = _excepthook


# ================================================================== checagem 1/2
registrar("repo-valido", "ok", REPO)

faltando = []
if not shutil.which("git"):
    faltando.append("git")
if sys.version_info < (3, 6):
    faltando.append("python3>=3.6")
if faltando:
    registrar(
        "ferramentas",
        "nao-executada",
        "ferramenta obrigatoria ausente: " + ", ".join(faltando) + " (falha fechada, sem bypass)",
    )
else:
    registrar("ferramentas", "ok", "git e python3 disponiveis")

SEM_FERRAMENTAS = bool(faltando)

# --- tag de `git ls-files -v` que significa "arquivo cacheado, estado normal".
# --- Unica tag ACEITA pela checagem 6. Comparacao SENSIVEL AO CASO: o git emite
# --- 'H' (normal), 'h' minuscula (assume-unchanged) e 'S' (skip-worktree).
TAG_CACHEADO_NORMAL = "H"

# ================================================================== arquivos
rastreados = []
if not SEM_FERRAMENTAS:
    proc = git("ls-files", "-z")
    if proc.returncode != 0:
        registrar("ferramentas", "nao-executada", "git ls-files falhou: " + sanear(proc.stderr.decode("utf-8", "replace").strip()))
        SEM_FERRAMENTAS = True
    else:
        rastreados = zpaths(proc.stdout)

MODIFICADOS = []
NAO_RASTREADOS = []
OCULTOS = []
if not SEM_FERRAMENTAS:
    proc = git("diff", "--no-ext-diff", "--no-textconv", "--no-color",
               "--name-only", "-z", "HEAD")
    if proc.returncode != 0:
        registrar("ferramentas", "nao-executada", "git diff HEAD falhou: " + sanear(proc.stderr.decode("utf-8", "replace").strip()))
        SEM_FERRAMENTAS = True
    else:
        MODIFICADOS = sorted(set(zpaths(proc.stdout)))

if not SEM_FERRAMENTAS:
    proc = git("ls-files", "--others", "--exclude-standard", "-z")
    if proc.returncode != 0:
        registrar("ferramentas", "nao-executada", "git ls-files --others falhou: " + sanear(proc.stderr.decode("utf-8", "replace").strip()))
        SEM_FERRAMENTAS = True
    else:
        NAO_RASTREADOS = sorted(set(zpaths(proc.stdout)))

if not SEM_FERRAMENTAS:
    proc = git("ls-files", "-v", "-z")
    if proc.returncode != 0:
        registrar("ferramentas", "nao-executada", "git ls-files -v falhou: " + sanear(proc.stderr.decode("utf-8", "replace").strip()))
        SEM_FERRAMENTAS = True
    else:
        for item in zpaths(proc.stdout):
            tag, _, caminho = item.partition(" ")
            if not caminho:
                continue
            # REGRA SENSIVEL AO CASO — NAO usar upper()/lower() aqui.
            # `git ls-files -v` (medido em git 2.53.0): 'H' arquivo cacheado
            # normal (flags 0x0), 'h' minuscula = assume-unchanged (flags
            # 0x8000), 'S' = skip-worktree (flags 0x4000) e 's' minuscula =
            # as DUAS flags no indice (flags 0xc000). Aplicar tag.upper()
            # transforma 'h' em 'H' e o gate passa a APROVAR (exit 0) um
            # repositorio cujo arquivo rastreado foi alterado sob
            # assume-unchanged — exatamente o bypass que esta checagem existe
            # para fechar. A unica tag aceita e 'H' exato.
            #
            # A deteccao vem dos BITS DO INDICE, nunca de `git status` nem de
            # `git diff`: sob assume-unchanged/skip-worktree os dois NAO veem a
            # alteracao, logo confiar neles seria burla e nao checagem. Por isso
            # a checagem falha fechada na simples presenca da flag, exista ou
            # nao divergencia de conteudo.
            if tag != TAG_CACHEADO_NORMAL:
                OCULTOS.append((tag, caminho))

MODIFICADOS = sorted(set(MODIFICADOS))

HEAD = None
if not SEM_FERRAMENTAS:
    proc = git("rev-parse", "--verify", "HEAD")
    if proc.returncode != 0 or not proc.stdout.strip():
        registrar("sha-release", "falha", "HEAD nao pode ser resolvido (repositorio sem commit?)")
    else:
        HEAD = proc.stdout.decode("ascii", "replace").strip()

# ================================================================== 3. sha
if not SEM_FERRAMENTAS and HEAD is not None:
    if not SHA_INFORMADO:
        registrar("sha-release", "incompleto",
                  "--expected-sha nao informado: checagem de SHA nao solicitada, resultado incompleto")
    elif HEAD.lower() == ESPERADO.lower():
        registrar("sha-release", "ok", "HEAD igual ao SHA de release esperado")
    else:
        registrar("sha-release", "falha", "HEAD divergente do SHA de release esperado")
        achado("sha-release", ".", None, "sha-divergente",
               "HEAD " + (HEAD or "?") + " != esperado " + ESPERADO)

# ================================================================== 4. arvore
if SEM_FERRAMENTAS:
    pass
elif MODIFICADOS:
    registrar("arvore-limpa", "falha", "%d arquivo(s) rastreado(s) modificado(s)/removido(s)/renomeado(s)" % len(MODIFICADOS))
    for caminho in MODIFICADOS:
        achado("arvore-limpa", caminho, None, "rastreado-modificado",
               "arquivo rastreado difere de HEAD")
else:
    # nota de honestidade: sob assume-unchanged/skip-worktree o `git diff HEAD`
    # NAO enxerga a alteracao do arquivo, entao este "ok" sozinho nao prova
    # arvore limpa quando a checagem 6 falha.
    nota_cega = (" (porem ha estado especial no indice: git diff NAO ve alteracao sob "
                 "assume-unchanged/skip-worktree, ver checagem 6)") if OCULTOS else ""
    registrar("arvore-limpa", "ok",
              "nenhum arquivo rastreado modificado, removido ou renomeado" + nota_cega)

# ================================================================== 5. untracked
if SEM_FERRAMENTAS:
    pass
elif NAO_RASTREADOS:
    registrar("sem-untracked", "falha", "%d arquivo(s) nao rastreado(s) presente(s)" % len(NAO_RASTREADOS))
    for caminho in NAO_RASTREADOS:
        achado("sem-untracked", caminho, None, "nao-rastreado",
               "arquivo nao rastreado: reprova o release por si so")
else:
    registrar("sem-untracked", "ok", "nenhum arquivo nao rastreado")

# ================================================================== 6. ocultacao
def mecanismo_indice(tag):
    """Mecanismo por trás de uma tag de `git ls-files -v`, com a distinção de
    maiúsculas/minúsculas preservada: 'h' é assume-unchanged, 'S' é
    skip-worktree e 's' são as duas. Devolve apenas rótulo: nunca
    conteúdo de arquivo."""
    if tag == "h":
        return "assume-unchanged"
    if tag == "S":
        return "skip-worktree"
    if tag == "s":
        return "skip-worktree+assume-unchanged"
    return "estado especial do indice"


if SEM_FERRAMENTAS:
    pass
elif OCULTOS:
    mecanismos = sorted(set(mecanismo_indice(tag) for tag, _ in OCULTOS))
    registrar("sem-ocultacao", "falha",
              "%d arquivo(s) com estado especial no indice (%s): esconde alteracao de "
              "arquivo rastreado de git status e de git diff" % (len(OCULTOS), ", ".join(mecanismos)))
    for tag, caminho in sorted(OCULTOS, key=lambda par: (par[1], par[0])):
        achado("sem-ocultacao", caminho, None, "indice-oculto",
               "%s: tag git ls-files -v = %s" % (mecanismo_indice(tag), tag))
else:
    registrar("sem-ocultacao", "ok", "nenhum assume-unchanged nem skip-worktree")

# ================================================================== leitura de conteudo
LIMITE_ENTRADA = 8 * 1024 * 1024


def caminho_absoluto(rel):
    return os.path.join(REPO, rel)


def dentro_do_repo(rel):
    base = os.path.realpath(REPO)
    alvo = os.path.realpath(caminho_absoluto(rel))
    return alvo == base or alvo.startswith(base + os.sep)


def ler(rel):
    """devolve (bytes|None, motivo) — nunca levanta excecao para o gate."""
    p = caminho_absoluto(rel)
    try:
        st = os.lstat(p)
    except OSError as exc:
        return None, "ilegivel: " + sanear(exc.strerror or exc)
    if os.path.islink(p) or not os.path.isfile(p):
        return None, "ignorado: nao e arquivo regular (symlink/ especial)"
    if not dentro_do_repo(rel):
        return None, "ignorado: resolve para fora do repositorio"
    if st.st_size > LIMITE_ENTRADA:
        return None, "ignorado: acima do limite de %d bytes" % LIMITE_ENTRADA
    try:
        with open(p, "rb") as fh:
            return fh.read(), ""
    except OSError as exc:
        return None, "ilegivel: " + sanear(exc.strerror or exc)


# --- 7. marcadores de conflito
CONFLITOS = (
    ("conflict-marker-inicio", re.compile(r"^<{7}")),
    ("conflict-marker-fim", re.compile(r"^>{7}")),
    ("conflict-marker-separador", re.compile(r"^={7,}$")),
)

# --- 8. segredos aparentes
REGRAS_ESPECIFICAS = (
    ("segredo-chave-privada", re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----")),
    ("segredo-aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("segredo-github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("segredo-slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("segredo-stripe-live", re.compile(r"\b(?:sk|rk)[-_](?:live|test)[-_][0-9A-Za-z]{10,}")),
    ("segredo-google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("segredo-slack-webhook", re.compile(r"https://hooks\.slack\.com/services/[A-Za-z0-9/+]{20,}")),
)
# nome de chave com prefixo opcional (API_TOKEN, DJANGO_SECRET_KEY, AWS_SECRET_ACCESS_KEY...).
CHAVE_GENERICA = re.compile(
    rb"(?i)(?<![A-Za-z0-9])(?:[A-Za-z0-9]+[_-])*(?:api[_-]?key|apikey|secret[_-]?key|secret|senha"
    rb"|password|passwd|passphrase|private[_-]?key|access[_-]?key|token)\b[\"']?[ \t]*[:=][ \t]*"
    rb"[\"']([^\"'\n]{6,})[\"']"
)
PLACEHOLDER = re.compile(
    rb"(?i)(example|placeholder|changeme|change-me|change_me|your[-_ ]?|senha|passw"
    rb"|<[^>]+>|x{3,}|\*{3,}|todo|fixme|django-insecure|not-a-real|fake|dummy"
    rb"|sample|redact|\bnone\b|\bnull\b|os\.environ|env\(|\$\(|\{|\}|replacedby"
    rb"|acme|teste|localhost)"
)


def valor_plausivel(valor):
    """Filtro explícito contra falso positivo que tornaria o gate inutil.
    Mantem valor longo e de forma*s* de segredo (4 classes de caractere, ou
    >=32 caracteres com 3 classes). Valor nunca e devolvido ao chamador."""
    if PLACEHOLDER.search(valor):
        return False
    if len(valor) < 16:
        return False
    if re.search(rb"\s", valor):
        return False
    classes = 0
    if re.search(rb"[a-z]", valor):
        classes += 1
    if re.search(rb"[A-Z]", valor):
        classes += 1
    if re.search(rb"[0-9]", valor):
        classes += 1
    if re.search(rb"[^A-Za-z0-9]", valor):
        classes += 1
    return classes == 4 or (len(valor) >= 32 and classes >= 3)


def binario(dados):
    return b"\0" in dados[:65536]


# ================================================================== varredura
conflitos = 0
segredos = 0
descartados_placeholder = 0
ignorados_leitura = 0
erro_parse = False
erro_yaml = False
sem_pyyaml = False

try:
    import yaml  # noqa: F401
except Exception:
    sem_pyyaml = True

if not SEM_FERRAMENTAS:
    import ast

    for rel in sorted(rastreados):
        dados, motivo = ler(rel)
        if dados is None:
            if motivo.startswith("ilegivel"):
                erro_parse = True
                achado("python-valido", rel, None, "arquivo-ilegivel", motivo)
            else:
                ignorados_leitura += 1
            continue

        # --- 7 e 8: só em arquivo textual rastreado
        if not binario(dados):
            try:
                texto = dados.decode("utf-8")
            except UnicodeDecodeError:
                texto = None
            if texto is not None:
                for numero, linha in enumerate(texto.splitlines(), 1):
                    achou_especifica = False
                    for regra, padrao in CONFLITOS:
                        if padrao.search(linha):
                            conflitos += 1
                            achado("sem-conflito", rel, numero, regra,
                                   "marcador de conflito de merge")
                    for regra, padrao in REGRAS_ESPECIFICAS:
                        if padrao.search(linha):
                            achou_especifica = True
                            segredos += 1
                            achado("sem-segredos", rel, numero, regra,
                                   "padrao de segredo reconhecido; valor omitido")
                    if achou_especifica:
                        # regra especifica ja descreve o achado: nao duplica
                        # achado generico na mesma linha (determinismo)
                        continue
                    for achado_generico in CHAVE_GENERICA.finditer(linha.encode("utf-8", "replace")):
                        if valor_plausivel(achado_generico.group(1)):
                            segredos += 1
                            achado("sem-segredos", rel, numero, "segredo-chave-valor-literal",
                                   "chave/token com valor literal; valor omitido")
                        else:
                            descartados_placeholder += 1

        # --- 9: .py rastreado tem de fazer parse
        if rel.endswith(".py"):
            try:
                ast.parse(dados)
            except SyntaxError as exc:
                erro_parse = True
                achado("python-valido", rel, exc.lineno, "python-syntax-error",
                       "SyntaxError: " + sanear(exc.msg) + " (linha " + str(exc.lineno) + ")")
            except Exception as exc:
                erro_parse = True
                achado("python-valido", rel, None, "python-parse-error",
                       sanear(type(exc).__name__ + ": " + str(exc)))

# ================================================================== 7. status
if SEM_FERRAMENTAS:
    registrar("sem-conflito", "nao-executada", "checagem de conteudo nao executada (falha fechada)")
    registrar("sem-segredos", "nao-executada", "checagem de conteudo nao executada (falha fechada)")
    registrar("python-valido", "nao-executada", "checagem de conteudo nao executada (falha fechada)")
    registrar("yaml-valido", "nao-executada", "checagem de conteudo nao executada (falha fechada)")
else:
    registrar("sem-conflito", "falha" if conflitos else "ok",
              "%d marcador(es) de conflito" % conflitos if conflitos else "nenhum marcador de conflito")
    detalhe_segredo = "%d achado(s) de segredo aparente (valor nunca exibido)" % segredos
    if descartados_placeholder:
        detalhe_segredo += "; %d candidato(s) descartado(s) pelo filtro de placeholder" % descartados_placeholder
    registrar("sem-segredos", "falha" if segredos else "ok", detalhe_segredo)
    registrar("python-valido", "falha" if erro_parse else "ok",
              "arquivo .py rastreado nao faz parse" if erro_parse else "todo .py rastreado faz parse")

    # ================================================================== 10. yaml
    arquivos_yaml = [r for r in sorted(rastreados) if r.endswith(".yml") or r.endswith(".yaml")]
    if not arquivos_yaml:
        registrar("yaml-valido", "ok", "nenhum arquivo .yml/.yaml rastreado (escopo vazio)")
    elif sem_pyyaml:
        erro_yaml = True
        registrar("yaml-valido", "nao-executada",
                  "PyYAML ausente e ha %d arquivo(s) .yml/.yaml rastreado(s): falha fechada, sem fallback" % len(arquivos_yaml))
    else:
        for rel in arquivos_yaml:
            dados, motivo = ler(rel)
            if dados is None:
                erro_yaml = True
                achado("yaml-valido", rel, None, "arquivo-ilegivel", motivo)
                continue
            try:
                texto = dados.decode("utf-8")
            except UnicodeDecodeError as exc:
                erro_yaml = True
                achado("yaml-valido", rel, None, "yaml-encoding-error", sanear(str(exc)))
                continue
            try:
                list(yaml.safe_load_all(texto))
            except yaml.YAMLError as exc:
                erro_yaml = True
                linha = None
                try:
                    if getattr(exc, "problem_mark", None) is not None:
                        linha = exc.problem_mark.line + 1
                except Exception:
                    linha = None
                problema = sanear(getattr(exc, "problem", None) or type(exc).__name__)
                achado("yaml-valido", rel, linha, "yaml-parse-error", problema)
            except Exception as exc:
                erro_yaml = True
                achado("yaml-valido", rel, None, "yaml-parse-error",
                       sanear(type(exc).__name__ + ": " + str(exc)))
        registrar("yaml-valido", "falha" if erro_yaml else "ok",
                  "arquivo .yml/.yaml rastreado nao faz parse" if erro_yaml
                  else "%d arquivo(s) .yml/.yaml validado(s)" % len(arquivos_yaml))

if SEM_FERRAMENTAS:
    for nome in ("sha-release", "arvore-limpa", "sem-untracked", "sem-ocultacao"):
        if nome not in estado:
            registrar(nome, "nao-executada", "checagem nao executada (falha fechada)")

# ================================================================== resultado
falhas = [c for c in CHECAGENS if estado[c[1]]["status"] == "falha"]
nao_executadas = [c for c in CHECAGENS if estado[c[1]]["status"] == "nao-executada"]
incompletas = [c for c in CHECAGENS if estado[c[1]]["status"] == "incompleto"]
incompleto = bool(nao_executadas or incompletas)

if falhas or incompleto:
    resultado = "incompleto" if (incompleto and not falhas) else "reprovado"
    codigo = 1
else:
    resultado = "aprovado"
    codigo = 0

achados.sort(key=lambda a: (int(a["id"]), a["caminho"], a["linha"] if a["linha"] is not None else -1, a["regra"]))

resumo = {
    "checagens_ok": len(CHECAGENS) - len(falhas) - len(nao_executadas) - len(incompletas),
    "checagens_falha": len(falhas),
    "checagens_nao_executadas": len(nao_executadas),
    "checagens_incompletas": len(incompletas),
    "achados": len(achados),
}

if MODO == "json":
    saida = {
        "gate": "verificar-proveniencia",
        "versao": "1",
        "repo": REPO,
        "sha_head": HEAD,
        "sha_esperado": ESPERADO if SHA_INFORMADO else None,
        "resultado": resultado,
        "resultado_incompleto": incompleto,
        "checagens": [
            {
                "id": ident,
                "nome": nome,
                "descricao": descricao,
                "status": estado[nome]["status"],
                "detalhe": estado[nome]["detalhe"],
                "achados": sum(1 for a in achados if a["checagem"] == nome),
            }
            for ident, nome, descricao in CHECAGENS
        ],
        "achados": achados,
        "resumo": resumo,
        "exit_code": codigo,
    }
    print(json.dumps(saida, ensure_ascii=False, indent=2, sort_keys=False))
else:
    print("GATE DE PROVENIENCIA (verificar-proveniencia)")
    print("repo: %s" % REPO)
    print("head: %s" % (HEAD or "(indisponivel)"))
    print("sha-esperado: %s" % (ESPERADO if SHA_INFORMADO else "nao informado"))
    print("resultado: %s" % resultado.upper())
    print("resultado-incompleto: %s" % ("sim" if incompleto else "nao"))
    print("")
    print("CHECAGENS")
    for ident, nome, descricao in CHECAGENS:
        info = estado[nome]
        print("[%-14s] %s %s — %s" % (info["status"], ident, nome, descricao))
        if info["detalhe"]:
            print("                 detalhe: %s" % info["detalhe"])
    print("")
    print("ACHADOS (ordem: checagem, caminho, linha, regra)")
    for a in achados:
        local = a["caminho"] if a["linha"] is None else "%s:%d" % (a["caminho"], a["linha"])
        print("[%s %s] %s :: %s :: %s" % (a["id"], a["checagem"], local, a["regra"], a["mensagem"]))
    if not achados:
        print("(nenhum)")
    print("")
    print("TOTAIS")
    print("checagens-ok: %d" % resumo["checagens_ok"])
    print("checagens-falha: %d" % resumo["checagens_falha"])
    print("checagens-nao-executadas: %d" % resumo["checagens_nao_executadas"])
    print("checagens-incompletas: %d" % resumo["checagens_incompletas"])
    print("achados: %d" % resumo["achados"])
    print("exit-code: %d" % codigo)

sys.exit(codigo)
PY
exit $?
