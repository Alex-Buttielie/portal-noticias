from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConfiguracaoRobo, FonteRobo, RegistroExecucaoIngestao
from .robos_serializers import ConfiguracaoRoboSerializer, FonteRoboSerializer, RegistroExecucaoIngestaoSerializer
from .services.ingestao import executar_ingestao


def _eh_admin(user):
    return getattr(user, "papel", None) == "admin"


def _executar_ingestao_em_background(rid: str) -> None:
    """Roda `executar_ingestao()` fora do ciclo da requisição.

    O endpoint responde 202 antes; o SUCESSO fica registrado em
    `RegistroExecucaoIngestao` (visível em GET /execucoes/). A FALHA não é
    persistida no banco — `executar_ingestao()` só grava o registro quando
    conclui — e por isso vai para o log com traceback e o `request_id`, que
    é o caminho de investigação hoje. Persistir a falha no banco é backlog.
    Conexões de banco por thread: o Django abre/fecha automaticamente por
    thread; `close_old_connections()` no início evita reutilizar conexão
    stale do pool do worker.

    Risco aceito e documentado: thread `daemon` morre se o PM2 reiniciar o
    processo no meio da ingestão. Migrar para Celery é o destino correto.
    """
    import logging
    import traceback

    from django.db import close_old_connections

    _log = logging.getLogger(__name__)
    close_old_connections()
    try:
        registro = executar_ingestao()
    except Exception as exc:
        tb = traceback.format_exc()
        detalhe = str(exc).strip() or f"{exc.__class__.__name__} sem mensagem"
        _log.exception("[%s] Falha em executar_ingestao (background): %s\n%s", rid, detalhe, tb)
    else:
        _log.info(
            "[%s] Ingestão em background ok registro=%s itens=%s grupos=%s",
            rid,
            registro.id,
            registro.total_itens_ingeridos,
            registro.total_grupos_formados,
        )
    finally:
        close_old_connections()


class FontesRoboView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        qs = FonteRobo.objects.all().order_by("nome")
        return Response(FonteRoboSerializer(qs, many=True).data)

    def post(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        s = FonteRoboSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data, status=status.HTTP_201_CREATED)


class FonteRoboDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_obj(self, pk):
        try:
            return FonteRobo.objects.get(pk=pk)
        except FonteRobo.DoesNotExist:
            return None

    def patch(self, request, pk):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        obj = self._get_obj(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s = FonteRoboSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        obj = self._get_obj(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfigRoboView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        cfg, _ = ConfiguracaoRobo.objects.get_or_create(pk=1)
        return Response(ConfiguracaoRoboSerializer(cfg).data)

    def patch(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        cfg, _ = ConfiguracaoRobo.objects.get_or_create(pk=1)
        s = ConfiguracaoRoboSerializer(cfg, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class ExecucoesRoboView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        qs = RegistroExecucaoIngestao.objects.all().order_by("-executado_em")[:50]
        return Response(RegistroExecucaoIngestaoSerializer(qs, many=True).data)


class ExecutarRoboView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _eh_admin(request.user):
            return Response(status=status.HTTP_403_FORBIDDEN)
        import logging
        import threading
        import traceback

        _log = logging.getLogger(__name__)
        rid = getattr(request, "request_id", "-")
        # A ingestão síncrona (~90 feeds + LLM) excede qualquer timeout
        # HTTP razoável — por isso roda em thread daemon com resposta 202
        # imediata (o progresso é acompanhado via GET /execucoes/).
        # Sem isso, o endpoint só funciona com `--timeout 180` (ou mais) no
        # gunicorn, o que mantém workers presos e contraria o P1-3
        # (ANALISE_CUSTO_PERFORMANCE.md): timeout curto + gthread.
        _log.info("[%s] POST /api/admin/robos/executar aceito (ingestão em background)", rid)
        thread = threading.Thread(
            target=_executar_ingestao_em_background,
            args=(rid,),
            daemon=True,
            name=f"ingestao-manual-{rid}",
        )
        thread.start()
        return Response(
            {"detail": "Ingestão iniciada em background.", "request_id": rid},
            status=status.HTTP_202_ACCEPTED,
        )
