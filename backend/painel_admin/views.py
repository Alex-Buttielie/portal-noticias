from django.db.models import ProtectedError, Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from assinatura.models import Plan, Subscription, HistoricoPagamento
from catalogo_noticias.models import NewsItem
from gating.models import ConfiguracaoSistema, FeatureLimit, FeatureLimitAlteracaoLog
from identidade.models import User
from moderacao.models import Denuncia
from moderacao import services as moderacao_services
from painel_admin.models import AuditoriaAdmin
from painel_admin.permissions import IsAdmin404
from painel_admin.serializers import (
    AssinaturaAdminSerializer,
    DenunciaAdminSerializer,
    DenunciaAcaoSerializer,
    DestaqueEditorialAdminSerializer,
    FeatureLimitAdminSerializer,
    FeatureLimitUpdateSerializer,
    FilaDecisaoSerializer,
    PlanAdminSerializer,
    PlanCreateSerializer,
    RegraCuradoriaAdminSerializer,
    UsuarioAdminSerializer,
    UsuarioUpdateSerializer,
)
from painel_admin.services import auditar, decidir_fila


class AdminPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _paginate(request, queryset, serializer_class, context=None):
    paginator = AdminPagination()
    page = paginator.paginate_queryset(queryset, request)
    data = serializer_class(page, many=True, context=context or {}).data
    return paginator.get_paginated_response(data)


class UsuarioListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        qs = User.objects.all().order_by("-date_joined")
        search = request.query_params.get("search") or request.query_params.get("q")
        if search:
            qs = qs.filter(Q(email__icontains=search) | Q(nome__icontains=search))
        papel = request.query_params.get("papel")
        if papel in ("free", "premium", "admin"):
            qs = qs.filter(papel=papel)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [
            {
                "id": u.id,
                "email": u.email,
                "nome": u.nome,
                "papel": u.papel,
                "is_active": u.is_active,
                "email_verificado": u.email_verificado,
                "date_joined": u.date_joined,
            }
            for u in page
        ]
        return paginator.get_paginated_response(data)


class UsuarioDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request, user_id):
        try:
            u = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "id": u.id,
                "email": u.email,
                "nome": u.nome,
                "papel": u.papel,
                "is_active": u.is_active,
                "email_verificado": u.email_verificado,
                "date_joined": u.date_joined,
            }
        )

    def patch(self, request, user_id):
        try:
            u = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = UsuarioUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        anterior = {"papel": u.papel, "is_active": u.is_active}
        if "papel" in ser.validated_data:
            u.papel = ser.validated_data["papel"]
        if "is_active" in ser.validated_data:
            u.is_active = ser.validated_data["is_active"]
        u.save(update_fields=["papel", "is_active"] if "is_active" in ser.validated_data or "papel" in ser.validated_data else [])
        novo = {"papel": u.papel, "is_active": u.is_active}
        auditar(acao="usuario_update", alvo_tipo="User", alvo_id=u.id, detalhe={"anterior": anterior, "novo": novo}, alterado_por=request.user)
        return Response(
            {
                "id": u.id,
                "email": u.email,
                "nome": u.nome,
                "papel": u.papel,
                "is_active": u.is_active,
                "email_verificado": u.email_verificado,
                "date_joined": u.date_joined,
            }
        )


class FilaListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        status_param = request.query_params.get("status", "pendente")
        qs = NewsItem.objects.select_related("cluster").order_by("-timestamp_ingestao")
        if status_param in ("pendente", "aprovado", "rejeitado", "nao_aplicavel"):
            qs = qs.filter(status_revisao=status_param)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        data = [
            {
                "tipo": "cluster" if it.cluster_id else "item",
                "id": it.id,
                "titulo": it.titulo,
                "categoria": it.categoria,
                "status_revisao": it.status_revisao,
                "nome_fonte": it.nome_fonte,
                "url_fonte_original": it.url_fonte_original,
                "urgente": it.urgente,
                "cluster": it.cluster_id,
                "cluster_titulo": it.cluster.titulo_acontecimento if it.cluster_id else "",
                "timestamp_ingestao": it.timestamp_ingestao,
            }
            for it in page
        ]
        return paginator.get_paginated_response(data)


