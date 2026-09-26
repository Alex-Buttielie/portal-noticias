"""
P1-06 — DESCADASTRO: o direito do titular, e o teste mais importante do item.

O QUE ESTE ARQUIVO PROVA
=======================
`POST /api/newsletter/descadastrar/` é o direito do titular (LGPD art. 8º, V —
cancelamento do consentimento). O risco de um endpoint de cancelamento não é
"não funcionar": é **funcionar demais**, isto é, virar oráculo que responde
"este e-mail está inscrito no portal". Resposta que distingue inscrito de não
inscrito confirma a um terceiro que o endereço de alguém está na base — e é
exatamente o que a LGPD proíbe (art. 19: o acesso a dados só pode ser feito
mediante transparência sobre a finalidade).

O QUE JÁ ESTAVA CERTO (medido em d225791, antes deste item)
===========================================================
* O endpoint é `AllowAny` (`newsletter/views.py:34`) e aceita o token pela
  query OU pelo corpo — que é o que o frontend envia
  (`frontend/lib/api.ts:959-963`).
* Descadastrar desativa a inscrição (`services.descadastrar_por_token`), e a
  inscrição desativada não recebe e-mail (filtro `ativa=True` em
  `services.enviar_newsletters`) — o efeito do cancelamento existia.
* Duplo clique já era inofensivo na prática: a segunda chamada repetia a mesma
  atualização.

O QUE ESTAVA ERRADO (medido antes da correção)
==============================================
* token válido → 200 `{"detail": "Descadastro realizado."}`
  token inválido → 400 `{"detail": "Token inválido."}`
  Duas respostas distintas para o mesmo endpoint = oráculo de cadastro.
* O token era o **segredo cru do banco** (`models.py:40`), permanente e
  replayável: 3 POSTs do mesmo token → 3 × 200, segredo nunca rotacionado,
  sem expiry.

COMO ESTE ARQUIVO PROVA QUE NÃO REVELA
=======================================
`test_descadastro_nao_distingue_inscrito_de_nao_inscrito` monta os quatro
estados possíveis de um token (válido / inexistente / expirado / já usado) e
compara a resposta **inteira** — status, corpo e cabeçalhos — byte a byte. Não
basta os status coincidirem: um corpo que dissesse "você estava inscrito"
vazaria do mesmo jeito, e este teste pega.
"""

from __future__ import annotations

import time
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core import signing
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from newsletter import services
from newsletter.models import InscricaoNewsletter
from newsletter.tokens import gerar_token_descadastro, hash_do_segredo, ler_hash_do_token

pytestmark = pytest.mark.django_db
User = get_user_model()

URL = "/api/newsletter/descadastrar/"


# ---------------------------------------------------------------------------
# Ajudantes
# ---------------------------------------------------------------------------


def _consentido(email):
    user = User.objects.create_user(email=email, password="senha123", papel="free")
    user.consentimento_aceito_em = timezone.now()
    user.save(update_fields=["consentimento_aceito_em"])
    return user


def _inscricao(email="descadastro@example.com"):
    return services.inscrever(_consentido(email), InscricaoNewsletter.TIPO_PADRAO)


def _postar(token, **extra):
    corpo = dict(extra)
    if token is not None:
        corpo["token"] = token
    return APIClient().post(URL, corpo, format="json")


# Cabeçalhos que mudam a CADA requisição, por desenho, e portanto não podem
# carregar informação sobre o token. `X-Request-ID` é um UUID de correlação
# gerado por requisição (`RequestIdLogFilter`, `config/settings.py`): ele é
# diferente em duas respostas idênticas e igual em duas respostas diferentes.
# Comparar tudo indiscriminadamente daria falso negativo (o teste falharia por
# causa do UUID) e, pior, daria a impressão de que ele é sinal de alguma coisa.
POR_REQUEST = {"X-Request-ID"}


def _resposta_completa(resposta):
    """Tudo que o cliente observa e que é estável entre requisições."""
    return (
        resposta.status_code,
        resposta.content,
        tuple(
            (chave, valor)
            for chave, valor in sorted(resposta.headers.items())
            if chave not in POR_REQUEST
        ),
    )


