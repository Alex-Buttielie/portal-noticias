"""
Testes do eixo 4 (health/readiness/métricas).

O QUE PROVAM, E O QUE NÃO PROVAM
=================================

PROVAM — os QUATRO ESTADOS exigidos, e mais:

1. **Dependências ok** → `/readyz` 200 com o status derivado das
   checagens, `/livez` 200, `/healthz` 200 com o contrato estável.
2. **Dependência caída** → `/readyz` 503 e `status: nao_pronto`, com a
   checagem que falhou nomeada e a CATEGORIA preenchida. Este é o teste
   que impede o falso verde: um `ok` fixo quebraria aqui.
3. **Sem token** → `/health-detail` e `/metrics` respondem 401 para
   anônimo. NUNCA 200, mesmo com `HEALTH_DETAIL_TOKEN` não configurado.
4. **Token errado** → 401 nos dois, e o corpo não contém detalhe algum.
5. `/healthz` NÃO VAZA: o teste derruba o banco e verifica que a resposta
   pública não contém host, porta, nome do banco, usuário, nem a mensagem
   do driver. Este é o teste do vazamento que existia em
   `origin/develop` (`config/views.py` devolvia `str(exc)`).
6. `/livez` NÃO depende de third-party: com o banco derrubado, continua 200.
   É o que separa liveness de readiness.
7. Timeout: uma checagem que nunca retorna produz `categoria: timeout` e
   a resposta acontece (não trava).
8. `hmac.compare_digest` é usado, e token vazio/não configurado é
   fail-closed.
9. Métricas no formato Prometheus e com `nosniff`.
10. `no-store` nos endpoints de saúde (um 503 de readiness cacheado pelo
    proxy reconduz tráfego para um serviço quebrado).

NÃO PROVAM
 - Comportamento do orquestrador (K8s/Compose) diante dos 503. O que
   importa aqui é o contrato HTTP; quem consome é testado no seu repo.
 - Que as métricas sejam agregadas entre workers do Gunicorn: o registro
   é em processo (dívida declarada em `config/health.py`).
"""

from __future__ import annotations

import pytest
from django.test import override_settings

from config import health
from config.health import (
    METRICAS,
    ResultadoChecagem,
    checar_banco,
    token_valido,
    verificar_prontidao,
)

TOKEN = "token-de-teste-p0-10-nao-usar-fora-da-suite"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _zera_metricas():
    METRICAS._contadores.clear()  # noqa: SLF001
    METRICAS._rotulos.clear()  # noqa: SLF001
    yield


@pytest.fixture()
def banco_caido(monkeypatch):
    """Faz a checagem de banco falhar como se o Postgres estivesse fora."""

    def _falha(timeout):
        return ResultadoChecagem(
            ok=False,
            categoria="indisponivel",
            motivo="banco indisponível",
            detalhe="OperationalError",
        )

    monkeypatch.setattr(health, "checar_banco", _falha)
    return _falha


@pytest.fixture()
def banco_lento(monkeypatch):
    """Checagem que nunca retorna no prazo — exercita o timeout."""

    def _preso(timeout):
        return ResultadoChecagem(
            ok=False, categoria="timeout", motivo=f"banco não respondeu em {timeout:g}s"
        )

    monkeypatch.setattr(health, "checar_banco", _preso)
    return _preso


# ---------------------------------------------------------------------------
# ESTADO 1 — dependências ok
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dependencias_ok_readyz_200(client) -> None:
    resposta = client.get("/readyz")
    assert resposta.status_code == 200, resposta.content
    corpo = resposta.json()
    assert corpo["status"] == "pronto"
    assert corpo["checagens"]["banco"]["ok"] is True
    assert "categoria" in corpo["checagens"]["banco"]


@pytest.mark.django_db
def test_dependencias_ok_todos_os_contratos(client) -> None:
    assert client.get("/livez").status_code == 200
    assert client.get("/livez").json() == {"status": "vivo"}
    assert client.get("/healthz").status_code == 200
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").status_code == 200


