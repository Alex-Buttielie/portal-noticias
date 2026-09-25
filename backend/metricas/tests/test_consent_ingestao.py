"""Consentimento de analytics no endpoint público: fail-closed de verdade.

Cobre os critérios 25, 26 e 28 (implementation-contract.md, run
20260925-1020-observabilidade): payload com tipo desconhecido, campo em excesso
ou dado pessoal é rejeitado/redigido com sinal técnico, e token ausente,
inválido ou expirado NÃO vira dado de produto autorizado.

Regressão que este arquivo existe para impedir: até o Bloco A2 o
`POST /api/metricas/eventos/` persistia o evento sem conferir token nenhum,
mesmo com `ANALYTICS_REQUIRE_CONSENT_TOKEN=True` (fail-open — o controle de
privacidade era decorativo). `test_token_ausistente_nao_persiste` falha se a
verificação for removida.
"""

from __future__ import annotations

import json
import logging
import time

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from config.metrics import METRICS
from metricas import consent
from metricas.models import EventoSite

pytestmark = pytest.mark.django_db

CHAVE = "chave-de-teste-a-nao-usar-em-producao-0123456789"
SUB = "sessao-teste-01"
URL = "/api/metricas/eventos/"
EMAIL = "leitor.exemplo@dominio.invalid"


@pytest.fixture(autouse=True)
def _consentimento_por_padrao():
    """Todo o módulo roda com a chave de teste: o `.env` local não tem
    `ANALYTICS_CONSENT_SIGNING_KEY`, e sem o override o token cairia na
    SECRET_KEY (o que tornaria a suíte dependente de configuração externa)."""

    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=CHAVE,
        ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS="",
        ANALYTICS_REQUIRE_CONSENT_TOKEN=True,
    ):
        yield


def _token(sub: str = SUB, **kwargs) -> str:
    return consent.gerar_token_consent(sub=sub, **kwargs)


def _evento(**extra):
    corpo = {"tipo": "page_view", "path": "/", "sessao": SUB, "origem": "direto"}
    corpo.update(extra)
    return corpo


def _post(corpo: dict, token: str | None = None, no_header: bool = False):
    """POST com o token no header (caminho preferido) ou no corpo (beacon)."""

    client = APIClient()
    headers = {}
    if token and not no_header:
        headers["HTTP_X_CONSENT_TOKEN"] = token
    return client.post(URL, corpo, format="json", **headers)


# ---------------------------------------------------------------------------
# Caminho feliz: consentimento válido persiste
# ---------------------------------------------------------------------------


def test_token_valido_persiste_o_evento():
    resposta = _post(_evento(), token=_token())

    assert resposta.status_code == 201
    assert resposta.data["registrado"] is True
    assert EventoSite.objects.filter(tipo="page_view", sessao=SUB).count() == 1


def test_token_valido_tambem_via_campo_no_corpo_para_sendbeacon():
    """`navigator.sendBeacon` não envia header: o campo é o caminho do beacon."""

    resposta = _post(_evento(consent_token=_token()))

    assert resposta.status_code == 201
    assert EventoSite.objects.filter(tipo="page_view", sessao=SUB).count() == 1


def test_token_do_corpo_nao_vira_coluna_do_evento():
    """O transporte do token não pode acabar persistido como atributo do evento."""

    _post(_evento(consent_token=_token()))

    evento = EventoSite.objects.get(tipo="page_view")
    bruto = json.dumps(
        {campo.name: str(getattr(evento, campo.name)) for campo in EventoSite._meta.fields}
    )
    assert _token() not in bruto
    assert "consent_token" not in bruto


def test_contador_de_aceite_nao_e_incrementado_em_token_invalido():
    """Aceite e recusa precisam ser distinguíveis em `/metrics`."""

    METRICS.clear()
    _post(_evento(), token=_token())
    _post(_evento(), token=_token()[:-6] + "AAAAAA")
    exposicao = METRICS.render_prometheus()

    assert 'portal_analytics_events_rejected_total{reason="assinatura_invalida"}' in exposicao
    assert "portal_analytics_consent_rejections_total" in exposicao


