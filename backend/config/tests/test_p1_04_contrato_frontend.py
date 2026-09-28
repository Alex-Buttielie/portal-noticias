"""
CONTRATO FRONTEND x BACKEND — o tipo declarado tem que ser o tipo real
========================================================================

O QUE ESTE ARQUIVO PROVA
=======================
Para o endpoint `POST /api/auth/cadastro/`, os campos que
`frontend/lib/api.ts` PROMETE no tipo de retorno existem de fato na
resposta que o backend devolve — e nenhum campo sobra do lado de lá.

A propriedade nasce de um defeito concreto. `frontend/lib/api.ts`
declarava `Promise<{ detail: string; usuario: Usuario }>`, mas o backend
(P1-04) parou de devolver `usuario`: o campo carregava `id`, `papel` e
`email_verificado` da conta, que são oráculos de existência de conta. Como
`request<T>` devolve `corpo as T` — uma afirmação, não uma verificação — o
TypeScript não podia reclamar. O único consumidor
(`frontend/app/cadastro/page.tsx`) descartava o resultado, então o bug era
invisível em runtime E invisível para o `tsc`. O primeiro código que lesse
`.usuario` receberia `undefined` com o compilador calado.

Por que isto é uma GUARDA e não uma conferência de hoje
========================================================
Os campos declarados são extraídos MECANICAMENTE do fonte TypeScript, por
parsing, dentro deste teste. Não há mapa escrito à mão, não há lista
mantida por alguém, e não há constante neste arquivo que alguém possa
ajustar para o teste passar.

E o teste falha ALTO se a extração não encontrar o que procura. Uma guarda
que, quando o fonte muda de forma, deixa de checar e continua verde é
pior do que não ter guarda — ela anuncia uma cobertura que não existe.
Por isso a asserção é sobre a EXTRAÇÃO ter funcionado, não só sobre o
resultado.

ESCOPO — LEIA ANTES DE CONFIAR NESTA COBERTURA
==============================================
Isto fecha o caso do CADASTRO, que é o defeito encontrado. NÃO fecha a
classe do problema: `frontend/lib/api.ts` tem ~103 tipos de resposta e
todos passam pelo mesmo `return corpo as T`. Nenhum deles é verificado em
runtime. Fechar a classe exigiria validação em runtime de todos os
formatos (uma biblioteca de schema, que exige mexer em
`frontend/package.json` — fora do escopo deste lote) ou geração de contrato
a partir dos serializers, o que é um trabalho de Onda própria.

O que ESTE arquivo faz, então, é tornar o mecanismo visível e prender o
caso concreto: se alguém reintroduzir um campo no tipo sem o backend
mandá-lo, a suíte reprova.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from config.tests.backends import EntregaSimuladaBackend, caminho_de

pytestmark = pytest.mark.django_db

#: `frontend/lib/api.ts` a partir de `backend/config/tests/` -> repo root.
RAIZ = Path(__file__).resolve().parents[3]
FONTE_API = RAIZ / "frontend" / "lib" / "api.ts"

URL_CADASTRO = "/api/auth/cadastro/"

#: O cadastro só responde 201 depois de ENTREGAR o e-mail (P1-04), e o
#: `locmem` que o pytest-django injeta está em `BACKENDS_SEM_ENTREGA_REAL`.
#: Sem um backend que entrega de verdade, o endpoint responde 503 e o corpo
#: que chegaríamos a comparar seria o de "sem canal" — o teste passaria
#: comparando o contrato errado.
BACKEND_QUE_ENTREGA = caminho_de(EntregaSimuladaBackend)


# ---------------------------------------------------------------------------
# Extração mecânica do tipo declarado
# ---------------------------------------------------------------------------
def _segmentar_membros(corpo: str) -> list[str]:
    """
    Divide o corpo de um `{...}` de TypeScript nos membros de NÍVEL DE
    TOPO, respeitando objetos, arrays e literais aninhados.

    Por que isto precisa existir: a versão anterior acumulava o corpo
    inteiro e cortava no primeiro ":", o que fazia o extrator devolver
    SEMPRE só o primeiro campo. A guarda do D2 então verificava menos do
    que afirmava verificar — e, se `usuario` estivesse em segunda posição,
    ela não veria nada. Foi o teste de poder discriminante que pegou
    isso, revertendo o tipo com dois campos e vendo a guarda passar.
    """
    # `corpo` chega como `{...}` completo. As chaves do objeto de TOPO nao
    # sao membro: sao o container. Por isso `atual` comeca vazio e a
    # abertura de nivel 0 nao e acumulada — a versao que acumulava produzia
    # o membro "{ detail: string }" inteiro, que depois nao casava com o
    # nome de campo e o extrator devolvia vazio.
    membros: list[str] = []
    atual: list[str] = []
    profundidade = 0
    dentro_de_string: str | None = None

    for caractere in corpo:
        if dentro_de_string is not None:
            atual.append(caractere)
            if caractere == dentro_de_string:
                dentro_de_string = None
            continue
        if caractere in "\"'`":
            dentro_de_string = caractere
            atual.append(caractere)
            continue
        if caractere in "{[(":
            if profundidade == 0:
                # Abertura do objeto de topo: container, nao membro.
                profundidade = 1
                atual = []
            else:
                profundidade += 1
                atual.append(caractere)
            continue
        if caractere in "}])":
            profundidade -= 1
            if profundidade <= 0:
                profundidade = 0
                if "".join(atual).strip():
                    membros.append("".join(atual))
                atual = []
                continue
            atual.append(caractere)
            continue
        if caractere == ";" and profundidade == 1:
            if "".join(atual).strip():
                membros.append("".join(atual))
            atual = []
            continue
        atual.append(caractere)

    if "".join(atual).strip():
        membros.append("".join(atual))
    return membros


def _campos_declarados_de_cadastro() -> set[str]:
    """
    Lê `frontend/lib/api.ts` e devolve o conjunto de campos que o tipo de
    retorno de `cadastrar()` PROMETE.

    Reconhece as duas formas que o arquivo usa para esse retorno: uma
    interface nomeada (`Promise<CadastroResposta>`) e um objeto literal
    inline (`Promise<{ detail: string }>`). A forma nomeada é resolvida
    seguindo a declaração da interface no mesmo arquivo.
    """
    fonte = FONTE_API.read_text(encoding="utf-8")

    assinatura = re.search(
        r"export\s+function\s+cadastrar\s*\(.*?\)\s*:\s*Promise<(?P<alvo>.+?)>\s*\{",
        fonte,
        re.DOTALL,
    )
    assert assinatura is not None, (
        "não encontrei a assinatura de `cadastrar()` em frontend/lib/api.ts. "
        "A forma da declaração mudou e ESTE TESTO PAROU DE CHECAR — "
        "atualize a extração em vez de deixar a guarda silenciosa."
    )
    alvo = assinatura.group("alvo").strip()

    if alvo.startswith("{"):
        corpo = alvo
    else:
        interface = re.search(
            r"export\s+(?:interface|type)\s+" + re.escape(alvo) + r"\s*=?\s*\{(.*?)\n\}",
            fonte,
            re.DOTALL,
        )
        assert interface is not None, (
            f"o tipo `{alvo}` declarado por `cadastrar()` não foi encontrado em "
            "frontend/lib/api.ts. ESTE TESTO PAROU DE CHECAR."
        )
        corpo = "{" + interface.group(1) + "\n}"

    campos: set[str] = set()
    for membro in _segmentar_membros(corpo):
        if ":" not in membro:
            continue
        nome = membro.split(":", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome):
            campos.add(nome)
    return campos


# ---------------------------------------------------------------------------
# AUTOTESTE DO EXTRATOR — a lacuna que deixou o defeito passar
# ---------------------------------------------------------------------------
class TestExtratorDoContrato:
    """
    O extrator é a parte deste arquivo que pode falhar em SILÊNCIO: se a
    segmentação voltar errada, a comparação com a resposta do backend
    compara conjuntos errados e pode passar.

    Estes casos existem porque a primeira versão do extrator devolvia
    sempre só o primeiro campo — e nenhuma asserção sobre o contrato
    reclamou, porque o resto do arquivo continuava funcionando.
    """

    def test_um_campo(self):
        assert _campos_de("{ detail: string }") == {"detail"}

    def test_dois_campos(self):
        """O caso que a primeira versão ERROU: o segundo campo sumia."""
        assert _campos_de("{ detail: string; usuario: Usuario }") == {"detail", "usuario"}

    def test_tres_campos(self):
        corpo = "{ detail: string; usuario: Usuario; perfil: Perfil }"
        assert _campos_de(corpo) == {"detail", "usuario", "perfil"}

    def test_campos_aninhados_nao_viram_campo_de_topo(self):
        corpo = (
            "{ detail: string; itens: { termo: string; total: number }[]; "
            "outros: { a: number } }"
        )
        assert _campos_de(corpo) == {"detail", "itens", "outros"}

    def test_string_com_ponto_e_virgula_nao_quebra(self):
        corpo = '{ detail: "a;b{c}"; outro: string }'
        assert _campos_de(corpo) == {"detail", "outro"}

    def test_tipo_generico_com_virgula(self):
        corpo = "{ valores: Record<string, number>; detail: string }"
        assert _campos_de(corpo) == {"valores", "detail"}

    def test_campo_sem_tipo_e_ignorado(self):
        assert _campos_de("{ detail; outro: string }") == {"outro"}


def _campos_de(corpo: str) -> set[str]:
    """Atalho dos autotestes: aplica a mesma segmentação do contrato."""
    campos: set[str] = set()
    for membro in _segmentar_membros(corpo):
        if ":" not in membro:
            continue
        nome = membro.split(":", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nome):
            campos.add(nome)
    return campos


# ---------------------------------------------------------------------------
# A garantia
# ---------------------------------------------------------------------------
def test_o_tipo_declarado_de_cadastro_e_extraido_e_nao_vazio():
    """
    A guarda sobre a própria guarda.

    Sem isto, um dia em que a extração deixar de achar o tipo faria o teste
    de cima passar por vacuidade — e o "verde" passaria a anunciar uma
    cobertura que não existe. Este teste falha alto em vez disso.
    """
    campos = _campos_declarados_de_cadastro()
    assert campos, "a extração devolveu vazio: a guarda não está checando nada"
    assert campos == {"detail"}, (
        "o tipo de retorno de `cadastrar()` voltou a declarar campos além de "
        f"`detail`: {sorted(campos)}. O backend (P1-04) só envia `detail` — "
        "qualquer campo a mais é um oráculo de existência de conta."
    )


@override_settings(EMAIL_BACKEND=BACKEND_QUE_ENTREGA)
def test_o_tipo_declarado_bate_com_a_resposta_real_do_backend():
    """
    O contrato, dos dois lados: o que o TypeScript promete é o que o HTTP
    devolve. Comparação nos DOIS sentidos — um campo prometido que não vem
    (o defeito original) e um campo que vem e não é prometido (a forma
    inversa, que esconderia dado novo).
    """
    declarados = _campos_declarados_de_cadastro()
    assert declarados, "extração vazia: a guarda não checa nada"

    client = APIClient()
    resposta = client.post(
        URL_CADASTRO,
        data={
            "email": "contrato@example.com",
            "senha": "senha123456",
            "nome": "Contrato",
            "aceite_termos": True,
        },
        format="json",
    )

    assert resposta.status_code == 201, resposta.content
    corpo = resposta.json()
    assert isinstance(corpo, dict), f"a resposta não é um objeto: {corpo!r}"

    so_na_frente = declarados - set(corpo)
    assert not so_na_frente, (
        f"o frontend promete {sorted(so_na_frente)} e o backend NÃO devolve. "
        "É a armadilha do `request<T>`: `corpo as T` afirma o tipo sem "
        "verificar, então o `.campo` devolvia `undefined` em runtime com o "
        "TypeScript calado."
    )

    sobra = set(corpo) - declarados
    assert not sobra, (
        f"o backend devolve {sorted(sobra)} e o tipo do frontend não declara. "
        "Dado não declarado é dado que ninguém tipou."
    )
