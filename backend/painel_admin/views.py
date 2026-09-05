from django.db.models import Q
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from assinatura.models import Plan, Subscription, HistoricoPagamento
from catalogo_noticias.models import NewsItem
from gating.models import FeatureLimit, FeatureLimitAlteracaoLog
from identidade.models import User
from moderacao.models import Denuncia
from moderacao import services as moderacao_services
from painel_admin.models import AuditoriaAdmin
from painel_admin.permissions import IsAdmin404
from painel_admin.serializers import (
    AssinaturaAdminSerializer,
    DenunciaAdminSerializer,
    DenunciaAcaoSerializer,
    FeatureLimitAdminSerializer,
    FeatureLimitUpdateSerializer,
    FilaDecisaoSerializer,
    PlanAdminSerializer,
    PlanCreateSerializer,
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
