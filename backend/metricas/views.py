"""API de analytics de produto (Central de Inteligência) e consentimento.

A ingestão pública é a fronteira de privacidade do portal: até o Bloco A2 ela
persistia evento sem conferir o token de consentimento, apesar de
`ANALYTICS_REQUIRE_CONSENT_TOKEN` existir com default `True` (fail-open). Agora
o token é verificado de verdade (`metricas/consent.py`), o payload passa por
allowlist e nada é persistido sem prova de consentimento.
"""

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.metrics import METRICS
from config.throttling import ConsentimentoAnonThrottle

from . import consent, services
from .models import EventoSite
from .services_inteligencia import central_inteligencia


class PainelMetricasView(APIView):
    """Critério de aceite 2 — só admin."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "papel", None) != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        dias = int(request.query_params.get("dias", 30))
        return Response(services.painel(dias))


# ---------------------------------------------------------------------------
# FRENTE 6 — Central de Inteligência: ingestão de eventos + painel agregado.
# ---------------------------------------------------------------------------

# Tipos roteados para os modelos do feed (FRENTE 3 — fonte única do sinal
# por notícia/busca, sem duplicar contadores). O resto vai para EventoSite.
_ROTA_FEED = {"news_view", "news_click", "share", "save", "search", "search_result_click"}
_TIPOS_FEED_VALIDOS = {"view", "click", "read", "save", "unsave", "share", "search_click"}
_MAPA_TIPO_FEED = {
    "news_view": "view",
    "news_click": "click",
    "share": "share",
    "save": "save",
    "search_result_click": "search_click",
}
_ORIGENS_VALIDAS = {c[0] for c in EventoSite.ORIGEM_CHOICES}


def _usuario_ou_none(request):
    u = getattr(request, "user", None)
    if u is not None and getattr(u, "is_authenticated", False):
        return u
    return None


def _texto(valor, limite=500):
    if valor is None:
        return ""
    return str(valor)[:limite]


def _token_do_request(request, dados) -> str:
    """Token de consentimento, do header ou do corpo.

    O header (`X-Consent-Token`) é o caminho preferido porque não entra no
    corpo — e corpo é o que um log de aplicação ou um proxy poderia acabar
    guardando. O campo `consent_token` existe porque `navigator.sendBeacon`
    (usado por `frontend/lib/analytics.ts`) NÃO permite cabeçalhos
    customizados: sem ele o tracker precisaria abandonar o beacon.
    """

    bruto = request.headers.get("X-Consent-Token", "") if hasattr(request, "headers") else ""
    if not bruto and isinstance(dados, dict):
        bruto = dados.get("consent_token", "")
    return "" if bruto is None else str(bruto).strip()


class ConsentimentoTokenView(APIView):
    """POST /api/metricas/consent/ — emite o token de consentimento assinado.

    É a única forma de obter um token válido: a chave HMAC é do backend e nunca
    chega ao navegador. O navegador só chama isto DEPOIS do gesto de consentimento
    (`frontend/lib/cookie-consent.ts`), e revalida quando `exp` passa.

    Por que isso não é um botão de aceitar: o gesto humano é do cliente. O que o
    token garante é que todo evento carregue a prova de que foi este backend que
    autorizou aquela janela de coleta, para aquela sessão, e que a prova pode ser
    revogada girando a chave. Sem emissor, o "token" seria uma string que o
    próprio visitante inventa — o controle decorativo que o Bloco A2 removeu.

    Rate limitado (`consentimento`) porque é público, sem autenticação e barato
    de chamar: um emissor sem limite é um script de coleta de dados com carimbo
    do próprio site.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ConsentimentoAnonThrottle]

    def post(self, request):
        dados = request.data if isinstance(request.data, dict) else {}
        categoria = _texto(dados.get("categoria"), 32).strip() or consent.CATEGORIA_ANALYTICS
        if categoria not in consent.CATEGORIAS_VALIDAS:
            # Categoria errada (ex.: o token técnico) não é emitida aqui: este
            # endpoint é de analytics de PRODUTO e o consentimento técnico tem
            # outro mecanismo (header `X-Technical-Consent`).
            consent.registrar_recusa(consent.MOTIVO_CATEGORIA, origem="token")
            return Response(
                {"detail": "Categoria de consentimento inválida."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        sujeito = consent.normalizar_sub(dados.get("sessao") or dados.get("sub"))
        if not consent.sub_valido(sujeito):
            consent.registrar_recusa(consent.MOTIVO_SUJEITO, origem="token")
            return Response(
                {"detail": "Sessão inválida para consentimento."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token, claims = consent.emitir_consentimento(categoria=categoria, sub=sujeito)
        except consent.ConsentError as exc:
            # Configuração quebrada (sem chave). Fail-closed: nada é emitido.
            consent.registrar_recusa(exc.motivo, origem="token")
            return Response(
                {"detail": "Consentimento indisponível."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        METRICS.inc("portal_analytics_consent_tokens_issued_total", category=categoria[:16])
        return Response(
            {
                "token": token,
                "categoria": categoria,
                "sub": sujeito,
                "exp": int(claims["exp"]),
                "ttl_segundos": int(claims["exp"]) - int(claims["iat"]),
            },
            status=status.HTTP_201_CREATED,
        )


class EventoIngestaoView(APIView):
    """POST /api/metricas/eventos/ — público, fail-closed no consentimento.

    Ordem deliberada das etapas:

    1. **allowlist do payload** (`consent.sanear_payload`), que é uma função
       pura: ela normaliza tipo/tamanho/texto e é o que dá a `sessao` já
       normalizada com que o token vai ser comparado. Nada é persistido aqui.
    2. **consentimento** (token assinado) — é o passo decisivo: sem prova
       válida, o evento não chega a `EventoSite`, `InteracaoNoticia` nem
       `EventoBusca`. Um payload recusado no passo 1 (ex.: grande demais) sai
       antes, com o mesmo 202 e o mesmo formato de resposta.
    3. **persistência** — só o que sobreviveu às duas primeiras etapas.

    Nunca quebra a navegação: qualquer falha de persistência devolve 202 com
    `registrado: False` em vez de 500 (o tracking é best-effort por definição).
    Rejeição por consentimento também é 202, com um código estável e curto
    (`motivo`) — suficiente para o cliente renovar o token, sem confirmar nada
    sobre o visitante. O motivo completo fica no log técnico e na métrica.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        bruto = request.data if isinstance(request.data, dict) else {}
        saneado = consent.sanear_payload(bruto)
        if not saneado.ok:
            consent.registrar_recusa(saneado.motivo)
            return Response(
                {"registrado": False, "motivo": saneado.motivo},
                status=status.HTTP_202_ACCEPTED,
            )
        dados = saneado.dados
        tipo = _texto(dados.get("tipo"), 40).strip()
        if not consent.consentimento_requerido():
            consent.registrar_bypass()
        else:
            # A sessão pedida só é exigida se ela for um sujeito válido: quando
            # não é (cliente que não manda `sessao`, ou manda um id curto/inválido),
            # quem manda é o TOKEN — o evento passa a ser atribuído ao sujeito
            # assinado, nunca ao que o cliente alegou. Aceitar a alegação sem
            # verificação deixaria um token válido (de uma sessão) poluir outra.
            sub_pedido = dados.get("sessao") or None
            if not consent.sub_valido(sub_pedido):
                sub_pedido = None
            verificacao = consent.verificar_consentimento(
                _token_do_request(request, bruto), sub_esperado=sub_pedido
            )
            if not verificacao.ok:
                consent.registrar_recusa(verificacao.motivo, tipo=tipo)
                return Response(
                    {"registrado": False, "motivo": f"consent_{verificacao.motivo}"},
                    status=status.HTTP_202_ACCEPTED,
                )
            if not consent.sub_valido(dados.get("sessao")):
                dados["sessao"] = verificacao.sub
        # Campo fora da allowlist NÃO é "evento rejeitado": o evento segue e é
        # persistido (o descarte já foi contado em
        # `portal_analytics_payload_fields_dropped_total`, dentro de
        # `sanear_payload`). Contar aqui fazia o painel de "eventos rejeitados"
        # disparar com eventos sendo aceitos — alarme falso justamente na
        # métrica que existe para não ser verde-mentira (achado MINOR-6).
        if not tipo:
            return Response({"detail": "Informe tipo."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            if tipo in _ROTA_FEED:
                registrado = self._rotear_feed(request, tipo, dados)
            elif tipo in EventoSite.TIPOS_VALIDOS:
                registrado = self._registrar_site(request, tipo, dados)
            else:
                consent.registrar_recusa(consent.MOTIVO_TIPO_DESCONHECIDO, tipo=tipo)
                return Response(
                    {
                        "detail": "Tipo de evento desconhecido.",
                        "motivo": consent.MOTIVO_TIPO_DESCONHECIDO,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response({"registrado": registrado}, status=status.HTTP_201_CREATED)
        except Exception:
            return Response({"registrado": False}, status=status.HTTP_202_ACCEPTED)

    def _base_sessao(self, dados):
        # `sessao` já saiu do sanitizador normalizada (só `[A-Za-z0-9._-]`, até
        # 64 chars) e ligada ao sujeito do token; o corte final é apenas o
        # limite do `max_length` do modelo.
        return _texto(dados.get("sessao"), 64)

    def _registrar_site(self, request, tipo, dados) -> bool:
        origem = _texto(dados.get("origem"), 20).strip()
        try:
            EventoSite.objects.create(
                user=_usuario_ou_none(request),
                sessao=self._base_sessao(dados),
                tipo=tipo,
                path=_texto(dados.get("path"), 500),
                categoria=_texto(dados.get("categoria"), 100),
                autor_ref=_texto(dados.get("autor_ref") or dados.get("autor"), 200),
                secao_home=_texto(dados.get("secao_home") or dados.get("secao"), 60),
                origem=origem if origem in _ORIGENS_VALIDAS else "",
                dispositivo=_texto(dados.get("dispositivo"), 20),
                pais=_texto(dados.get("pais"), 100),
                estado=_texto(dados.get("estado"), 100),
                cidade=_texto(dados.get("cidade"), 150),
                regiao=_texto(dados.get("regiao"), 150),
                tempo_permanencia_seg=int(dados.get("tempo_permanencia_seg") or 0),
                scroll_max_pct=int(dados.get("scroll_max_pct") or 0),
                extra=dados.get("extra") or {},
            )
            return True
        except Exception:
            return False

    def _rotear_feed(self, request, tipo, dados) -> bool:
        """Roteia para `feed` (fonte única). `search` usa `busca.registrar_busca`."""
        try:
            from feed import busca as busca_services
            from feed.models import InteracaoNoticia

            user = _usuario_ou_none(request)
            sessao = self._base_sessao(dados)
            if tipo == "search":
                busca_services.registrar_busca(
                    _texto(dados.get("termo") or dados.get("query"), 300),
                    int(dados.get("resultados") or 0),
                    user=user,
                    session_key=sessao,
                    filtros=dados.get("filtros") if isinstance(dados.get("filtros"), dict) else {},
                )
                return True
            entry_tipo = _texto(dados.get("entry_tipo"), 10).strip() or "item"
            if entry_tipo not in ("item", "cluster"):
                entry_tipo = "item"
            # `id` era um alias informal aceito aqui; saiu da allowlist, então
            # quem manda evento sem `entry_id` recebe `registrado: False` em vez
            # de um evento gravado com id 0.
            entry_id = int(dados.get("entry_id") or 0)
            if entry_id <= 0:
                return False
            if tipo == "search_result_click":
                busca_services.registrar_clique_resultado(
                    entry_tipo, entry_id,
                    query=_texto(dados.get("termo") or dados.get("query"), 300),
                    user=user, session_key=sessao,
                    tempo_leitura_seg=max(0, int(dados.get("tempo_leitura_seg") or 0)),
                )
                return True
            tipo_feed = _MAPA_TIPO_FEED.get(tipo)
            if tipo_feed not in _TIPOS_FEED_VALIDOS:
                return False
            from catalogo_noticias.models import NewsCluster, NewsItem

            kwargs: dict = {
                "tipo": tipo_feed,
                "entry_tipo": entry_tipo,
                "user": user,
                "session_key": sessao,
                "categoria": _texto(dados.get("categoria"), 100),
                "tempo_leitura_seg": max(0, int(dados.get("tempo_leitura_seg") or 0)),
                "query": "",
            }
            if entry_tipo == "cluster":
                obj = NewsCluster.objects.filter(pk=entry_id).first()
                if obj is None:
                    return False
                kwargs["cluster"] = obj
                if not kwargs["categoria"]:
                    primeiro = obj.itens.order_by("-timestamp_ingestao").first()
                    kwargs["categoria"] = (obj.categoria_dominante or (primeiro.categoria if primeiro else ""))[:100]
            else:
                obj = NewsItem.objects.filter(pk=entry_id).first()
                if obj is None:
                    return False
                kwargs["item"] = obj
                if not kwargs["categoria"]:
                    kwargs["categoria"] = (obj.categoria or "")[:100]
            InteracaoNoticia.objects.create(**kwargs)
            return True
        except Exception:
            return False


class CentralInteligenciaView(APIView):
    """GET /api/metricas/inteligencia/ — só admin.

    Params: `periodo` = hoje|ontem|7d|30d|90d|custom (+ `inicio`/`fim`
    YYYY-MM-DD quando custom). O comparativo com o período anterior vem
    embutido no payload.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if getattr(request.user, "papel", None) != "admin":
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(
            central_inteligencia(
                periodo=request.query_params.get("periodo", "30d"),
                inicio=request.query_params.get("inicio"),
                fim=request.query_params.get("fim"),
            )
        )