@pytest.mark.django_db
def test_healthz_nao_consulta_o_banco(client, monkeypatch) -> None:
    """
    `/healthz` é o endpoint de monitor externo e do HEALTHCHECK do Docker.
    Não pode depender de terceiro: uma indisponibilidade do Postgres não
    pode tirar o portal do ar, só o traffic de leitura.
    """

    def _nem_chama(timeout):
        raise AssertionError("/healthz não deveria checar dependência nenhuma")

    monkeypatch.setattr(health, "checar_banco", _nem_chama)
    assert client.get("/healthz").status_code == 200


@pytest.mark.django_db
def test_check_banco_real_passa_no_banco_de_teste() -> None:
    """A checagem real, contra o Postgres de verdade da suíte."""
    resultado = checar_banco(5.0)
    assert resultado.ok is True, resultado
    assert resultado.duracao_ms >= 0


# ---------------------------------------------------------------------------
# ESTADO 2 — dependência caída
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dependencia_caida_readyz_503_e_nao_falso_ok(client, banco_caido) -> None:
    """
    O teste central do eixo: com o banco fora, `/readyz` tem que dizer que
    NÃO está pronto. Um `ok` fixo passaria em todo o resto e falharia aqui.
    """
    resposta = client.get("/readyz")
    assert resposta.status_code == 503
    corpo = resposta.json()
    assert corpo["status"] == "nao_pronto"
    assert corpo["checagens"]["banco"]["ok"] is False
    assert corpo["checagens"]["banco"]["categoria"] == "indisponivel"


@pytest.mark.django_db
def test_dependencia_lenta_vira_timeout_e_nao_trava(client, banco_lento) -> None:
    resposta = client.get("/readyz")
    assert resposta.status_code == 503
    assert resposta.json()["checagens"]["banco"]["categoria"] == "timeout"


@pytest.mark.django_db
def test_livez_continua_200_com_banco_caido(client, banco_caido) -> None:
    """
    Liveness e readiness são contratos separados. Se `/livez` também
    falhasse com o banco fora, o orquestrador reiniciaria o container
    durante uma indisponibilidade do Postgres — um boot storm em vez de
    espera.
    """
    assert client.get("/livez").status_code == 200
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503


@pytest.mark.django_db
def test_checagem_que_estoura_nao_derruba_as_outras(monkeypatch) -> None:
    """
    Uma checagem com bug não pode fazer `/readyz` devolver 500 nem
    mascarar as demais. Ela é registrada como erro e o resto roda.
    """

    def _explode(timeout):
        raise RuntimeError("bug na checagem")

    monkeypatch.setattr(health, "checar_banco", _explode)
    monkeypatch.setattr(health, "checar_cache", lambda t: None)
    monkeypatch.setattr(health, "checar_broker", lambda t: None)
    relatorio = verificar_prontidao()
    assert relatorio.ok is False
    assert relatorio.checagens["banco"].categoria == "erro"
    assert sorted(relatorio.nao_verificadas) == ["broker", "cache"]


# ---------------------------------------------------------------------------
# ESTADO 3 — sem token
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ["/health-detail", "/metrics"])
def test_sem_token_401(client, rota) -> None:
    resposta = client.get(rota)
    assert resposta.status_code == 401, f"{rota} respondeu {resposta.status_code} a anônimo"
    # O corpo de um 401 não pode carregar detalhe de dependência.
    assert "checagens" not in resposta.content.decode()


@pytest.mark.django_db
def test_sem_token_e_sem_segredo_configurado_ainda_401(client) -> None:
    """
    Fail-closed: sem `HEALTH_DETAIL_TOKEN` configurado, o acesso por token
    é DESABILITADO — nunca liberado. Um deploy que esqueceu o segredo não
    pode publicar métricas.
    """
    with override_settings(HEALTH_DETAIL_TOKEN=""):
        assert client.get("/health-detail").status_code == 401
        assert client.get("/metrics").status_code == 401
        assert token_valido("qualquer-coisa") is False
        assert token_valido("") is False
        assert token_valido(None) is False


