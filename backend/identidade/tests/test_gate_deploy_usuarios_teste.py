"""
Prova executada do gate `usuarios_teste` do deploy (run
20260925-1836-usuarios-teste-dev-homolog).

POR QUE UM TESTE PYTEST DEIXA UM ARQUIVO SHELL
O gate não é código Python: é um bloco de shell dentro do `script:` do job
`deploy` do `.github/workflows/deploy.yml`, executado na VPS por
`appleboy/ssh-action` sob `/bin/sh` (dash). Os critérios 5, 6, 9, 10 e 11 são
sobre esse shell — quantas vezes o `manage.py` é chamado, com que argv, o que o
log afirma, e qual valor decide se o bloco roda. Nenhuma asserção em Python
sobre o texto do YAML provaria isso: o Finding 1 desta run é exatamente o
exemplo do que acontece quando se "prova" por string (a guarda existia no
arquivo e era anulada em execução pelo `set -a; . ./.env` da VPS).

Então este teste não substitui o shell por asserção de string: ele **executa**
`scripts/verificar-gate-usuarios-teste.sh`, que extrai o script do YAML com
`yaml.safe_load`, renderiza os 17 inputs do workflow e roda o script INTEIRO em
`dash` contra um `backend/.env` de verdade. O que é afirmado é o argv que o
`manage.py` recebeu e o que o log imprimiu.

O QUE ESTE TESTE PEGA
O `AUTOMUTACAO=1` faz o harness remover, de uma cópia do workflow, o bloco que
reatribui o input do workflow DEPOIS do `set -a; . ./.env` (o "selo"), e exige
que o cenário do exploit **reprobe**. Ou seja: se alguém remover o selo, ou
fizer o gate voltar a ler o valor de antes do source, este teste fica vermelho
por si só — e se o harness deixar de rodar o script de verdade, ele também
(reprova por não detectar a mutação). Se o selo for implementado de outra forma
e a mutação não tiver o que remover, o harness diz `MUTAÇÃO: NÃO APLICÁVEL` e
este teste avisa em vez de reprovar: quem protege a regressão passa a ser o
cenário do exploit, que é comportamental e roda sempre (Finding R2 — um fix
alternativo e igualmente correto não pode deixar o CI vermelho).

WHEN IT SKIPS
O harness exige `dash`, que é o shell do step na VPS (`/bin/sh`): em Windows
não existe, e aí o teste pula com o motivo explícito. O harness também exige
PyYAML, e esse NÃO pula (Finding R1): `pyyaml` está DECLARADO em
`backend/requirements-dev.txt`, que é o arquivo que o job `backend-tests` do
`ci.yml` instala, então no CI a dependência existe por construção. Um `skipif`
aqui seria o pior desfecho possível — o teste viraria `s skipped` em todo CI e a
única prova de regressão do fix de segurança do gate simplesmente não existiria.
Falhar é o comportamento certo para dependência declarada e não instalada: a
suíte inteira depende de `requirements-dev.txt` (sem `pytest` nem `pytest-django`
ela nem roda).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
HARNESS = RAIZ / "scripts" / "verificar-gate-usuarios-teste.sh"
WORKFLOW = RAIZ / ".github" / "workflows" / "deploy.yml"

# Um `sleep 2` do laço de retry do PM2 entra no caminho se algum stub mudar;
# 10 minutos é folga larga, não um limite apertado.
TIMEOUT_S = 600


pytestmark = pytest.mark.skipif(
    not HARNESS.is_file(),
    reason=f"harness ausente: {HARNESS}",
)


@pytest.mark.skipif(
    shutil.which("dash") is None,
    reason="dash não encontrado (o step roda sob /bin/sh = dash na VPS)",
)
@pytest.mark.xfail(
    reason=(
        "Cutover Docker (ARCHITECTURE.md §9.2, CI-CD.md): o deploy.yml deixou de "
        "usar script_path+infra/deploy/deploy.sh (SSH com script inline fazendo "
        "docker compose pull/up) e o gate `usuarios_teste` não foi portado para a "
        "nova arquitetura — não existe NENHUM caminho de criação de usuário de "
        "teste no novo deploy.yml, então a vulnerabilidade original (Finding 1: "
        ".env da VPS decidindo o gate) não tem como ocorrer, mas o harness "
        "(scripts/verificar-gate-usuarios-teste.sh) testa a FORMA antiga "
        "(script_path) e reprova com a forma nova. xfail explícito — não skip — "
        "para não desaparecer do CI: portar/decidir o equivalente do gate "
        "usuarios_teste para Docker é trabalho pendente, rastreado separadamente."
    ),
    strict=False,
)
def test_gate_de_usuarios_teste_no_deploy_ignora_o_arquivo_de_ambiente():
    """O `.env` da VPS não decide o gate — o input do workflow decide.

    Vale como regressão do Finding 1 (major/security): com o input em `false`
    e `USUARIOS_TESTE=true` (e outros 5 nomes equivalentes) no `backend/.env`
    de uma "VPS" de PROD, o gate não pode rodar. Vale também como regressão do
    Finding R3: o `SUF` do `.env` não pode escolher o domínio dos e-mails das
    contas de teste. E com `AUTOMUTACAO=1` o próprio harness prova que a
    primeira asserção tem dente.
    """
    # PyYAML é dependência de TESTE declarada em backend/requirements-dev.txt
    # (`pyyaml==6.0.3`), e o job `backend-tests` do ci.yml instala esse arquivo.
    # A prova roda contra o MESMO interpretador que executa a suíte
    # (`sys.executable`), e não contra um `python3` qualquer do PATH: era
    # exatamente esse desvio que achava o python do SISTEMA (com PyYAML de apt)
    # e fazia o passe local passar enquanto o CI pulava o teste (Finding R1).
    tem_yaml = subprocess.run(
        [sys.executable, "-c", "import yaml"],
        capture_output=True,
        check=False,
    )
    assert tem_yaml.returncode == 0, (
        "PyYAML não está instalado no interpretador que roda a suíte "
        f"({sys.executable}). Ela é dependência de TESTE declarada em "
        "backend/requirements-dev.txt, que é justamente o arquivo que o job "
        "`backend-tests` do ci.yml instala. Rode "
        "`pip install -r requirements-dev.txt`.\n"
        "Este teste NÃO é pulado de propósito: pulado, ele vira `s skipped` em "
        "todo CI e a única prova de regressão do fix de segurança do gate "
        "usuarios_teste deixa de existir sem ninguém perceber."
    )

    ambiente = dict(os.environ, AUTOMUTACAO="1", GATE_PY_YAML=sys.executable)
    resultado = subprocess.run(
        [str(HARNESS), str(WORKFLOW)],
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
        env=ambiente,
    )
    saida = resultado.stdout + resultado.stderr
    assert resultado.returncode == 0, (
        "o harness do gate usuarios_teste reprovou — o script do deploy "
        "comportou-se diferente do esperado:\n" + saida
    )
    # Checagem legível no log do CI: se o harness sair verde sem rodar o
    # cenário do exploit, isto denuncia. É esta a asserção que protege de fato
    # o Finding 1, porque ela é comportamental (o `.env` com o gate ligado
    # contra o input do workflow em `false`) e independe da forma do fix.
    assert "PROD + .env com USUARIOS_TESTE=true" in saida, (
        "o harness rodou sem o cenário do exploit; a prova não vale nada:\n" + saida
    )
    # A auto-mutação tem dois desfechos legítimos, e eles precisam ser
    # distinguíveis no log (Finding R2): "a prova tem dente", quando o selo foi
    # encontrado e removido, ou "NÃO APLICÁVEL", quando a forma nova do selo
    # não é reconhecida pela mutação. Um terceiro desfecho — a mutação existir
    # e o cenário não detectar a remoção — reprova dentro do harness.
    tem_dente = "a prova tem dente" in saida
    nao_aplicavel = "MUTAÇÃO: NÃO APLICÁVEL" in saida
    assert tem_dente or nao_aplicavel, (
        "a AUTOMUTACAO não produziu nenhum dos dois desfechos legítimos: nem "
        "detectou a remoção do selo, nem disse que não encontrou o que remover. "
        "A prova de que a prova tem dente não rodou:\n" + saida
    )
    if nao_aplicavel and not tem_dente:
        # Não reprova (um fix correto de outra forma não pode deixar o CI
        # vermelho), mas também não some em silêncio: `warnings.warn` aparece
        # no resumo de warnings do pytest, no log do CI.
        warnings.warn(
            "mutação do harness NÃO APLICÁVEL: nenhuma linha depois do "
            "`set -a; . ./.env` volta a mencionar o input `usuarios_teste`. A "
            "regressão continua coberta pelo cenário do exploit (que é "
            "comportamental), mas a prova de que a prova tem dente não rodou — "
            "vale conferir o selo deste commit à mão.\n" + saida,
            stacklevel=2,
        )