class _RelogioDeslocado:
    """Só substitui `time()`; o resto do módulo `time` continua real.

    O `TimestampSigner` do Django assina `payload:timestamp` (a assinatura
    COBRE o timestamp — `django/core/signing.py`, `Signer.sign`), então
    reescrever o campo no token depois invalidaria a assinatura e o teste
    mediria a assinatura, não a idade. Deslocar o relógio no momento da EMISSÃO
    exercita o caminho real do código, assinatura válida e tudo.
    """

    def __init__(self, segundos):
        self._segundos = segundos

    def time(self):
        return time.time() - self._segundos

    def __getattr__(self, nome):
        return getattr(time, nome)


def _emitir_com_idade(inscricao, segundos):
    """Token de descadastro emitido `segundos` no passado."""
    with mock.patch.object(signing, "time", _RelogioDeslocado(segundos)):
        return gerar_token_descadastro(inscricao)


# ---------------------------------------------------------------------------
# O teste central do item
# ---------------------------------------------------------------------------


def test_descadastro_nao_distingue_inscrito_de_nao_inscrito():
    """Os quatro estados de token produzem a MESMA resposta, byte a byte.

    Faz este teste falhar: voltar a responder 400/200 conforme
    `descadastrar_por_token` devolvesse `True`/`False` (o código anterior), ou
    reintroduzir um corpo que distinga os casos.
    """
    inscricao = _inscricao()
    token_valido = gerar_token_descadastro(inscricao)
    token_expirado = _emitir_com_idade(inscricao, 60 * 60 * 24 * 365)

    # 1. válido, ainda não usado  2. nunca existiu  3. já usado  4. de um ano atrás
    resposta_valido = _postar(token_valido)
    resposta_inexistente = _postar("token-que-nunca-existiu-abcdef")
    resposta_replay = _postar(token_valido)
    resposta_expirado = _postar(token_expirado)

    estados = {
        "válido": resposta_valido,
        "inexistente": resposta_inexistente,
        "já usado": resposta_replay,
        "expirado": resposta_expirado,
    }
    observavel = {nome: _resposta_completa(r) for nome, r in estados.items()}

    assert observavel["válido"] == observavel["inexistente"], (
        "a resposta distingue um token de inscrição real de um token qualquer: "
        "o endpoint virou oráculo de cadastro"
    )
    assert observavel["válido"] == observavel["já usado"]
    assert observavel["válido"] == observavel["expirado"]

    # E o corpo não pode ser mudo: quem chegou com link velho precisa de uma
    # instrução útil, não de um "não existe" que o denunciaria nem de um silêncio
    # que o faria esperar dezoito vezes.
    assert resposta_valido.status_code == 200
    detalhe = resposta_valido.json()["detail"].lower()
    assert "descadastro registrado" in detalhe
    assert "expiram" in detalhe or "mais recente" in detalhe


def test_resposta_nao_contem_o_endereco_de_ninguem():
    """A resposta também não carrega dado pessoal de quem está inscrito."""
    inscricao = _inscricao("pessoa-privada@example.com")
    detalhe = _postar(gerar_token_descadastro(inscricao)).json()["detail"]
    assert "pessoa-privada@example.com" not in detalhe
    assert "@" not in detalhe


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------


def test_descadastrar_duas_vezes_nao_da_erro_nem_efeito_diferente():
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)

    primeira = _postar(token)
    inscricao.refresh_from_db()
    estado_apos_primeira = inscricao.ativa
    carimbo_apos_primeira = inscricao.atualizado_em

    segunda = _postar(token)
    inscricao.refresh_from_db()

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.json() == segunda.json()
    assert estado_apos_primeira is False
    assert inscricao.ativa is False, "a segunda chamada reativou a inscrição"
    # A segunda chamada não pode reescrever a linha: `ativa` já estava False, e o
    # instante registrado da revogação (`atualizado_em`) não deve andar.
    assert inscricao.atualizado_em == carimbo_apos_primeira


def test_descadastrar_tres_vezes_segue_estavel():
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)
    respostas = [_postar(token) for _ in range(3)]
    assert len({_resposta_completa(r) for r in respostas}) == 1
    inscricao.refresh_from_db()
    assert inscricao.ativa is False