# ---------------------------------------------------------------------------
# Regressão: sem token (ou com token ruim) nada é persistido
# ---------------------------------------------------------------------------


def test_token_ausistente_nao_persiste():
    """REGRESSÃO do fail-open: era isto que permitia coletar sem consentimento."""

    resposta = _post(_evento())

    assert resposta.status_code == 202
    assert resposta.data == {"registrado": False, "motivo": "consent_ausente"}
    assert EventoSite.objects.count() == 0


@pytest.mark.parametrize(
    "token,motivo",
    [
        pytest.param("", "consent_ausente", id="vazio"),
        pytest.param("   ", "consent_ausente", id="branco"),
        pytest.param("lixo", "consent_malformado", id="malformado"),
        pytest.param("v1.a.b", "consent_malformado", id="partes-invalidas"),
        pytest.param("v1.@@@.@@@", "consent_malformado", id="base64-invalido"),
        pytest.param("x" * 4_000, "consent_token_grande", id="absurdamente-longo"),
    ],
)
def test_token_ausente_ou_malformado_nao_persiste(token, motivo):
    resposta = _post(_evento(), token=token)

    assert resposta.status_code == 202
    assert resposta.data["registrado"] is False
    assert resposta.data["motivo"] == motivo
    assert EventoSite.objects.count() == 0


def test_token_expirado_nao_persiste():
    token = _token(ttl_seconds=120, agora=int(time.time()) - 3_600)

    resposta = _post(_evento(), token=token)

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "consent_expirado"
    assert EventoSite.objects.count() == 0


def test_assinatura_invalida_nao_persiste():
    """Alguém que monte o token à mão, sem a chave, não ganha evento."""

    resposta = _post(_evento(), token=_token()[:-6] + "AAAAAA")

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "consent_assinatura_invalida"
    assert EventoSite.objects.count() == 0