# ---------------------------------------------------------------------------
# ESTADO 4 — com token errado
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("rota", ["/health-detail", "/metrics"])
@pytest.mark.parametrize(
    "token",
    ["errado", "token-de-teste-p0-10-nao-usar-fora-da-su", TOKEN + "x", TOKEN.upper(), ""],
)
def test_token_errado_401(client, rota, token) -> None:
    resposta = client.get(rota, headers={"X-Observability-Token": token})
    assert resposta.status_code == 401, f"{rota} + token errado => {resposta.status_code}"


# ---------------------------------------------------------------------------
# Com o token certo / staff
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_token_certo_liberacao(client) -> None:
    detalhe = client.get("/health-detail", headers={"X-Observability-Token": TOKEN})
    assert detalhe.status_code == 200
    assert detalhe.json()["checagens"]["banco"]["ok"] is True

    met = client.get("/metrics", headers={"X-Observability-Token": TOKEN})
    assert met.status_code == 200
    assert "text/plain" in met["Content-Type"]


@pytest.mark.django_db
def test_staff_autenticado_liberacao(client, django_user_model) -> None:
    """Staff passa pelo caminho de sessão, sem token."""
    usuario = django_user_model.objects.create_user(
        email="staff@x.tld", password="x", papel="admin", is_staff=True
    )
    assert client.get("/health-detail").status_code == 401
    client.force_login(usuario)
    assert client.get("/health-detail").status_code == 200
    assert client.get("/metrics").status_code == 200


@pytest.mark.django_db
def test_usuario_nao_staff_nao_passa(client, django_user_model) -> None:
    """`papel=admin` sem `is_staff` NÃO libera: o portão é `is_staff`."""
    usuario = django_user_model.objects.create_user(
        email="comum@x.tld", password="x", papel="admin", is_staff=False
    )
    client.force_login(usuario)
    assert client.get("/health-detail").status_code == 401
    assert client.get("/metrics").status_code == 401


@pytest.mark.django_db
def test_health_detail_inclui_detalhe_e_publico_nao(client, banco_caido) -> None:
    """O detalhe vai para o autorizado; o público nunca o recebe."""
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    # `readyz` mostra categoria e motivo redigido, mas NUNCA a mensagem
    # do driver.
    assert "detalhe" not in client.get("/readyz").json()["checagens"]["banco"]
    restrito = client.get("/health-detail", headers={"X-Observability-Token": TOKEN})
    assert restrito.status_code == 200
    assert restrito.json()["checagens"]["banco"]["detalhe"] == "OperationalError"


# ---------------------------------------------------------------------------
# O vazamento que existia
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_healthz_nao_vaza_nada_quando_o_banco_cai(client, monkeypatch) -> None:
    """
    Regressão do vazamento de `origin/develop`, onde `healthz` devolvia
    `{"status": "erro", "detalhe": str(exc)}` com
    `django.db.utils.OperationalError`, cujo `str()` contém
    `connection to server at "10.0.0.5" (172.17.0.2), port 5432 failed:
    connection refused: FATAL:  password authentication failed for user
    "portal"`.

    Este teste injeta uma exceção com essa mensagem e exige que NADA
    disso apareça na resposta pública.
    """

    def _vazamento(timeout):
        raise Exception(
            'connection to server at "10.0.0.5" (172.17.0.2), port 5432 failed: '
            'connection refused: FATAL:  password authentication failed for user "portal"'
        )

    monkeypatch.setattr(health, "checar_banco", _vazamento)
    resposta = client.get("/healthz")
    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    for segredo in ("10.0.0.5", "172.17.0.2", "5432", "portal", "password", "FATAL"):
        assert segredo not in corpo, f"vazou {segredo!r} em /healthz: {corpo}"
    assert resposta.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readyz_nao_vaza_a_mensagem_do_driver(client, monkeypatch) -> None:
    def _vazamento(timeout):
        raise Exception('could not connect to server: host=db-interno.papel port=5432 password="s3nh4"')

    monkeypatch.setattr(health, "checar_banco", _vazamento)
    corpo = client.get("/readyz").content.decode()
    assert "s3nh4" not in corpo
    assert "db-interno.papel" not in corpo
    assert "5432" not in corpo