def test_descadastro_de_quem_ja_estava_desativado_nao_muda_nada():
    """Inscrição desligada por outro caminho (o DELETE autenticado) e o link
    depois: resposta igual, e a pessoa continua desligada.

    O token É consumido mesmo assim (o segredo gira). É deliberado: um link
    reutilizado — impresso, reencaminhado, guardado no histórico — deixa de
    valer na primeira vez que é exercido, mesmo quando não havia o que revogar.
    E como a resposta é a mesma nos dois casos, consumir o token não diz nada ao
    chamador sobre o que havia.
    """
    inscricao = _inscricao()
    services.cancelar_inscricao(inscricao.user)
    inscricao.refresh_from_db()
    segredo = inscricao.token_descadastro

    resposta = _postar(gerar_token_descadastro(inscricao))

    inscricao.refresh_from_db()
    assert inscricao.ativa is False
    assert resposta.status_code == 200
    assert inscricao.token_descadastro != segredo, "o link deveria ser consumido no uso"
    assert _postar(gerar_token_descadastro(inscricao)).json() == resposta.json()


# ---------------------------------------------------------------------------
# Uso único
# ---------------------------------------------------------------------------


def test_token_e_de_uso_unico_secredo_e_rotacionado_no_primeiro_uso():
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)
    segredo_antes = inscricao.token_descadastro

    _postar(token)

    inscricao.refresh_from_db()
    assert inscricao.ativa is False
    assert inscricao.token_descadastro != segredo_antes, (
        "o segredo do banco não foi rotacionado: o mesmo token continuaria válido "
        "para sempre, e 'expira' seria ficção"
    )


def test_token_antigo_deixa_de_valer_apos_reinscricao():
    """Reinscrever gera segredo novo; o link guardado no e-mail antigo não volta
    a valer — nem consegue cancelar a inscrição que a pessoa refez."""
    inscricao = _inscricao()
    token_antigo = gerar_token_descadastro(inscricao)
    _postar(token_antigo)
    inscricao.refresh_from_db()
    assert inscricao.ativa is False

    services.inscrever(inscricao.user, InscricaoNewsletter.TIPO_PADRAO)
    inscricao.refresh_from_db()
    assert inscricao.ativa is True

    _postar(token_antigo)
    inscricao.refresh_from_db()
    assert inscricao.ativa is True, (
        "um token já usado conseguiu cancelar a inscrição — o cancelamento não é de uso único"
    )


def test_cancelamentos_concorrentes_do_mesmo_token_nao_reativam_nada():
    """Dois descadastros do mesmo token: só um pode rotacionar o segredo.

    O filtro do `UPDATE` inclui o segredo antigo, então o segundo POST não casa
    linha nenhuma. O efeito final é o mesmo dos dois — desinscrito — que é o
    que interessa; o que não pode acontecer é um segundo cancelamento gravando
    por cima.
    """
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)

    assert services.descadastrar_por_token(token) is True
    assert services.descadastrar_por_token(token) is False

    inscricao.refresh_from_db()
    assert inscricao.ativa is False


# ---------------------------------------------------------------------------
# Expiração
# ---------------------------------------------------------------------------


def test_token_expirado_nao_desinscreve():
    inscricao = _inscricao()
    token = _emitir_com_idade(inscricao, 60 * 60 * 24 * 365)

    resposta = _postar(token)

    inscricao.refresh_from_db()
    assert inscricao.ativa is True, "um token de um ano de idade cancelou a inscrição"
    assert resposta.status_code == 200, "expirado não pode virar um status diferente"


def test_validade_vem_do_setting_e_e_lida_por_chamada():
    """O mesmo token, com 100 segundos de idade, é aceito ou recusado só pelo
    limite configurado — prova que é a IDADE que decide, e não uma assinatura
    quebrada (neste caminho o segredo do banco também mudou, então um erro de
    assinatura apareceria aqui)."""
    inscricao = _inscricao()
    velho = _emitir_com_idade(inscricao, 100)

    with override_settings(NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS=10):
        assert ler_hash_do_token(velho) is None, "100s de idade passou por um limite de 10s"
    with override_settings(NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS=300):
        assert ler_hash_do_token(velho) is not None, "100s de idade reprovou num limite de 300s"


def test_default_de_validade_e_30_dias():
    from django.conf import settings

    assert settings.NEWSLETTER_TOKEN_DESCADASTRO_MAX_AGE_SECONDS == 30 * 24 * 60 * 60


def test_tempo_do_token_e_selo_do_django_e_nao_aleatorio():
    """Trava a premissa de `_emitir_com_idade`: dois tokens da mesma inscrição
    são byte a byte iguais. Sem isso, os testes de expiração mediriam
    aleatoriedade em vez de idade."""
    inscricao = _inscricao()
    assert gerar_token_descadastro(inscricao) == gerar_token_descadastro(inscricao)
    assert ler_hash_do_token(gerar_token_descadastro(inscricao)) == hash_do_segredo(
        inscricao.token_descadastro
    )