class FilaDecisaoView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def post(self, request, item_id):
        ser = FilaDecisaoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        item = decidir_fila(item_id, ser.validated_data["acao"], request.user)
        if item is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response({"detail": "ok", "status_revisao": item.status_revisao})


class PlanListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        qs = Plan.objects.all().order_by("preco")
        return _paginate(request, qs, PlanAdminSerializer)

    def post(self, request):
        ser = PlanCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        plan = Plan.objects.create(nome=d["nome"], preco=d["preco"], duracao_dias=d["duracao_dias"], ativo=d.get("ativo", True))
        auditar(acao="plan_create", alvo_tipo="Plan", alvo_id=plan.id, detalhe={"novo": {"nome": plan.nome, "preco": str(plan.preco), "duracao_dias": plan.duracao_dias, "ativo": plan.ativo}}, alterado_por=request.user)
        return Response(PlanAdminSerializer(plan).data, status=status.HTTP_201_CREATED)


class PlanDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request, plan_id):
        try:
            plan = Plan.objects.get(pk=plan_id)
        except Plan.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(PlanAdminSerializer(plan).data)

    def patch(self, request, plan_id):
        try:
            plan = Plan.objects.get(pk=plan_id)
        except Plan.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        anterior = {"nome": plan.nome, "preco": str(plan.preco), "duracao_dias": plan.duracao_dias, "ativo": plan.ativo}
        ser = PlanCreateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for k, v in ser.validated_data.items():
            setattr(plan, k, v)
        plan.save()
        novo = {"nome": plan.nome, "preco": str(plan.preco), "duracao_dias": plan.duracao_dias, "ativo": plan.ativo}
        auditar(acao="plan_update", alvo_tipo="Plan", alvo_id=plan.id, detalhe={"anterior": anterior, "novo": novo}, alterado_por=request.user)
        return Response(PlanAdminSerializer(plan).data)

    def delete(self, request, plan_id):
        try:
            plan = Plan.objects.get(pk=plan_id)
        except Plan.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        try:
            plan.delete()
        except ProtectedError:
            # Subscription.plan usa on_delete=PROTECT (ver assinatura/models.py):
            # plano com histórico de assinaturas não pode ser apagado, só
            # desativado — evita perder o vínculo histórico.
            return Response(
                {"detail": "Este plano possui assinaturas vinculadas e não pode ser excluído. Desative-o em vez disso."},
                status=status.HTTP_409_CONFLICT,
            )
        auditar(acao="plan_delete", alvo_tipo="Plan", alvo_id=plan_id, detalhe={"nome": plan.nome}, alterado_por=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LimiteListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        qs = FeatureLimit.objects.all().order_by("chave", "plano")
        return _paginate(request, qs, FeatureLimitAdminSerializer)


class LimiteDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request, limite_id):
        try:
            lim = FeatureLimit.objects.get(pk=limite_id)
        except FeatureLimit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(FeatureLimitAdminSerializer(lim).data)

    def patch(self, request, limite_id):
        try:
            lim = FeatureLimit.objects.get(pk=limite_id)
        except FeatureLimit.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = FeatureLimitUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        anterior = lim.valor
        lim.valor = ser.validated_data["valor"]
        if "descricao" in ser.validated_data:
            lim.descricao = ser.validated_data["descricao"]
        lim.atualizado_por = request.user
        lim.save()
        FeatureLimitAlteracaoLog.objects.create(
            feature_limit_chave=lim.chave, plano=lim.plano, valor_anterior=anterior, valor_novo=lim.valor, alterado_por=request.user
        )
        auditar(acao="limite_update", alvo_tipo="FeatureLimit", alvo_id=lim.id, detalhe={"chave": lim.chave, "plano": lim.plano, "anterior": anterior, "novo": lim.valor}, alterado_por=request.user)
        return Response(FeatureLimitAdminSerializer(lim).data)


class AssinaturaListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        qs = Subscription.objects.select_related("user", "plan").order_by("-criado_em")
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        plan_id = request.query_params.get("plan")
        if plan_id:
            qs = qs.filter(plan_id=plan_id)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(user__email__icontains=search) | Q(user__nome__icontains=search))
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        data = AssinaturaAdminSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class AssinaturaDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request, assinatura_id):
        try:
            sub = Subscription.objects.select_related("user", "plan").get(pk=assinatura_id)
        except Subscription.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        pagamentos = HistoricoPagamento.objects.filter(subscription=sub).order_by("-criado_em")
        dados = AssinaturaAdminSerializer(sub).data
        dados["pagamentos"] = [{"id": p.id, "valor": str(p.valor), "status": p.status, "criado_em": p.criado_em} for p in pagamentos]
        return Response(dados)


class DenunciaListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        qs = Denuncia.objects.select_related("denunciante").order_by("-criado_em")
        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        paginator = AdminPagination()
        page = paginator.paginate_queryset(qs, request)
        data = DenunciaAdminSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class DenunciaAcaoView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def post(self, request, denuncia_id):
        try:
            denuncia = Denuncia.objects.get(pk=denuncia_id)
        except Denuncia.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = DenunciaAcaoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        alvo = denuncia.alvo
        usuario_alvo = getattr(alvo, "autor", None) or getattr(alvo, "autor_id", None)
        if hasattr(alvo, "autor"):
            usuario_alvo = alvo.autor
        else:
            usuario_alvo = denuncia.denunciante
        acao = moderacao_services.aplicar_acao(
            usuario_alvo if hasattr(usuario_alvo, "id") else denuncia.denunciante,
            d["tipo"],
            d["motivo"],
            request.user,
            denuncia=denuncia,
        )
        procedente = d.get("procedente", True)
        moderacao_services.resolver_denuncia(denuncia, request.user, procedente, d["motivo"])
        auditar(acao="moderacao_acao", alvo_tipo="Denuncia", alvo_id=denuncia.id, detalhe={"tipo": d["tipo"], "procedente": procedente}, alterado_por=request.user)
        return Response({"detail": "acao aplicada", "acao_id": acao.id})