def test_payload_adulterado_com_reassinatura_nao_persiste():
    """Trocar `sub`/`categoria` e re-assinar com outra chave é a forja completa."""

    import base64
    import hashlib
    import hmac

    agora = int(time.time())
    claims = {"v": 1, "categoria": "analytics", "iat": agora, "exp": agora + 86_400, "sub": SUB}
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    assinatura = (
        base64.urlsafe_b64encode(
            hmac.new(b"chave-do-atacante", f"v1.{payload}".encode("ascii"), hashlib.sha256).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )

    resposta = _post(_evento(), token=f"v1.{payload}.{assinatura}")

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "consent_assinatura_invalida"
    assert EventoSite.objects.count() == 0


def test_token_de_categoria_tecnica_nao_persiste():
    """`analytics` ≠ `technical`: o consentimento técnico não abre o de produto."""

    import base64
    import hashlib
    import hmac

    agora = int(time.time())
    claims = {
        "v": 1,
        "categoria": "technical",
        "iat": agora,
        "exp": agora + 86_400,
        "sub": SUB,
    }
    payload = (
        base64.urlsafe_b64encode(
            json.dumps(claims, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        .decode("ascii")
        .rstrip("=")
    )
    assinatura = (
        base64.urlsafe_b64encode(
            hmac.new(CHAVE.encode("utf-8"), f"v1.{payload}".encode("ascii"), hashlib.sha256).digest()
        )
        .decode("ascii")
        .rstrip("=")
    )

    resposta = _post(_evento(), token=f"v1.{payload}.{assinatura}")

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "consent_categoria_invalida"
    assert EventoSite.objects.count() == 0


def test_token_de_outra_sessao_nao_persiste():
    """Token é ligado ao sujeito: não é um bem público reutilizável."""

    resposta = _post(_evento(sessao="outra-sessao-77"), token=_token())

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "consent_sujeito_invalido"
    assert EventoSite.objects.count() == 0


@pytest.mark.parametrize("sessao", [None, "", "s1", "ç", "  "])
def test_sessao_ausente_ou_invalida_adota_o_sujeito_do_token(sessao):
    """Quem manda na sessão é o TOKEN, não o que o cliente alegou.

    Um cliente que manda id curto/inválido continua sendo registrado (o evento
    não se perde), e um cliente que inventa a sessão de outro não consegue
    poluir a sessão alheia: a alegação é descartada em favor do sujeito
    assinado. Já uma sessão VÁLIDA e diferente da do token é recusada (teste
    anterior) — são dois controles distintos e complementares.
    """

    corpo = _evento() if sessao is None else _evento(sessao=sessao)

    resposta = _post(corpo, token=_token())

    assert resposta.status_code == 201
    assert EventoSite.objects.get(tipo="page_view").sessao == SUB


def test_evento_roteado_para_o_feed_tambem_exige_consentimento():
    """`search`/`news_view` escrevem em `feed.*`, não em `EventoSite`: a
    checagem tem que ser ANTES do roteamento, não dentro de uma das rotas."""

    from django.test import override_settings as _override

    with _override(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True):
        sem_token = _post({"tipo": "search", "termo": "agronegócio", "sessao": SUB})
        com_token = _post(
            {"tipo": "search", "termo": "agronegócio", "sessao": SUB}, token=_token()
        )

    from feed.models import EventoBusca

    assert sem_token.status_code == 202
    assert com_token.status_code == 201
    assert EventoBusca.objects.count() == 1


def test_rotacao_de_chave_invalida_o_token_publicado_quando_a_chave_sai():
    """Revogação real: com a chave antiga fora da lista, o token morre."""

    antiga = "chave-antiga-de-teste-nao-usar-0123456789"
    nova = "chave-nova-de-teste-nao-usar-0123456789abcde"
    with override_settings(ANALYTICS_CONSENT_SIGNING_KEY=antiga):
        antigo = _token()
        publicado = _post(_evento(), token=antigo)

    # Durante a janela de rotação, o token já no navegador continua valendo.
    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=nova, ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS=antiga
    ):
        ainda_valido = _post(_evento(), token=antigo)

    # Depois de a chave antiga sair da lista: revogação.
    with override_settings(
        ANALYTICS_CONSENT_SIGNING_KEY=nova, ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS=""
    ):
        revogado = _post(_evento(), token=antigo)

    assert publicado.status_code == 201
    assert ainda_valido.status_code == 201
    assert revogado.status_code == 202
    assert revogado.data["motivo"] == "consent_assinatura_invalida"
    assert EventoSite.objects.count() == 2


# ---------------------------------------------------------------------------
# Sinal técnico das recusas
# ---------------------------------------------------------------------------


def test_recusa_registra_motivo_e_tipo_no_log_sem_carregar_token_nem_payload(caplog):
    caplog.set_level(logging.INFO, logger="metricas.consent")
    token = _token()[:-6] + "AAAAAA"

    _post(_evento(path=f"/politica?utm=leitor", extra={"contato": EMAIL}), token=token)

    registro = next(r for r in caplog.records if "NÃO persistido" in r.getMessage())
    texto = registro.getMessage()
    assert "consent_ausente" not in texto  # o motivo vem sem o prefixo da resposta
    assert "motivo=assinatura_invalida" in texto
    assert "tipo=page_view" in texto
    # Nem o token, nem o path/query, nem o e-mail do payload entram no log.
    for pii in (token, "leitor@", EMAIL, "politica", "utm"):
        assert pii not in texto


def test_recusa_gera_metrica_com_o_motivo():
    METRICS.clear()

    _post(_evento())

    exposicao = METRICS.render_prometheus()
    assert 'portal_analytics_consent_rejections_total{origin="evento",reason="ausente"}' in exposicao
    assert 'portal_analytics_events_rejected_total{reason="ausente"}' in exposicao


# ---------------------------------------------------------------------------
# Flag desligado (uso local) — caminho legado, mas nunca silencioso
# ---------------------------------------------------------------------------


@override_settings(ANALYTICS_REQUIRE_CONSENT_TOKEN=False)
def test_flag_desligado_mantem_o_caminho_legado_mas_deixa_visivel(caplog):
    caplog.set_level(logging.WARNING, logger="metricas.consent")
    METRICS.clear()

    resposta = _post(_evento())

    assert resposta.status_code == 201
    assert EventoSite.objects.filter(tipo="page_view", sessao=SUB).count() == 1
    # Visível em métrica E em log: bypass silencioso é o pior dos dois mundos
    # (alguém acharia que o consentimento está valendo).
    assert "portal_analytics_consent_bypass_total 1" in METRICS.render_prometheus()
    assert "ANALYTICS_REQUIRE_CONSENT_TOKEN está desligado" in caplog.text


@override_settings(ANALYTICS_REQUIRE_CONSENT_TOKEN=False)
def test_flag_desligado_ainda_redige_o_payload():
    """Desligar a validação não abre a porta para dado pessoal."""

    _post(_evento(extra={"contato": EMAIL, "email": EMAIL, "ok": 1}))

    bruto = json.dumps(EventoSite.objects.get(tipo="page_view").extra)
    assert EMAIL not in bruto
    assert '"ok": 1' in bruto


# ---------------------------------------------------------------------------
# Critério 25: tipo desconhecido, campo em excesso, dado pessoal
# ---------------------------------------------------------------------------


def test_tipo_desconhecido_e_recusado_com_sinal_tecnico():
    METRICS.clear()

    resposta = _post(_evento(tipo="invasao_alien"), token=_token())

    assert resposta.status_code == 400
    assert resposta.data["motivo"] == "tipo_desconhecido"
    assert EventoSite.objects.count() == 0
    assert 'portal_analytics_events_rejected_total{reason="tipo_desconhecido"}' in (
        METRICS.render_prometheus()
    )


def test_tipo_desconhecido_nao_e_refletido_na_resposta():
    """Ecoar o input do cliente em resposta pública é superfície de XSS/reflected
    e não ajuda ninguém: o cliente já sabe o que mandou."""

    resposta = _post(_evento(tipo="<script>alert(1)</script>"), token=_token())

    assert resposta.status_code == 400
    assert "<script>" not in json.dumps(resposta.data)


def test_campo_em_excesso_e_descartado_e_nao_persiste():
    METRICS.clear()

    resposta = _post(
        _evento(cpf="123.456.789-00", email=EMAIL, authorization="Bearer segredo"),
        token=_token(),
    )

    assert resposta.status_code == 201
    evento = EventoSite.objects.get(tipo="page_view")
    bruto = json.dumps({c.name: str(getattr(evento, c.name)) for c in EventoSite._meta.fields})
    for vazamento in ("123.456.789-00", EMAIL, "segredo", "cpf", "email", "authorization"):
        assert vazamento not in bruto
    exposicao = METRICS.render_prometheus()
    assert "portal_analytics_payload_fields_dropped_total" in exposicao
    # Achado MINOR-6: campo em excesso NÃO é "evento rejeitado" — o evento é
    # persistido (201). Contar recusa aqui fazia o alerta de "eventos rejeitados"
    # disparar com eventos sendo aceitos.
    assert "portal_analytics_events_rejected_total" not in exposicao


def test_dado_pessoal_em_extra_e_redigido_e_nao_chega_ao_banco():
    resposta = _post(
        _evento(extra={"contato": EMAIL, "token": "abc123", "ok": 1, "url": "https://x.invalid/?t=1"}),
        token=_token(),
    )

    assert resposta.status_code == 201
    bruto = json.dumps(EventoSite.objects.get(tipo="page_view").extra)
    assert EMAIL not in bruto
    assert "abc123" not in bruto
    assert bruto.count("[REDACTED]") >= 2
    assert '"ok": 1' in bruto  # o que não é sensível sobrevive


def test_query_string_do_path_nao_e_persistida():
    """Critério 28: query string é onde moram `utm`, busca e, às vezes, PII."""

    _post(_evento(path="/politica?utm_source=newsletter&email=" + EMAIL), token=_token())

    evento = EventoSite.objects.get(tipo="page_view")
    assert evento.path == "/politica"
    assert "utm" not in evento.path and EMAIL not in evento.path


@pytest.mark.parametrize("campo_extra", ["termo", "query", "categoria", "autor_ref"])
def test_termo_de_busca_com_pii_e_redigido_antes_de_ir_para_o_evento_de_busca(campo_extra):
    """O termo buscado é o produto (termos populares), mas também é o que uma
    pessoa digita: e-mail/CPF/token que aparecer nele é redigido antes do
    enfileiramento."""

    corpo = _evento(tipo="search", resultado=0, **{campo_extra: f"contato {EMAIL}"})
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True):
        resposta = _post(corpo, token=_token())

    from feed.models import EventoBusca

    assert resposta.status_code == 201
    assert EventoBusca.objects.count() == 1
    assert EMAIL not in EventoBusca.objects.get().query


def test_filtros_de_busca_passam_pela_redaction():
    with override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True):
        _post(
            _evento(
                tipo="search",
                termo="porto",
                filtros={"email": EMAIL, "origem": "newsletter"},
            ),
            token=_token(),
        )

    from feed.models import EventoBusca

    filtros = json.dumps(EventoBusca.objects.get().filtros or {})
    assert EMAIL not in filtros
    assert "newsletter" in filtros  # filtro legítimo sobrevive