# ---------------------------------------------------------------------------
# Sem login; e a única resposta diferente, que não consulta o banco
# ---------------------------------------------------------------------------


def test_descadastro_funciona_sem_autenticacao():
    inscricao = _inscricao()
    resposta = APIClient().post(
        URL, {"token": gerar_token_descadastro(inscricao)}, format="json"
    )
    inscricao.refresh_from_db()
    assert inscricao.ativa is False
    assert resposta.status_code == 200


def test_token_aceito_pela_query_string_tambem():
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)
    resposta = APIClient().post(f"{URL}?token={token}", {}, format="json")
    inscricao.refresh_from_db()
    assert inscricao.ativa is False
    assert resposta.status_code == 200


def test_ausencia_de_token_responde_400_sem_consultar_o_banco(django_assert_num_queries):
    """A única resposta diferente é "não veio token", e ela não lê o banco.

    É o que fecha a porta do oráculo por construção: a resposta depende só de
    uma condição do PEDIDO (o campo veio vazio?), que é constante e não carrega
    informação sobre nenhuma pessoa. A prova é `0` queries.
    """
    _inscricao()
    with django_assert_num_queries(0):
        resposta = _postar(None)
    assert resposta.status_code == 400
    assert "token" in resposta.json()["detail"].lower()


@pytest.mark.parametrize("vazio", ["", "   "])
def test_token_vazio_e_tratado_como_ausente(vazio):
    _inscricao()
    assert _postar(vazio).status_code == 400


def test_um_token_nao_afeta_a_inscricao_de_outra_pessoa():
    """Dois tokens válidos e distintos: cada um cancela a sua inscrição, e só a
    sua. Se um token devolvesse a inscrição errada, haveria vazamento cruzado."""
    inscricao_a = _inscricao("pessoa-a@example.com")
    inscricao_b = _inscricao("pessoa-b@example.com")
    token_a = gerar_token_descadastro(inscricao_a)

    _postar(token_a)

    inscricao_a.refresh_from_db()
    inscricao_b.refresh_from_db()
    assert inscricao_a.ativa is False
    assert inscricao_b.ativa is True


# ---------------------------------------------------------------------------
# O segredo do banco não vaza no link
# ---------------------------------------------------------------------------


def test_link_de_descadastro_nao_contem_o_segredo_do_banco():
    inscricao = _inscricao()
    segredo = inscricao.token_descadastro
    corpo = services.montar_corpo_email(inscricao)

    assert segredo not in corpo, "o segredo do banco está no link do e-mail"
    # O que vai no link é o SHA-256 do segredo, assinado e com timestamp. Compara
    # o HASH (estável) e não o token inteiro: o timestamp muda a cada segundo, e
    # comparar o token inteiro daria falso negativo conforme a virada do segundo.
    assert hash_do_segredo(segredo) in corpo
    assert "/newsletter/descadastrar?token=" in corpo
    # E o hash, sozinho, não serve para nada sem o segredo do banco.
    assert ler_hash_do_token(hash_do_segredo(segredo)) is None


def test_assinatura_de_outro_salt_nao_e_aceita():
    """Um token de outra finalidade do projeto não cancela newsletter.

    Reaproveitar o par entre verificação de e-mail e descadastro daria ao dono de
    um link de verificação o direito de cancelar a newsletter — e o contrário.
    """
    inscricao = _inscricao()
    alheio = signing.TimestampSigner(salt="identidade.verificar-email").sign(
        hash_do_segredo(inscricao.token_descadastro)
    )
    _postar(alheio)
    inscricao.refresh_from_db()
    assert inscricao.ativa is True


def test_token_adulterado_nao_e_aceito():
    inscricao = _inscricao()
    token = gerar_token_descadastro(inscricao)
    adulterado = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    _postar(adulterado)
    inscricao.refresh_from_db()
    assert inscricao.ativa is True


def test_consulta_de_token_alheio_nao_revela_nada_ao_chamador():
    """A camada de serviço devolve só "token apresentado ou não".

    `descadastrar_por_token` é a fronteira onde a mentira poderia voltar a
    entrar: se devolvesse "havia inscrição", a view não teria como esconder.
    """
    inscricao = _inscricao()
    assert services.descadastrar_por_token(gerar_token_descadastro(inscricao)) is True
    assert services.descadastrar_por_token("nada-disso-aqui") is False