class SistemaConfigView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        cfg, _ = ConfiguracaoSistema.objects.get_or_create(pk=1)
        return Response({"premium_ativo": cfg.premium_ativo, "atualizado_em": cfg.atualizado_em})

    def patch(self, request):
        cfg, _ = ConfiguracaoSistema.objects.get_or_create(pk=1)
        valor = request.data.get("premium_ativo")
        if not isinstance(valor, bool):
            return Response(
                {"detail": "Informe premium_ativo como verdadeiro ou falso."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        cfg.premium_ativo = valor
        cfg.save()
        auditar(
            acao="sistema_premium_update",
            alvo_tipo="ConfiguracaoSistema",
            alvo_id=1,
            detalhe={"premium_ativo": valor},
            alterado_por=request.user,
        )
        return Response({"premium_ativo": cfg.premium_ativo, "atualizado_em": cfg.atualizado_em})


# ---------------------------------------------------------------------------
# FRENTE 6 — Central de Inteligência: controles editoriais.
#
# `DestaqueEditorial` (feed/models.py, FRENTE 3: manchete/destaque/bloqueio
# por entrada) é respeitado por `feed/recomendacao.py` (manchetes,
# destaques_do_dia, bloqueios em todas as seções); `RegraCuradoria`
# (painel_admin) é aplicada no feed geral via
# `painel_admin.services_regras.aplicar_regras_curadoria`.
# ---------------------------------------------------------------------------


def _modelo_destaque():
    """Modelo `DestaqueEditorial` (FRENTE 3) ou None se ainda não mergeado."""
    try:
        from feed.models import DestaqueEditorial

        return DestaqueEditorial
    except Exception:
        return None


def _sem_feed():
    return Response(
        {"detail": "Overrides por entrada indisponíveis: modelos editoriais do feed ainda não presentes."},
        status=status.HTTP_501_NOT_IMPLEMENTED,
    )


def _titulo_entrada(entry_tipo, entry_id):
    try:
        if entry_tipo == "cluster":
            from catalogo_noticias.models import NewsCluster

            obj = NewsCluster.objects.filter(pk=entry_id).first()
            return obj.titulo_acontecimento if obj else ""
        from catalogo_noticias.models import NewsItem

        obj = NewsItem.objects.filter(pk=entry_id).first()
        return obj.titulo if obj else ""
    except Exception:
        return ""


def _serializar_destaque(ov):
    return {
        "id": ov.id,
        "tipo": ov.tipo,
        "entry_tipo": ov.entry_tipo,
        "entry_id": ov.cluster_id if ov.entry_tipo == "cluster" else ov.item_id,
        "titulo": _titulo_entrada(ov.entry_tipo, ov.cluster_id if ov.entry_tipo == "cluster" else ov.item_id),
        "posicao": ov.posicao,
        "ativo": ov.ativo,
        "inicio": ov.inicio,
        "fim": ov.fim,
        "motivo": ov.motivo,
        "vigente": ov.vigente(),
        "criado_em": ov.criado_em,
    }


class DestaqueEditorialListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        DestaqueEditorial = _modelo_destaque()
        if DestaqueEditorial is None:
            return _sem_feed()

        qs = DestaqueEditorial.objects.all().order_by("posicao", "-criado_em")
        tipo = request.query_params.get("tipo")
        if tipo in ("destaque", "manchete", "bloqueio"):
            qs = qs.filter(tipo=tipo)
        return Response([_serializar_destaque(ov) for ov in qs[:200]])

    def post(self, request):
        DestaqueEditorial = _modelo_destaque()
        if DestaqueEditorial is None:
            return _sem_feed()

        ser = DestaqueEditorialAdminSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        entry_tipo, entry_id = d["entry_tipo"], d["entry_id"]
        if _titulo_entrada(entry_tipo, entry_id) == "" and not (
            entry_tipo == "cluster"
        ):
            # Item inexistente: ainda permite criar bloqueio preventivo? Não —
            # override órfão confunde a Central; exige alvo real.
            from catalogo_noticias.models import NewsItem

            if not NewsItem.objects.filter(pk=entry_id).exists():
                return Response(
                    {"detail": "Notícia inexistente para este override."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if entry_tipo == "cluster":
            from catalogo_noticias.models import NewsCluster

            if not NewsCluster.objects.filter(pk=entry_id).exists():
                return Response(
                    {"detail": "Acontecimento inexistente para este override."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        kwargs = {
            "tipo": d["tipo"],
            "entry_tipo": entry_tipo,
            "posicao": d.get("posicao", 0),
            "ativo": d.get("ativo", True),
            "inicio": d.get("inicio"),
            "fim": d.get("fim"),
            "motivo": d.get("motivo", ""),
        }
        if entry_tipo == "cluster":
            kwargs["cluster_id"] = entry_id
            kwargs["item"] = None
        else:
            kwargs["item_id"] = entry_id
            kwargs["cluster"] = None
        ov = DestaqueEditorial.objects.create(**kwargs)
        auditar(
            acao="destaque_create", alvo_tipo="DestaqueEditorial", alvo_id=ov.id,
            detalhe={"tipo": ov.tipo, "entry": f"{entry_tipo}:{entry_id}"},
            alterado_por=request.user,
        )
        return Response(_serializar_destaque(ov), status=status.HTTP_201_CREATED)


class DestaqueEditorialDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def _objeto(self, destaque_id):
        DestaqueEditorial = _modelo_destaque()
        if DestaqueEditorial is None:
            return None

        try:
            return DestaqueEditorial.objects.get(pk=destaque_id)
        except DestaqueEditorial.DoesNotExist:
            return None

    def patch(self, request, destaque_id):
        if _modelo_destaque() is None:
            return _sem_feed()
        ov = self._objeto(destaque_id)
        if ov is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = DestaqueEditorialAdminSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for campo in ("tipo", "posicao", "ativo", "inicio", "fim", "motivo"):
            if campo in ser.validated_data:
                setattr(ov, campo, ser.validated_data[campo])
        ov.save()
        auditar(
            acao="destaque_update", alvo_tipo="DestaqueEditorial", alvo_id=ov.id,
            detalhe={"novo": ser.validated_data}, alterado_por=request.user,
        )
        return Response(_serializar_destaque(ov))

    def delete(self, request, destaque_id):
        if _modelo_destaque() is None:
            return _sem_feed()
        ov = self._objeto(destaque_id)
        if ov is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ov.delete()
        auditar(
            acao="destaque_delete", alvo_tipo="DestaqueEditorial", alvo_id=destaque_id,
            detalhe={}, alterado_por=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _serializar_regra(regra):
    return {
        "id": regra.id,
        "tipo": regra.tipo,
        "entry_tipo": regra.entry_tipo,
        "entry_id": regra.entry_id,
        "alvo": regra.alvo,
        "ordem": regra.ordem,
        "ativo": regra.ativo,
        "inicio": regra.inicio,
        "fim": regra.fim,
        "motivo": regra.motivo,
        "vigente": regra.vigente(),
        "criado_em": regra.criado_em,
    }


class RegraCuradoriaListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def get(self, request):
        from painel_admin.models import RegraCuradoria

        qs = RegraCuradoria.objects.all().order_by("ordem", "-criado_em")
        tipo = request.query_params.get("tipo")
        if tipo:
            qs = qs.filter(tipo=tipo)
        return Response([_serializar_regra(r) for r in qs[:200]])

    def post(self, request):
        from painel_admin.models import RegraCuradoria

        ser = RegraCuradoriaAdminSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d["tipo"] in RegraCuradoria.TIPOS_ENTRADA and not (d.get("entry_tipo") and d.get("entry_id")):
            return Response(
                {"detail": "Este tipo de regra exige entry_tipo + entry_id."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if d["tipo"] in ("boost_categoria", "bloqueio_categoria", "colunista_destaque",
                         "ordem_categorias") and not (d.get("alvo") or "").strip():
            return Response(
                {"detail": "Este tipo de regra exige alvo (categoria/autor/lista)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        regra = RegraCuradoria.objects.create(
            tipo=d["tipo"],
            entry_tipo=d.get("entry_tipo") or "",
            entry_id=d.get("entry_id"),
            alvo=(d.get("alvo") or "")[:300],
            ordem=d.get("ordem", 0),
            ativo=d.get("ativo", True),
            inicio=d.get("inicio"),
            fim=d.get("fim"),
            motivo=d.get("motivo", ""),
            criado_por=request.user,
        )
        auditar(
            acao="regra_create", alvo_tipo="RegraCuradoria", alvo_id=regra.id,
            detalhe={"tipo": regra.tipo, "alvo": regra.alvo}, alterado_por=request.user,
        )
        return Response(_serializar_regra(regra), status=status.HTTP_201_CREATED)


class RegraCuradoriaDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin404]

    def _objeto(self, regra_id):
        from painel_admin.models import RegraCuradoria

        try:
            return RegraCuradoria.objects.get(pk=regra_id)
        except RegraCuradoria.DoesNotExist:
            return None

    def patch(self, request, regra_id):
        regra = self._objeto(regra_id)
        if regra is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = RegraCuradoriaAdminSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        for campo in ("tipo", "entry_tipo", "entry_id", "alvo", "ordem", "ativo", "inicio", "fim", "motivo"):
            if campo in ser.validated_data:
                setattr(regra, campo, ser.validated_data[campo])
        regra.save()
        auditar(
            acao="regra_update", alvo_tipo="RegraCuradoria", alvo_id=regra.id,
            detalhe={"novo": {k: str(v) for k, v in ser.validated_data.items()}},
            alterado_por=request.user,
        )
        return Response(_serializar_regra(regra))

    def delete(self, request, regra_id):
        regra = self._objeto(regra_id)
        if regra is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        regra.delete()
        auditar(
            acao="regra_delete", alvo_tipo="RegraCuradoria", alvo_id=regra_id,
            detalhe={}, alterado_por=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