def test_payload_absurdamente_grande_e_recusado():
    METRICS.clear()

    resposta = _post(_evento(categoria="x" * 5_000), token=_token())

    assert resposta.status_code == 202
    assert resposta.data["motivo"] == "payload_grande"
    assert EventoSite.objects.count() == 0


def test_corpo_com_muitos_campos_desconhecidos_e_recusado():
    corpo = _evento(**{f"invaso_{i}": "x" for i in range(consent.MAX_CAMPOS_INSPECIONADOS + 5)})

    resposta = _post(corpo, token=_token())

    assert resposta.status_code == 202
    assert EventoSite.objects.count() == 0


def test_corpo_nao_dict_nao_quebra():
    """Robustez: um `POST` com lista/string no lugar do objeto não pode virar 500."""

    client = APIClient()
    assert client.post(URL, ["a", "b"], format="json").status_code in {202, 400}
    assert client.post(URL, "texto", format="json").status_code in {202, 400}
    assert EventoSite.objects.count() == 0


def test_sem_tipo_continua_sendo_erro_de_cliente_e_nao_vira_500():
    resposta = _post({"sessao": SUB}, token=_token())

    assert resposta.status_code == 400


# ---------------------------------------------------------------------------
# Emissão do token
# ---------------------------------------------------------------------------


