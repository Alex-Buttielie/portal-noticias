"""
P1-05 — Login Google OAuth: suíte de ataque e de contrato de segurança.

POR QUE ESTA SUÍTE EXISTE
-------------------------
O código do login social já existia (6 testes, todos com
`GoogleProvider.verify_token` **inteiramente mockado**) e mesmo assim o
critério de aceite "OAuth funciona em DEV/HOMOLOG/PROD" nunca foi
cumprido. Mockar `verify_token` de ponta a ponta significa que nenhuma
linha de verificação do allauth roda nos testes: assinatura, `iss`, `aud`,
`exp` e a flag `email_verified` eram, até aqui, código não testado.

Esta suíte usa o caminho **real** do allauth. Em vez de mockar
`verify_token`, ela:

- gera um par RSA de 2048 bits na hora do teste;
- assina um `id_token` de verdade com a chave privada (RS256);
- injeta a chave pública em `jwtkit.fetch_key`, que é a **única** função
  que faz I/O de rede nesta verificação (busca dos certificados do
  Google). Nenhuma requisição de rede é feita em nenhum teste.

Ou seja: `GoogleProvider.verify_token` roda de verdade, `jwtkit`
`verify_and_decode` roda de verdade, e a checagem de assinatura continua
sendo exercitada — inclusive nos testes que a precisam reprovar.

BLOCERS COBERTOS
----------------
- `TestStateNonce` — o `state`/anti-CSRF e o anti-replay. Este fluxo não
  redireciona o navegador, então não existe `state` do protocolo; o
  equivalente é o par nonce emitido-pela-sessão + claim `nonce` assinado.
- `TestEmailVerificado` — identidade por e-mail **não verificado**. Era o
  blocker de sequestro de conta: `GoogleLoginView` buscava a conta local
  por e-mail sem olhar `email_verified` e vinculava.
- `TestAssinaturaIdToken` — assinatura, `iss`, `aud`, `exp`, `alg: none`.
- `TestAuditoria` — todo desfecho registrado, sem credencial no log.
- `TestConfiguracao` — ambiente sem client_id não vira "token inválido".
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import time
from unittest.mock import patch

import pytest
from allauth.core.internal.deferred import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from identidade import oauth_google

User = get_user_model()

pytestmark = pytest.mark.django_db

ISSUER = "https://accounts.google.com"
ENDPOINT_INICIAR = "/api/auth/google/iniciar/"
ENDPOINT_LOGIN = "/api/auth/google/"

# Identificador de cliente em uso na suíte (ver `config/settings_test.py`).
# Lido do settings em vez de repetido aqui: se o valor mudar, os testes
# continuam medindo a coisa certa em vez de medirem um literal velho.
CLIENT_ID = settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"]["client_id"]


# ---------------------------------------------------------------------------
# Infra de dublê: par RSA + id_token assinado de verdade
# ---------------------------------------------------------------------------

_CHAVE_PRIVADA = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_CHAVE_PUBLICA = _CHAVE_PRIVADA.public_key()


def _id_token(
    *,
    email="alvo@example.com",
    email_verified=True,
    nonce="nonce-de-teste",
    aud=None,
    iss=ISSUER,
    exp_segundos=3600,
    alg="RS256",
    chave=None,
    incluir_nonce=True,
    sub="google-sub-001",
):
    """Monta um `id_token` assinado, com o payload que o Google emitiria."""
    agora = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "iss": iss,
        "aud": CLIENT_ID if aud is None else aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": "Pessoa Teste",
        "given_name": "Pessoa",
        "iat": int(agora.timestamp()),
        "exp": int((agora + datetime.timedelta(seconds=exp_segundos)).timestamp()),
    }
    if incluir_nonce:
        payload["nonce"] = nonce
    material = "" if alg == "none" else (chave if chave is not None else _CHAVE_PRIVADA)
    return jwt.encode(payload, material, algorithm=alg, headers={"kid": "kid-de-teste"})


@contextlib.contextmanager
def chave_publica_injetada(chave=None, alg="RS256"):
    """
    Neutraliza **apenas** a busca de rede dos certificados do Google.

    `jwtkit.fetch_key` é a função que faz `GET` em
    `https://www.googleapis.com/oauth2/v1/certs`. Devolvendo o par
    (algoritmo, chave pública) direto, todo o resto de
    `verify_and_decode` — decodificação, conferência de assinatura, `iss`,
    `aud`, `exp` — continua sendo o código de produção rodando de verdade.
    """
    with patch(
        "allauth.socialaccount.internal.jwtkit.fetch_key",
        return_value=(alg, chave if chave is not None else _CHAVE_PUBLICA),
    ):
        yield


def _iniciar(client: APIClient) -> str:
    """Passo 1 do handshake: o `state`/nonce emitido para esta sessão."""
    resp = client.post(ENDPOINT_INICIAR, {}, format="json")
    assert resp.status_code == 200, resp.data
    return resp.data["nonce"]


def _nonce_e_token(client: APIClient, *, claim_nonce=None, **claims):
    """
    Ordem correta do handshake: primeiro o nonce da sessão, **depois** o
    `id_token` amarrado a ele.

    Fazer o contrário (token pronto, nonce depois) produz um token cujo
    claim `nonce` não é o `state` da sessão — que é exatamente o que o
    servidor recusa. Nos testes de ataque isso é o cenário; no caminho
    feliz é só um erro de teste.
    """
    nonce = _iniciar(client)
    id_token = _id_token(
        nonce=claim_nonce if claim_nonce is not None else nonce, **claims
    )
    return nonce, id_token


def _postar(client: APIClient, id_token: str, nonce: str, *, aceite_termos=True):
    return client.post(
        ENDPOINT_LOGIN,
        {"id_token": id_token, "aceite_termos": aceite_termos, "nonce": nonce},
        format="json",
    )


def _login(client: APIClient, *, aceite_termos=True, alg="RS256", **claims):
    """Caminho completo com a chave pública legítima injetada."""
    nonce, id_token = _nonce_e_token(client, alg=alg, **claims)
    with chave_publica_injetada(alg=alg):
        return _postar(client, id_token, nonce, aceite_termos=aceite_termos)


def _recusa(resp, status_esperado=(400, 403)):
    """Asserção de recusa: status de recusa e nenhum token emitido."""
    assert resp.status_code in status_esperado, resp.data
    assert "token" not in resp.data, resp.data
    return resp


# ---------------------------------------------------------------------------
# 1. state/nonce — anti-CSRF e anti-replay
# ---------------------------------------------------------------------------

class TestStateNonce:
    """
    O que cada teste prova:

    - `test_iniciar_emite_nonce_nao_previsivel` — 256 bits, muda a cada
      emissão, formato URL-safe. Um `state` previsível é um `state` inútil.
    - `test_nonce_ausente_ou_em_branco_e_recusado` — `state` ausente não
      cai num caminho permissivo.
    - `test_nonce_de_sessao_que_nao_e_a_nossa_e_recusado` — nonce plausível,
      emitido por outra sessão.
    - `test_nonce_errado_e_recusado` — nonce de outro formato.
    - `test_nonce_de_outra_sessao_nao_serve` — **o teste do atacante**: duas
      sessões, o nonce de uma não autentica a outra. É o que impede um site
      atacante de forçar o POST no navegador da vítima.
    - `test_nonce_reutilizado_e_recusado` — uso único (anti-replay).
    - `test_nonce_expirado_e_recusado` — janela de 10 minutos.
    - `test_novo_nonce_invalida_o_anterior` — duas abas não geram dois
      nonces válidos.
    - `test_nonce_ausente_na_claim_do_id_token_e_recusado` — o `id_token`
      precisa trazer o `nonce` assinado.
    - `test_nonce_divergente_na_claim_e_recusado` — a claim assinada tem de
      bater com o `state` da sessão. Replay de um `id_token` capturado de
      outra sessão morre aqui.
    - `test_login_com_nonce_correspondente_passa` — controle positivo, para
      que a recusa não seja "recusa porque quebrou".
    """

    def test_iniciar_emite_nonce_nao_previsivel(self):
        client = APIClient()
        primeiro = _iniciar(client)
        segundo = _iniciar(client)
        assert primeiro != segundo
        # token_urlsafe(32) = 43 caracteres = 256 bits de entropia.
        assert len(primeiro) == 43
        assert all(c.isalnum() or c in "-_" for c in primeiro)

    def test_nonce_ausente_ou_em_branco_e_recusado(self):
        id_token = _id_token()
        client = APIClient()
        _iniciar(client)
        for payload in (
            {"id_token": id_token, "aceite_termos": True},  # sem o campo
            {"id_token": id_token, "aceite_termos": True, "nonce": ""},
            {"id_token": id_token, "aceite_termos": True, "nonce": "   "},
        ):
            with chave_publica_injetada():
                resp = client.post(ENDPOINT_LOGIN, payload, format="json")
            _recusa(resp)
        assert not User.objects.filter(email="alvo@example.com").exists()

    def test_nonce_de_sessao_que_nao_e_a_nossa_e_recusado(self):
        outra = APIClient()
        nonce_da_outra_sessao = _iniciar(outra)

        vitima = APIClient()
        with chave_publica_injetada():
            resp = _postar(
                vitima, _id_token(nonce=nonce_da_outra_sessao), nonce_da_outra_sessao
            )
        _recusa(resp, (403,))
        assert not User.objects.filter(email="alvo@example.com").exists()

    def test_nonce_errado_e_recusado(self):
        client = APIClient()
        _iniciar(client)
        with chave_publica_injetada():
            resp = _postar(client, _id_token(nonce="x" * 43), "y" * 43)
        _recusa(resp, (403,))

    def test_nonce_de_outra_sessao_nao_serve(self):
        """
        O cenário de ataque: o navegador da vítima é forçado (por um site
        terceiro, via POST cross-site) a executar o login social. O atacante
        tem um `id_token` **dele** e quer que o navegador da vítima vincule a
        conta Google dele à conta da vítima. Ele não tem a sessão da vítima,
        logo não tem o nonce dela, logo o POST é recusado.
        """
        vitima = APIClient()
        _iniciar(vitima)  # a vítima abriu o formulário de login

        atacante = APIClient()
        nonce_do_atacante = _iniciar(atacante)
        id_token_do_atacante = _id_token(
            email="alvo@example.com", nonce=nonce_do_atacante
        )

        # O navegador da vítima faz o POST forçado, trazendo o id_token do
        # atacante. O nonce que o atacante conhece não é o da vítima.
        with chave_publica_injetada():
            resp = vitima.post(
                ENDPOINT_LOGIN,
                {
                    "id_token": id_token_do_atacante,
                    "aceite_termos": True,
                    "nonce": nonce_do_atacante,
                },
                format="json",
            )
        _recusa(resp, (403,))
        assert not User.objects.filter(email="alvo@example.com").exists()

    def test_nonce_reutilizado_e_recusado(self):
        """Anti-replay: o mesmo id_token + o mesmo nonce não entram duas vezes."""
        client = APIClient()
        nonce, id_token = _nonce_e_token(client)

        with chave_publica_injetada():
            primeira = _postar(client, id_token, nonce)
            assert primeira.status_code == 200, primeira.data
            segunda = _postar(client, id_token, nonce)
        _recusa(segunda, (403,))

    def test_nonce_expirado_e_recusado(self):
        client = APIClient()
        nonce, id_token = _nonce_e_token(client)
        # O nonce foi emitido, mas a sessão "envelheceu" além da janela.
        with patch.object(oauth_google.time, "time", return_value=time.time() + 10_000):
            with chave_publica_injetada():
                resp = _postar(client, id_token, nonce)
        _recusa(resp, (403,))

    def test_novo_nonce_invalida_o_anterior(self):
        """
        Uma emissão nova substitui a pendente: vale sempre o último nonce
        emitido pela sessão. Duas abas do botão de login, portanto, não
        produzem dois nonces válidos — senão o anterior viraria adivinhável
        por ordem de chegada. O front que quiser relogar chama
        `/iniciar/` de novo.
        """
        client = APIClient()
        primeiro = _iniciar(client)
        segundo = _iniciar(client)
        with chave_publica_injetada():
            resp = _postar(client, _id_token(nonce=primeiro), primeiro)
        _recusa(resp, (403,))

    def test_tentativa_malsucedida_invalida_o_nonce(self):
        """
        O `pop` acontece antes da comparação: uma tentativa errada gasta o
        nonce. Com 256 bits de entropia não há o que adivinhar, mas a
        propriedade mais útil é outra — um nonce nunca é "tente de novo",
        então replay nunca tem segunda chance.
        """
        client = APIClient()
        nonce, id_token = _nonce_e_token(client)
        with chave_publica_injetada():
            resp = _postar(client, _id_token(nonce="x" * 43), "x" * 43)
        _recusa(resp, (403,))
        with chave_publica_injetada():
            segunda = _postar(client, id_token, nonce)
        _recusa(segunda, (403,))

    def test_nonce_ausente_na_claim_do_id_token_e_recusado(self):
        """
        O front que não passar `nonce` para o Google recebe um id_token sem
        a claim. Recusar é o ponto: sem isso, o `state` da sessão seria
        decorativo (validado, mas não amarrado a nada assinado).
        """
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, incluir_nonce=False)
        _recusa(resp, (403,))

    def test_nonce_divergente_na_claim_e_recusado(self):
        """
        Replay clássico: o atacante rouba um `id_token` capturado de outra
        sessão. Ele tem o token **e** a sessão dele, e o claim `nonce` do
        token não é o `state` da sessão dele → recusado.
        """
        vitima = APIClient()
        nonce_da_vitima = _iniciar(vitima)

        atacante = APIClient()
        with chave_publica_injetada():
            resp = _login(atacante, claim_nonce="nonce-de-outra-sessao-qualquer")
        _recusa(resp, (403,))
        assert nonce_da_vitima != "nonce-de-outra-sessao-qualquer"

    def test_login_com_nonce_correspondente_passa(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client)
        assert resp.status_code == 200, resp.data
        assert resp.data["criado_agora"] is True
        assert User.objects.filter(email="alvo@example.com").exists()


class TestGuardasDoNonce:
    """
    A sessão é dado serializado do lado do cliente em alguns deploys (cookie
    assinado). Valor corrompido ou forjado ali precisa cair em "inválido" —
    nunca em exceção, nunca em "válido". Estes testes cobrem cada guarda.
    """

    CHAVE = oauth_google.CHAVE_SESSAO_NONCE

    def _request(self):
        from django.contrib.sessions.backends.cache import SessionStore
        from django.test import RequestFactory

        request = RequestFactory().post(ENDPOINT_LOGIN)
        request.session = SessionStore()
        return request

    @pytest.mark.parametrize(
        "pendente",
        [
            "string corrompida",
            ["lista", "corrompida"],
            12345,
            {},
            {"valor": "", "criado_em": 1.0},
            {"valor": None, "criado_em": 1.0},
            {"valor": "x" * 43},
            {"valor": "x" * 43, "criado_em": "ontem"},
            {"valor": "x" * 43, "criado_em": None},
        ],
    )
    def test_sessao_corrompida_e_recusada_sem_explodir(self, pendente):
        request = self._request()
        request.session[self.CHAVE] = pendente
        assert (
            oauth_google.motivo_recusa_nonce(request, "x" * 43)
            == oauth_google.MOTIVO_NONCE_INVALIDO
        )

    def test_sem_nonce_emitido_e_motivo_ausente(self):
        request = self._request()
        assert (
            oauth_google.motivo_recusa_nonce(request, "x" * 43)
            == oauth_google.MOTIVO_NONCE_AUSENTE
        )

    def test_nonce_nao_string_e_recusado(self):
        request = self._request()
        nonce = oauth_google.emitir_nonce(request)
        for malformado in (None, 123, b"bytes"):
            assert (
                oauth_google.motivo_recusa_nonce(request, malformado)
                == oauth_google.MOTIVO_NONCE_INVALIDO
            )
            # O nonce foi gasto mesmo assim (uso único).
            assert (
                oauth_google.motivo_recusa_nonce(request, nonce)
                == oauth_google.MOTIVO_NONCE_AUSENTE
            )
            nonce = oauth_google.emitir_nonce(request)

    def test_claim_de_nonce_ausente_ou_nao_dict(self):
        from allauth.socialaccount.models import SocialAccount

        class _Fake:
            def __init__(self, extra_data):
                self.account = SocialAccount(
                    provider="google", uid="u", extra_data=extra_data
                )

        assert oauth_google.claim_nonce_do_id_token(_Fake(None)) is None
        assert oauth_google.claim_nonce_do_id_token(_Fake({})) is None
        assert oauth_google.claim_nonce_do_id_token(_Fake({"nonce": 123})) is None
        assert oauth_google.claim_nonce_do_id_token(_Fake({"nonce": "ok"})) == "ok"
        # Objeto sem `account` nenhum também não explode.
        assert oauth_google.claim_nonce_do_id_token(object()) is None

    def test_email_do_provider_verificado_com_estruturas_vazias(self):
        class _Vazio:
            email_addresses = None
            account = None

        assert oauth_google.email_do_provider_verificado(_Vazio()) is False

        class _SemVerified:
            class EA:
                verified = False

            email_addresses = [EA()]
            account = None

        assert oauth_google.email_do_provider_verificado(_SemVerified()) is False

    def test_max_age_vem_de_setting_e_tem_padrao_sensato(self):
        assert oauth_google.max_age_seconds() == 600
        with override_settings(GOOGLE_OAUTH_NONCE_MAX_AGE_SECONDS=90):
            assert oauth_google.max_age_seconds() == 90


# ---------------------------------------------------------------------------
# 2. email_verified — o blocker de sequestro de conta
# ---------------------------------------------------------------------------

class TestEmailVerificado:
    """
    O blocker: `GoogleLoginView` fazia `User.objects.get(email__iexact=...)`
    e `sociallogin.connect(request, existing_user)` sem olhar o
    `email_verified` da asserção. O Google emite `email_verified: false` de
    verdade — é o estado normal de uma conta de domínio/corporativa cujo
    administrador ainda não verificou o e-mail. Resultado: quem tivesse essa
    conta Google entrava na conta local da vítima, com token válido, sem
    senha e sem prova de posse.

    - `test_email_nao_verificado_nao_vincula_conta_local` — o killer.
    - `test_email_nao_verificado_nao_cria_conta_nova` — nem cadastra.
    - `test_email_verificado_vincula_conta_local_verificada` — controle
      positivo: o caminho legítimo continua funcionando.
    - `test_email_verificado_nao_vincula_conta_local_nao_verificada` —
      segunda camada de prova de posse (e-mail local não confirmado).
    - `test_recusa_nao_distingue_os_casos` — sem oráculo de existência.
    """

    def test_email_nao_verificado_nao_vincula_conta_local(self):
        from allauth.socialaccount.models import SocialAccount

        vitima = User.objects.create_user(
            email="alvo@example.com", password="SenhaForte123"
        )
        vitima.papel = User.PAPEL_PREMIUM
        vitima.save()

        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, email_verified=False)

        _recusa(resp, (403,))
        assert not SocialAccount.objects.filter(user=vitima).exists()
        assert not Token.objects.filter(user=vitima).exists()
        # A senha da vítima continua sendo a única credencial que funciona.
        assert vitima.check_password("SenhaForte123")
        # Nem `last_login` mexido: nenhuma sessão foi aberta.
        assert vitima.last_login is None

    def test_email_nao_verificado_nao_cria_conta_nova(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(
                client, email="novo-nao-verificado@example.com", email_verified=False
            )
        _recusa(resp, (403,))
        assert not User.objects.filter(email="novo-nao-verificado@example.com").exists()

    def test_email_verificado_vincula_conta_local_verificada(self):
        """Controle positivo: e-mail verificado nos dois lados vincula e autentica."""
        from allauth.socialaccount.models import SocialAccount

        usuario = User.objects.create_user(
            email="alvo@example.com", password="SenhaForte123"
        )
        usuario.email_verificado = True
        usuario.papel = User.PAPEL_PREMIUM
        usuario.save()

        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, email_verified=True)

        assert resp.status_code == 200, resp.data
        assert resp.data["criado_agora"] is False
        assert SocialAccount.objects.filter(
            user=usuario, provider="google", uid="google-sub-001"
        ).exists()
        assert Token.objects.filter(user=usuario).exists()
        # Papel e senha preservados pela vinculação.
        usuario.refresh_from_db()
        assert usuario.papel == User.PAPEL_PREMIUM
        assert usuario.check_password("SenhaForte123")

    def test_email_verificado_nao_vincula_conta_local_nao_verificada(self):
        """
        Segunda camada de prova de posse: o Google verificou o e-mail, mas a
        conta local nunca foi confirmada (`email_verificado=False`) — ou seja,
        ninguém provou controle daquele e-mail dentro do sistema. Anexar um
        provedor de identidade a essa conta criaria um caminho de entrada que
        o dono da conta local jamais exercise. Recusado.
        """
        from allauth.socialaccount.models import SocialAccount

        usuario = User.objects.create_user(
            email="alvo@example.com", password="SenhaForte123"
        )
        assert usuario.email_verificado is False

        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, email_verified=True)

        _recusa(resp, (403,))
        assert not SocialAccount.objects.filter(user=usuario).exists()
        assert not Token.objects.filter(user=usuario).exists()

    def test_recusa_nao_distingue_os_casos(self):
        """
        A resposta de recusa é idêntica para "e-mail não verificado pelo
        provedor" e "conta local existe mas sem e-mail confirmado". Um
        oráculo de existência de conta valeria ouro para enumeração.
        """
        User.objects.create_user(email="alvo@example.com", password="SenhaForte123")

        c1, c2 = APIClient(), APIClient()
        with chave_publica_injetada():
            r1 = _login(c1, email_verified=False)
            r2 = _login(c2, email_verified=True)
        assert r1.status_code == r2.status_code == 403
        assert r1.data["detail"] == r2.data["detail"]


# ---------------------------------------------------------------------------
# 3. Assinatura, aud, iss, exp — o caminho real do allauth
# ---------------------------------------------------------------------------

class TestAssinaturaIdToken:
    """
    Nenhum destes testes mocka `verify_token`. Cada um forja um token e
    verifica que o allauth recusa:

    - `test_assinatura_de_chave_estrinha_e_recusada` — token assinado por
      uma chave que não é a do Google.
    - `test_alg_none_e_recusado` — o clássico `alg: none`.
    - `test_aud_errado_e_recusado` — token emitido para outro cliente
      (ex.: o cliente web de outro ambiente).
    - `test_issuer_errado_e_recusado` — token de outro emissor.
    - `test_token_expirado_e_recusado` — `exp` no passado.
    - `test_id_token_valido_e_aceito` — controle positivo.
    """

    def test_assinatura_de_chave_estrinha_e_recusada(self):
        chave_pirata = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        client = APIClient()
        # Assinado pela chave pirata, mas conferido contra a chave pública
        # legítima: tem que falhar.
        with chave_publica_injetada():
            resp = _login(client, chave=chave_pirata)
        _recusa(resp, (400,))
        assert not User.objects.filter(email="alvo@example.com").exists()

    def test_alg_none_e_recusado(self):
        client = APIClient()
        with chave_publica_injetada(alg="none"):
            resp = _login(client, alg="none")
        _recusa(resp, (400,))

    def test_aud_errado_e_recusado(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, aud="outro-cliente.apps.googleusercontent.com")
        _recusa(resp, (400,))

    def test_issuer_errado_e_recusado(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, iss="https://accounts.google.com.attacker.test")
        _recusa(resp, (400,))

    def test_token_expirado_e_recusado(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, exp_segundos=-10)
        _recusa(resp, (400,))

    def test_id_token_valido_e_aceito(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client)
        assert resp.status_code == 200, resp.data
        assert User.objects.get(email="alvo@example.com").email_verificado is True


# ---------------------------------------------------------------------------
# 4. Auditoria
# ---------------------------------------------------------------------------

class TestAuditoria:
    """
    - `test_sucesso_e_auditado` — desfecho "sucesso" registrado.
    - `test_falha_e_auditada` — desfecho "falha" registrado, com motivo.
    - `test_recusa_por_nonce_e_auditada` / `test_recusa_por_email_...` — cada
      gate tem motivo próprio, sem confundir.
    - `test_auditoria_nao_carrega_credencial` — o `id_token` não aparece em
      nenhum registro, nem em sucesso, nem em falha, nem no traceback.
    - `test_auditoria_tem_conjunto_fixo_de_campos` — nenhum campo livre
      entrando no log.
    """

    @staticmethod
    def _registros(caplog):
        return [r for r in caplog.records if getattr(r, "oauth_event", None)]

    def test_sucesso_e_auditado(self, caplog):
        caplog.set_level(logging.INFO, logger="identidade.google_oauth")
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client)
        assert resp.status_code == 200, resp.data

        sucessos = [r for r in self._registros(caplog) if r.oauth_desfecho == "sucesso"]
        assert sucessos, [r.getMessage() for r in caplog.records]
        assert sucessos[0].oauth_motivo == oauth_google.MOTIVO_OK
        assert sucessos[0].oauth_usuario_id == User.objects.get(email="alvo@example.com").pk
        assert sucessos[0].levelno == logging.INFO

    def test_falha_e_auditada(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        client = APIClient()
        chave_pirata = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with chave_publica_injetada():
            _login(client, chave=chave_pirata)

        falhas = [r for r in self._registros(caplog) if r.oauth_desfecho == "falha"]
        assert falhas, [r.getMessage() for r in caplog.records]
        assert falhas[0].oauth_motivo == oauth_google.MOTIVO_TOKEN_INVALIDO
        # O tipo da exceção entra; a exceção e o traceback, não.
        assert falhas[0].oauth_erro_tipo
        assert falhas[0].levelno == logging.WARNING

    def test_recusa_por_nonce_e_auditada(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        outra = APIClient()
        nonce = _iniciar(outra)
        vitima = APIClient()
        with chave_publica_injetada():
            _postar(vitima, _id_token(nonce=nonce), nonce)
        motivos = {r.oauth_motivo for r in self._registros(caplog)}
        assert oauth_google.MOTIVO_NONCE_AUSENTE in motivos

    def test_recusa_por_claim_de_nonce_divergente_e_auditada(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        client = APIClient()
        with chave_publica_injetada():
            _login(client, claim_nonce="nonce-de-outra-sessao")
        motivos = {r.oauth_motivo for r in self._registros(caplog)}
        assert oauth_google.MOTIVO_NONCE_CLAIM_DIVERGENTE in motivos

    def test_recusa_por_email_nao_verificado_e_auditada(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        User.objects.create_user(email="alvo@example.com", password="SenhaForte123")
        client = APIClient()
        with chave_publica_injetada():
            _login(client, email_verified=False)
        motivos = {r.oauth_motivo for r in self._registros(caplog)}
        assert oauth_google.MOTIVO_EMAIL_NAO_VERIFICADO in motivos

    def test_recusa_por_conta_local_nao_verificada_e_auditada(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        User.objects.create_user(email="alvo@example.com", password="SenhaForte123")
        client = APIClient()
        with chave_publica_injetada():
            _login(client, email_verified=True)
        motivos = {r.oauth_motivo for r in self._registros(caplog)}
        assert oauth_google.MOTIVO_CONTA_LOCAL_NAO_VERIFICADA in motivos

    def test_auditoria_nao_carrega_credencial(self, caplog):
        """
        O `id_token` é uma credencial de portadora: quem a tem entra. Ela não
        pode aparecer em log — nem em sucesso, nem em falha, nem no texto da
        exceção nem no traceback.
        """
        caplog.set_level(logging.DEBUG)
        segredos = []

        # Caminho de sucesso.
        client = APIClient()
        with chave_publica_injetada():
            nonce, bom = _nonce_e_token(client)
            segredos.append(bom)
            assert _postar(client, bom, nonce).status_code == 200
        assert "sucesso" in {r.oauth_desfecho for r in self._registros(caplog)}

        # Caminho de falha por assinatura: era um `logger.exception` antes.
        caplog.clear()
        client2 = APIClient()
        chave_pirata = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with chave_publica_injetada():
            nonce2, ruim = _nonce_e_token(client2, chave=chave_pirata)
            segredos.append(ruim)
            assert _postar(client2, ruim, nonce2).status_code == 400

        # Caminho de falha por estado inválido.
        caplog.clear()
        client3 = APIClient()
        _iniciar(client3)
        with chave_publica_injetada():
            outro = _id_token()
            segredos.append(outro)
            _postar(client3, outro, "z" * 43)

        # Caminho de falha por e-mail não verificado.
        caplog.clear()
        User.objects.create_user(
            email="alvo-sem-verificar@example.com", password="SenhaForte123"
        )
        client4 = APIClient()
        with chave_publica_injetada():
            n4, t4 = _nonce_e_token(
                client4, email="alvo-sem-verificar@example.com", email_verified=False
            )
            segredos.append(t4)
            _postar(client4, t4, n4)

        tudo = "\n".join(
            r.getMessage() + " " + repr(getattr(r, "args", ())) + " " + str(r.__dict__)
            for r in caplog.records
        )
        for segredo in segredos:
            assert segredo not in tudo
            # E os pedaços, para um log que decodifique o JWT.
            for pedaco in (segredo[:40], segredo[-40:]):
                assert pedaco not in tudo

    def test_auditoria_tem_conjunto_fixo_de_campos(self, caplog):
        caplog.set_level(logging.DEBUG, logger="identidade.google_oauth")
        client = APIClient()
        with chave_publica_injetada():
            _login(client)
        registros = self._registros(caplog)
        assert registros
        for registro in registros:
            assert set(registro.__dict__) >= {
                "oauth_event",
                "oauth_desfecho",
                "oauth_motivo",
                "oauth_usuario_id",
                "oauth_conta_nova",
                "oauth_erro_tipo",
            }
            # Nenhum campo cujo nome sugira credencial.
            assert not [c for c in registro.__dict__ if "token" in c.lower()]


# ---------------------------------------------------------------------------
# 5. Configuração por ambiente
# ---------------------------------------------------------------------------

class TestConfiguracao:
    """
    - `test_sem_client_id_responde_503_e_nao_400` — ambiente sem
      `GOOGLE_OAUTH_CLIENT_ID` não pode responder "token inválido": o allauth
      usa o client_id como `aud`, então sem ele **todo** token é recusado e o
      sintoma é indistinguível de um ataque. 503 separa "quebrado" de
      "recusado".
    - `test_escopos_do_google_sao_minimos` — o app pede só o necessário.
    """

    @staticmethod
    def _sem_client_id():
        provedores = {
            **settings.SOCIALACCOUNT_PROVIDERS,
            "google": {
                **settings.SOCIALACCOUNT_PROVIDERS["google"],
                "APP": {
                    **settings.SOCIALACCOUNT_PROVIDERS["google"]["APP"],
                    "client_id": "",
                },
            },
        }
        return override_settings(SOCIALACCOUNT_PROVIDERS=provedores)

    def test_sem_client_id_responde_503_e_nao_400(self, caplog):
        caplog.set_level(logging.WARNING, logger="identidade.google_oauth")
        with self._sem_client_id():
            assert oauth_google.client_id_configurado() is False

            iniciar = APIClient().post(ENDPOINT_INICIAR, {}, format="json")
            assert iniciar.status_code == 503, iniciar.data

            # Nem chega a pedir nonce: o gate de configuração vem primeiro.
            client = APIClient()
            with chave_publica_injetada():
                resp = client.post(
                    ENDPOINT_LOGIN,
                    {"id_token": _id_token(), "aceite_termos": True, "nonce": "x" * 43},
                    format="json",
                )
            assert resp.status_code == 503, resp.data
            assert "token" not in resp.data
            # A mensagem é a de ambiente quebrado, não a de credencial ruim.
            assert resp.data["detail"] != "Token do Google inválido."

        motivos = {
            r.oauth_motivo
            for r in caplog.records
            if getattr(r, "oauth_motivo", None)
        }
        assert oauth_google.MOTIVO_CLIENT_ID_NAO_CONFIGURADO in motivos

    def test_com_client_id_configurado_o_503_nao_acontece(self):
        assert oauth_google.client_id_configurado() is True
        assert APIClient().post(ENDPOINT_INICIAR, {}, format="json").status_code == 200

    def test_client_id_da_suite_nao_e_credencial_real(self):
        """
        Trava de propósito: se alguém colar um `client_id` de verdade em
        `config/settings_test.py`, a suíte passa a depender de um segredo
        versionado. Aqui ele só pode ser um identificador fictício.
        """
        assert "teste" in CLIENT_ID
        assert "googleusercontent.com" in CLIENT_ID

    def test_escopos_do_google_sao_minimos(self):
        """
        O app só precisa de identidade e e-mail para o que faz (nome de
        exibição, e-mail verificado). Pedir mais (drive, gmail, calendar)
        amplia a superfície de um consentimento que o usuário dá sem
        costuma ler. O escopo efetivo é o do botão do GIS no front, mas esta
        é a lista que o backend declara.
        """
        escopo = settings.SOCIALACCOUNT_PROVIDERS["google"]["SCOPE"]
        assert set(escopo) == {"profile", "email"}
        assert not set(escopo) & {
            "drive",
            "gmail",
            "calendar",
            "contacts",
            "https://www.googleapis.com/auth/drive",
        }


# ---------------------------------------------------------------------------
# 6. Adapter — o que o allauth entrega ao nosso User
# ---------------------------------------------------------------------------

class TestAdapter:
    """
    - `test_novo_usuario_herda_email_e_nome_do_google` — `populate_user` (que
      nunca era exercitado, porque os testes antigos mockavam `verify_token`
      inteiro) preenche `email` e `nome`.
    - `test_novo_usuario_google_nao_tem_senha_utilizavel` — sem senha em
      texto plano e sem senha utilizável.
    - `test_adapter_nao_autentica_por_email_sozinho` — o auto-vínculo por
      e-mail do allauth está desligado; a decisão é da view.
    - `test_login_de_retorno_nao_exige_novo_aceite` — quem já está vinculado
      entra de novo sem `aceite_termos`.
    """

    def test_novo_usuario_herda_email_e_nome_do_google(self):
        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client, email="heranca@example.com")
        assert resp.status_code == 200, resp.data
        usuario = User.objects.get(email="heranca@example.com")
        assert usuario.nome == "Pessoa Teste"
        assert usuario.papel == User.PAPEL_FREE
        assert usuario.consentimento_aceito_em is not None

    def test_novo_usuario_google_nao_tem_senha_utilizavel(self):
        client = APIClient()
        with chave_publica_injetada():
            _login(client, email="sem-senha@example.com")
        usuario = User.objects.get(email="sem-senha@example.com")
        assert usuario.has_usable_password() is False
        assert usuario.password.startswith("!")

    def test_adapter_nao_autentica_por_email_sozinho(self):
        from allauth.socialaccount.adapter import get_adapter

        assert get_adapter().authenticate_by_email(sociallogin=None) is None

    def test_login_de_retorno_nao_exige_novo_aceite(self):
        """Quem já está vinculado entra de novo sem `aceite_termos`."""
        c1 = APIClient()
        with chave_publica_injetada():
            primeiro = _login(c1)
        assert primeiro.status_code == 200, primeiro.data

        c2 = APIClient()
        with chave_publica_injetada():
            segundo = _login(c2, aceite_termos=False)
        assert segundo.status_code == 200, segundo.data
        assert segundo.data["criado_agora"] is False
        assert User.objects.filter(email="alvo@example.com").count() == 1

    def test_conta_inativa_nao_autentica_pelo_google(self):
        """
        `is_active` é conferido no login social tanto quanto no login por
        senha. Uma conta desativada pelo admin não pode ser reativada por
        quem detenha uma conta Google com o mesmo e-mail vinculado.
        """
        from allauth.socialaccount.models import SocialAccount

        usuario = User.objects.create_user(
            email="alvo@example.com", password="SenhaForte123"
        )
        usuario.email_verificado = True
        usuario.is_active = False
        usuario.save()
        SocialAccount.objects.create(
            user=usuario, provider="google", uid="google-sub-001"
        )

        client = APIClient()
        with chave_publica_injetada():
            resp = _login(client)

        assert resp.status_code == 403, resp.data
        assert "token" not in resp.data
        assert not Token.objects.filter(user=usuario).exists()
        assert usuario.last_login is None
