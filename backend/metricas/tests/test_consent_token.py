"""Contrato do token de consentimento assinado: formato, verificação, rotação.

Cobre os critérios 26 e 27 (implementation-contract.md, run
20260925-1020-observabilidade): token ausente, inválido, adulterado, expirado ou
de categoria errada NÃO pode virar dado de produto autorizado.

Estes testes são a especificação executável do formato que o frontend vai
consumir (Bloco B): envelope `v1.<payload_b64url>.<assinatura_b64url>`, payload
canônico com chaves ordenadas e claims `v`/`categoria`/`iat`/`exp`/`sub`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from django.test import override_settings

from metricas import consent

CHAVE_A = "chave-de-teste-a-nao-usar-em-producao-0123456789"
CHAVE_B = "chave-de-teste-b-nao-usar-em-producao-9876543210"
SUB = "sessao-teste-01"

pytestmark = pytest.mark.django_db


def _claims(token: str) -> dict:
    parte = token.split(".")[1]
    bruto = base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4))
    return json.loads(bruto.decode("utf-8"))


def _reassinar(token: str, claims: dict, chave: str = CHAVE_A) -> str:
    """Refaz um token VÁLIDO com outras claims (para os testes de claim)."""

    payload = (
        base64.urlsafe_b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
        .decode("ascii")
        .rstrip("=")
    )
    mensagem = f"v1.{payload}".encode("ascii")
    assinatura = (
        base64.urlsafe_b64encode(
            hmac.new(chave.encode("utf-8"), mensagem, hashlib.sha256).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )
    return f"v1.{payload}.{assinatura}"


def _token(**kwargs) -> str:
    return consent.gerar_token_consent(sub=SUB, **kwargs)


@pytest.fixture(autouse=True)
def _chave_de_teste():
    """Isola o módulo da chave real do ambiente.

    Sem isto, `_chave_ativa()` cairia na `SECRET_KEY` do ambiente de teste e a
    suíte passaria a depender de configuração externa — e a rotação de chave,
    que precisa das duas chaves em settings diferentes, nem seria testável.
    """

    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=CHAVE_A, ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS=""
    ):
        yield


# ---------------------------------------------------------------------------
# Formato
# ---------------------------------------------------------------------------


def test_token_tem_envelope_de_tres_partes_e_claims_canonicas():
    agora = 1_758_000_000
    token = _token(agora=agora)

    assert token.count(".") == 2
    versao, payload, assinatura = token.split(".")
    assert versao == consent.VERSAO_TOKEN
    # base64url sem padding e com o alfabeto certo (nada de `+`, `/` ou `=`).
    assert set(payload) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert set(assinatura) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_")
    assert "=" not in token
    # Payload canônico: chaves ordenadas, sem espaços, claims completas.
    bruto = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)).decode("utf-8")
    assert bruto == json.dumps(
        {
            "categoria": "analytics",
            "exp": agora + 86_400,
            "iat": agora,
            "sub": SUB,
            "v": 1,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    # A assinatura cobre a VERSÃO também (não só o payload).
    esperada = hmac.new(
        CHAVE_A.encode("utf-8"), f"v1.{payload}".encode("ascii"), hashlib.sha256
    ).digest()
    assert base64.urlsafe_b64decode(assinatura + "=" * (-len(assinatura) % 4)) == esperada


def test_assinatura_tem_32_bytes_de_senha():
    """Comprimento fixo do digest: sem ele um token truncado 'validaria'."""

    token = _token()
    assert len(base64.urlsafe_b64decode(token.split(".")[2] + "==")) == hashlib.sha256().digest_size


def test_token_gerado_e_verificado_para_a_mesma_sessao():
    verificacao = consent.verificar_consentimento(_token(), sub_esperado=SUB)

    assert verificacao.ok
    assert verificacao.motivo == ""
    assert verificacao.claims["categoria"] == consent.CATEGORIA_ANALYTICS
    assert verificacao.sub == SUB


def test_payload_do_token_nao_carrega_dado_pessoal():
    """O token é a prova de consentimento: ele não pode virar um vetor de PII."""

    token = _token()
    assert "@" not in token
    assert "authorization" not in token.lower()
    claims = _claims(token)
    assert claims["v"] == 1
    assert claims["categoria"] == "analytics"
    assert claims["sub"] == SUB
    agora = time.time()
    assert claims["exp"] - claims["iat"] == 86_400
    assert abs(claims["iat"] - agora) < 5


# ---------------------------------------------------------------------------
# Recusas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("", id="vazio"),
        pytest.param(None, id="nulo"),
        pytest.param("   ", id="branco"),
        pytest.param("v1.sozinho", id="partes-a-menos"),
        pytest.param("v1.a.b.c", id="partes-a-mais"),
        pytest.param("v2.a.b", id="versao-desconhecida"),
        pytest.param("v1.@@@.@@@", id="base64-invalido"),
        pytest.param("v1.a+b.c", id="base64-padrao-e-nao-urlsafe"),
        pytest.param("x" * 5_000, id="absurdamente-longo"),
    ],
)
def test_token_malformado_e_recusado(token):
    verificacao = consent.verificar_consentimento(token, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo in {
        consent.MOTIVO_AUSENTE,
        consent.MOTIVO_MALFORMADO,
        consent.MOTIVO_TOKEN_GRANDE,
    }


@pytest.mark.parametrize(
    "token",
    [
        pytest.param("v1.çã.<b64>", id="payload-nao-ascii"),
        pytest.param("v1.a.assinatura-com-acentuação", id="assinatura-nao-ascii"),
        pytest.param("v1.\u00e9\u00e9.\u00e9\u00e9\u00e9", id="tudo-nao-ascii"),
        pytest.param("v1.a.é" * 900, id="nao-ascii-gigante"),
    ],
)
def test_token_com_caractere_fora_do_ascii_nao_vira_excecao(token):
    """Um `\u00e9` no token não pode virar `UnicodeEncodeError` na verificação:
    o endpoint é público e uma exceção aí seria 500 — o caminho oposto de
    "robusto"."""

    verificacao = consent.verificar_consentimento(token, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo in {consent.MOTIVO_MALFORMADO, consent.MOTIVO_TOKEN_GRANDE}


def test_token_valido_e_recusado_quando_assinatura_e_trocada():
    """Adulterar a assinatura mantendo o payload (ataque de troca)."""

    token = _token()
    _v, payload, assinatura = token.split(".")
    adulterado = f"{_v}.{payload}.{assinatura[:-4]}{'A' * 4}"

    verificacao = consent.verificar_consentimento(adulterado, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_ASSINATURA


def test_payload_adulterado_com_assinatura_da_chave_errada_e_recusado():
    """Reescrever `categoria`/`sub` e re-assinar com outra chave não vale."""

    agora = int(time.time())
    claims = {"v": 1, "categoria": "analytics", "iat": agora, "exp": agora + 86_400, "sub": SUB}
    forja = _reassinar(_token(), claims, chave=CHAVE_B)

    verificacao = consent.verificar_consentimento(forja, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_ASSINATURA


def test_token_expirado_e_recusado():
    token = _token(ttl_seconds=120, agora=int(time.time()) - 3_600)

    verificacao = consent.verificar_consentimento(token, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_EXPIRADO


def test_token_de_validade_acima_do_ttl_configurado_e_recusado():
    """TTL da configuração vence o token: sem isto, um token válido de 10 anos
    sobreviveria a qualquer mudança de política de retenção."""

    agora = int(time.time())
    claims = {
        "v": 1,
        "categoria": "analytics",
        "iat": agora,
        "exp": agora + 10 * 365 * 86_400,
        "sub": SUB,
    }
    longo = _reassinar(_token(), claims)

    with override_settings(ANALYTICS_CONSENT_TTL_SECONDS=3_600):
        verificacao = consent.verificar_consentimento(longo, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_TTL


def test_token_emitido_muito_no_futuro_e_recusado():
    agora = int(time.time())
    claims = {
        "v": 1,
        "categoria": "analytics",
        "iat": agora + 3_600,
        "exp": agora + 3_600 + 86_400,
        "sub": SUB,
    }
    futuro = _reassinar(_token(), claims)

    verificacao = consent.verificar_consentimento(futuro, sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_EMISSAO


def test_desvio_pequeno_de_relogio_nao_invalida_o_token():
    """Celular com NTP atrasado continua comendo analytics."""

    agora = int(time.time()) - 20  # relógio do visitante 20 s atrás
    token = _token(agora=agora)

    assert consent.verificar_consentimento(token, sub_esperado=SUB).ok


def test_categoria_errada_e_recusada():
    """`analytics` não é `technical` (nem o contrário): são categorias distintas."""

    agora = int(time.time())
    for categoria in ("technical", "tecnico", "analytics_v2", ""):
        claims = {
            "v": 1,
            "categoria": categoria,
            "iat": agora,
            "exp": agora + 86_400,
            "sub": SUB,
        }
        verificacao = consent.verificar_consentimento(
            _reassinar(_token(), claims), sub_esperado=SUB
        )
        assert not verificacao.ok, categoria
        assert verificacao.motivo in {consent.MOTIVO_CATEGORIA, consent.MOTIVO_MALFORMADO}, categoria


def test_token_nao_e_reaproveitado_em_outra_sessao():
    token = _token()

    mesma = consent.verificar_consentimento(token, sub_esperado=SUB)
    outra = consent.verificar_consentimento(token, sub_esperado="outra-sessao-99")

    assert mesma.ok
    assert not outra.ok
    assert outra.motivo == consent.MOTIVO_SUJEITO


@pytest.mark.parametrize(
    "claims_extra",
    [
        {"jti": "x"},
        {"email": "leitor@dominio.invalid"},
        {"escopo": "admin"},
    ],
)
def test_claim_a_mais_ou_claim_de_pii_e_recusada(claims_extra):
    """Nenhuma claim fora do contrato é aceita — o envelope não é um dicionário
    livre para contrabandear dado."""

    agora = int(time.time())
    claims = {
        "v": 1,
        "categoria": "analytics",
        "iat": agora,
        "exp": agora + 86_400,
        "sub": SUB,
        **claims_extra,
    }
    verificacao = consent.verificar_consentimento(_reassinar(_token(), claims), sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_MALFORMADO


@pytest.mark.parametrize(
    "claims_ruins",
    [
        {"v": 2},
        {"iat": "1758000000"},
        {"exp": 1.5},
        {"iat": True},
        {"categoria": 1},
        {"sub": "curto"},
        {"sub": "com espaço e acentos"},
    ],
)
def test_claims_com_tipo_ou_formato_errado_sao_recusadas(claims_ruins):
    agora = int(time.time())
    claims = {
        "v": 1,
        "categoria": "analytics",
        "iat": agora,
        "exp": agora + 86_400,
        "sub": SUB,
    }
    claims.update(claims_ruins)
    verificacao = consent.verificar_consentimento(_reassinar(_token(), claims), sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo in {consent.MOTIVO_MALFORMADO, consent.MOTIVO_CATEGORIA, consent.MOTIVO_SUJEITO}


def test_claim_ausente_e_recusada():
    agora = int(time.time())
    claims = {"v": 1, "categoria": "analytics", "iat": agora, "exp": agora + 86_400}
    verificacao = consent.verificar_consentimento(_reassinar(_token(), claims), sub_esperado=SUB)

    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_MALFORMADO


# ---------------------------------------------------------------------------
# Chave: fallback, ausência e rotação
# ---------------------------------------------------------------------------


def test_sem_chave_configurada_o_token_e_recusado_e_nao_e_emitido(monkeypatch):
    """Fail-closed de configuração: nada de "sem chave, aceita e segue"."""

    from django.conf import settings as django_settings

    token = _token()
    monkeypatch.setattr(django_settings, "ANALYTICS_CONSENT_SIGNING_KEY", "")
    monkeypatch.setattr(django_settings, "SECRET_KEY", "")

    with pytest.raises(consent.ConsentError) as erro:
        consent.gerar_token_consent(sub=SUB)
    assert erro.value.motivo == consent.MOTIVO_SEM_CHAVE

    verificacao = consent.verificar_consentimento(token, sub_esperado=SUB)
    assert not verificacao.ok
    assert verificacao.motivo == consent.MOTIVO_SEM_CHAVE


def test_chave_vazia_cai_na_secret_key():
    from django.conf import settings as django_settings

    with override_settings(ANALYTICS_CONSENT_SIGNING_KEY=""):
        token = consent.gerar_token_consent(sub=SUB)
        assert consent.verificar_consentimento(token, sub_esperado=SUB).ok
        # Assinado com a SECRET_KEY de fato, não com um valor inventado no módulo.
        payload = token.split(".")[1]
        esperado = hmac.new(
            str(django_settings.SECRET_KEY).encode("utf-8"),
            f"v1.{payload}".encode("ascii"),
            hashlib.sha256,
        ).digest()
        assert base64.urlsafe_b64decode(token.split(".")[2] + "==") == esperado


def test_rotacao_aceita_a_chave_anterior_e_invalida_quando_sai():
    antigo = _token()

    # Durante a janela de rotação, o token já no navegador continua valendo.
    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=CHAVE_B,
        ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS=CHAVE_A,
    ):
        assert consent.verificar_consentimento(antigo, sub_esperado=SUB).ok
        # E o novo já é assinado pela chave nova.
        assert consent.gerar_token_consent(sub=SUB) != antigo

    # Depois de a chave antiga sair da lista: revogação real.
    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=CHAVE_B, ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS=""
    ):
        verificacao = consent.verificar_consentimento(antigo, sub_esperado=SUB)
        assert not verificacao.ok
        assert verificacao.motivo == consent.MOTIVO_ASSINATURA


# ---------------------------------------------------------------------------
# Sujeito
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sub", ["", "abc", "x" * 65, "com espaço", "acentuação-çã", None, "a;b"])
def test_sujeito_invalido_nao_e_emitido(sub):
    with pytest.raises(consent.ConsentError) as erro:
        consent.gerar_token_consent(sub=sub)
    assert erro.value.motivo == consent.MOTIVO_SUJEITO


def test_normalizar_sub_descarta_caractere_fora_do_alfabeto():
    assert consent.normalizar_sub("sessão/../x y") == "sesso..xy"
    assert consent.sub_valido(consent.normalizar_sub("sessão/../x y"))
    assert not consent.sub_valido(consent.normalizar_sub("çã/x y"))  # curto demais


def test_categoria_invalida_nao_e_emitida():
    with pytest.raises(consent.ConsentError) as erro:
        consent.gerar_token_consent(categoria="technical", sub=SUB)
    assert erro.value.motivo == consent.MOTIVO_CATEGORIA


@pytest.mark.parametrize("sub", ["", "abc", "x" * 65, "com espaço", "acentuação-çã", None, "a;b"])
def test_sujeito_invalido_nao_e_emitido(sub):
    with pytest.raises(consent.ConsentError) as erro:
        consent.gerar_token_consent(sub=sub)
    assert erro.value.motivo == consent.MOTIVO_SUJEITO