def test_emissao_devolve_token_que_o_endpoint_aceita():
    client = APIClient()

    emissao = client.post("/api/metricas/consent/", {"sessao": SUB}, format="json")

    assert emissao.status_code == 201
    assert emissao.data["categoria"] == "analytics"
    assert emissao.data["ttl_segundos"] == 86_400
    assert emissao.data["exp"] > time.time()
    assert _post(_evento(), token=emissao.data["token"]).status_code == 201


def test_emissao_exige_sessao_valida_e_recusa_categoria_tecnica():
    client = APIClient()

    assert client.post("/api/metricas/consent/", {}, format="json").status_code == 400
    assert (
        client.post(
            "/api/metricas/consent/", {"sessao": SUB, "categoria": "technical"}, format="json"
        ).status_code
        == 400
    )


def test_recusa_na_emissao_vai_para_log_e_metrica(caplog):
    """Recusa do emissor é rara (erro de cliente/config): tem de aparecer, senão
    um consentimento quebrado vira 'ninguém nunca pediu token'."""

    caplog.set_level(logging.WARNING, logger="metricas.consent")
    METRICS.clear()

    APIClient().post(
        "/api/metricas/consent/", {"sessao": SUB, "categoria": "technical"}, format="json"
    )

    assert "token de consentimento NÃO emitido (motivo=categoria_invalida)" in caplog.text
    assert (
        'portal_analytics_consent_rejections_total{origin="token",reason="categoria_invalida"}'
        in METRICS.render_prometheus()
    )


def test_emissao_sem_chave_responde_503_e_nao_quebra(monkeypatch):
    """Configuração quebrada é erro de configuração, não motivo para aceitar
    token de qualquer jeito — e não pode virar 500.

    O patch é na função de leitura da chave (e não em `SECRET_KEY=""`) porque o
    próprio Django se recusa a subir com `SECRET_KEY` vazia: o cenário real de
    "nenhuma chave" é um deploy com as duas settings vazias, que nem chega ao
    Django. O que importa aqui é o comportamento do endpoint diante de um
    `sem_chave`.
    """

    monkeypatch.setattr(consent, "_chave_ativa", lambda: "")

    resposta = APIClient().post("/api/metricas/consent/", {"sessao": SUB}, format="json")

    assert resposta.status_code == 503
    assert resposta.data == {"detail": "Consentimento indisponível."}