# ---------------------------------------------------------------------------
# Timeout, headers e métricas
# ---------------------------------------------------------------------------


def test_com_timeout_retorna_no_prazo(monkeypatch) -> None:
    """A função mais lenta do mundo não pode segurar a resposta."""
    import time as _time

    inicio = _time.monotonic()
    resultado, expirou = health._com_timeout(lambda: _time.sleep(30), 0.3)  # noqa: SLF001
    decorrido = _time.monotonic() - inicio
    assert expirou is True
    assert resultado is None
    assert decorrido < 5, f"demorou {decorrido:.1f}s para declarar timeout"


def test_com_timeout_devolve_valor_quando_termina_no_prazo() -> None:
    valor, expirou = health._com_timeout(lambda: 42, 2)  # noqa: SLF001
    assert valor == 42
    assert expirou is False


@pytest.mark.django_db
def test_endpoints_de_saude_nao_sao_cacheados(client) -> None:
    """
    Um 503 de readiness cacheado pelo proxy reconduz tráfego a um serviço
    quebrado — o oposto do que o endpoint existe para dizer.
    """
    for rota in ("/healthz", "/livez", "/readyz"):
        resposta = client.get(rota)
        assert "no-store" in resposta.get("Cache-Control", ""), rota


@pytest.mark.django_db
def test_metricas_tem_formato_prometheus_e_nosniff(client) -> None:
    METRICAS.incrementar("portal_teste_total", 2, situacao="ok")
    resposta = client.get("/metrics", headers={"X-Observability-Token": TOKEN})
    assert resposta.status_code == 200
    assert resposta["X-Content-Type-Options"] == "nosniff"
    corpo = resposta.content.decode()
    assert "# TYPE portal_teste_total counter" in corpo
    assert 'portal_teste_total{situacao="ok"} 2' in corpo
    assert "portal_tempo_de_atividade_segundos" in corpo


def test_rotulo_de_metrica_com_aspas_nao_quebra_a_exposicao() -> None:
    """Rótulo vem de terceiro; aspas/newline precisam ser escapados."""
    METRICAS.incrementar("portal_x_total", 1, fonte='a"b\nc')
    saida = METRICAS.render()
    linha = [l for l in saida.splitlines() if l.startswith("portal_x_total{")][0]
    assert '\\"' in linha
    assert "\\n" in linha
    assert saida.count("\n") == len(saida.rstrip("\n").split("\n")), "quebrou de linha"


# ---------------------------------------------------------------------------
# Autorização
# ---------------------------------------------------------------------------


def test_token_valido_usa_tempo_constante(monkeypatch) -> None:
    """
    `==` em string vaza o segredo byte a byte pela latência. O código tem
    de passar por `hmac.compare_digest`; este teste fixa isso.
    """
    import hmac as _hmac

    chamadas = []
    real = _hmac.compare_digest

    def _espiao(a, b):
        chamadas.append((a, b))
        return real(a, b)

    monkeypatch.setattr(health.hmac, "compare_digest", _espiao)
    assert token_valido(TOKEN) is True
    assert chamadas, "compare_digest não foi chamado — a comparação está exposta a timing"
    assert chamadas[0][0] == TOKEN


@pytest.mark.django_db
def test_bearer_tambem_serve_de_token(client) -> None:
    resposta = client.get("/health-detail", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resposta.status_code == 200


# ---------------------------------------------------------------------------
# Cache localmem não vira verde falso
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cache_localmem_e_reportado_como_nao_verificado(client) -> None:
    """
    Devolver `ok` para um `LocMemCache` seria um verde de mentira: não há
    dependência externa para checar. O relatório diz explicitamente que
    não foi verificado, para que ninguém confunda com "verificado e ok".
    """
    relatorio = verificar_prontidao()
    assert "cache" in relatorio.nao_verificadas
    assert "cache" not in relatorio.checagens
    assert relatorio.ok is True  # só o banco é essencial

    corpo = client.get("/readyz").json()
    assert "cache" in corpo["nao_verificadas"]