def test_emissao_esta_limitada_por_throttle(settings):
    """O emissor é público e barato: sem teto vira coleta de dados em massa.

    O limite vem da configuração real (`THROTTLE_CONSENTIMENTO_RATE`), lida
    aqui em vez de hardcodada, como `config/tests/test_throttling.py` faz com
    os demais escopos.
    """

    from django.core.cache import cache

    from config.settings import REST_FRAMEWORK

    limite = int(REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["consentimento"].partition("/")[0])
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    client = APIClient()
    codigos = [
        client.post("/api/metricas/consent/", {"sessao": SUB}, format="json").status_code
        for _ in range(limite + 2)
    ]

    assert 429 not in codigos[:limite], f"throttle antes do limite: {codigos}"
    assert codigos[limite:] == [429, 429]
    assert "Retry-After" in client.post(
        "/api/metricas/consent/", {"sessao": SUB}, format="json"
    ).headers
    cache.clear()


def test_emissao_nao_e_contornavel_girando_x_forwarded_for(settings):
    """Regressão do achado MAJOR-1: este teto era decorativo.

    O `SimpleRateThrottle.get_ident` do DRF usa o `X-Forwarded-For` cru quando
    `NUM_PROXIES` não está configurado, e os nginx versionados não definem esse
    header — então o balde era escolhido pelo cliente. 40 POSTs com o header
    rotacionado contra o teto de 30/min devolviam 40×`201` e zero `429`, que é
    exatamente o "script de coleta de dados com o carimbo do próprio site" que o
    limite existe para impedir.

    Aqui o par (`REMOTE_ADDR`) é externo e não declarado como proxy, então o
    header não pode influenciar o balde: o limite precisa valer.
    """

    from django.core.cache import cache

    from config.settings import REST_FRAMEWORK

    limite = int(REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["consentimento"].partition("/")[0])
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    cache.clear()
    client = APIClient()
    codigos = [
        client.post(
            "/api/metricas/consent/",
            {"sessao": SUB},
            format="json",
            REMOTE_ADDR="203.0.113.10",
            HTTP_X_FORWARDED_FOR=f"10.0.0.{indice}",
        ).status_code
        for indice in range(limite + 10)
    ]

    assert 429 not in codigos[:limite], f"throttle antes do limite: {codigos}"
    assert codigos.count(429) == len(codigos) - limite, codigos
    cache.clear()


def test_emissao_respeita_o_teto_por_cliente_atras_de_proxy_declarado(settings):
    """O outro lado da moeda: a correção não pode transformar o limite em
    "30/min para o site inteiro". Com o proxy declarado, cada cliente real tem
    o seu balde — e o mesmo cliente continua sendo barrado."""

    from django.core.cache import cache

    from config.settings import REST_FRAMEWORK

    limite = int(REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["consentimento"].partition("/")[0])
    settings.CACHES = {
        "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    }
    settings.OBSERVABILITY_TRUSTED_PROXY_NETWORKS = "172.18.0.0/16"
    cache.clear()
    client = APIClient()

    def _pede(indice_cliente: int) -> int:
        return client.post(
            "/api/metricas/consent/",
            {"sessao": SUB},
            format="json",
            REMOTE_ADDR="172.18.0.9",
            # O proxy ANEXA o cliente real no fim da cadeia (default do Nginx).
            HTTP_X_FORWARDED_FOR=f"198.51.100.{indice_cliente}",
        ).status_code

    # Três clientes distintos, cada um no seu balde.
    assert [_pede(10), _pede(11), _pede(12)] == [201, 201, 201]
    # O mesmo cliente esgota o PRÓPRIO teto (a primeira requisição acima já
    # consumiu uma das `limite` vagas).
    codigos = [_pede(10) for _ in range(limite - 1)]
    assert 429 not in codigos
    assert _pede(10) == 429
    # E o outro cliente continua com o balde intacto.
    assert _pede(11) == 201
    cache.clear()
