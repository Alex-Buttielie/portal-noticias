from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConfiguracaoRobo, FonteRobo, RegistroExecucaoIngestao
from .permissions import IsAdmin
from .robos_serializers import ConfiguracaoRoboSerializer, FonteRoboSerializer, RegistroExecucaoIngestaoSerializer
from .services.ingestao import executar_ingestao


def _executar_ingestao_em_background(rid: str) -> None:
    """Roda `executar_ingestao()` e registra o resultado.

    O endpoint responde 202 antes; o SUCESSO fica registrado em
    `RegistroExecucaoIngestao` (visível em GET /execucoes/). C-05
    (implementation-contract.md run 20261013-1048-home-radar-central-ux):
    a FALHA (exceção não isolada por `executar_ingestao()` — erro de
    infra, não um item/grupo individual) também é persistida, como um
    `RegistroExecucaoIngestao` com `falhou=True`/`erro_falha` preenchido —
    antes desta run, só ia para o log (com traceback e `request_id`, que
    continuam sendo o caminho de investigação profunda; aqui só garante que
    a FALHA aparece em algum lugar da Central, não só no log do servidor).

    Função pura em termos de conexão: não fecha/abre conexão de banco —
    isso é responsabilidade de quem a chama (ver `_executar_ingestao_thread`
    para o caso real de thread em background). Chamá-la diretamente (sem
    thread), como fazem os testes de C-05, é seguro porque ela nunca
    descarta a conexão de quem a invoca.
    """
    import logging
    import traceback

    _log = logging.getLogger(__name__)
    try:
        registro = executar_ingestao()
    except Exception as exc:
        tb = traceback.format_exc()
        detalhe = str(exc).strip() or f"{exc.__class__.__name__} sem mensagem"
        _log.exception("[%s] Falha em executar_ingestao (background): %s\n%s", rid, detalhe, tb)
        try:
            RegistroExecucaoIngestao.objects.create(
                falhou=True,
                # Trunca para não depender do tamanho exato da coluna
                # (TextField não tem limite real no Postgres, mas um
                # traceback inteiro na listagem da Central não ajuda quem
                # está triando — o log do servidor tem a versão completa).
                erro_falha=f"[{rid}] {detalhe}\n{tb}"[:4000],
            )
        except Exception:
            _log.exception("[%s] Falha ao persistir o registro de FALHA da ingestão.", rid)
    else:
        _log.info(
            "[%s] Ingestão em background ok registro=%s itens=%s grupos=%s",
            rid,
            registro.id,
            registro.total_itens_ingeridos,
            registro.total_grupos_formados,
        )


def _executar_ingestao_thread(rid: str) -> None:
    """Entry point real da thread `daemon` iniciada por `ExecutarRoboView`.

    Conexões de banco por thread: o Django abre uma nova por thread sob
    demanda, mas uma thread do SO pode ser reaproveitada por runtime
    (ex. thread pool); `close_old_connections()` ao entrar evita herdar uma
    conexão stale, e ao saír evita prender uma conexão aberta na thread que
    termina. Isolado em cima de `_executar_ingestao_em_background` (que não
    toca conexão) para não derrubar a conexão de quem chama essa função
    fora de uma thread de verdade (ex. os testes de C-05, que chamam
    `_executar_ingestao_em_background` direto, sem thread, de propósito).

    Risco aceito e documentado: thread `daemon` morre se o PM2 reiniciar o
    processo no meio da ingestão. Migrar para Celery é o destino correto.
    """
    from django.db import close_old_connections

    close_old_connections()
    try:
        _executar_ingestao_em_background(rid)
    finally:
        close_old_connections()


class FontesRoboView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = FonteRobo.objects.all().order_by("nome")
        return Response(FonteRoboSerializer(qs, many=True).data)

    def post(self, request):
        s = FonteRoboSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data, status=status.HTTP_201_CREATED)


class FonteRoboDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def _get_obj(self, pk):
        try:
            return FonteRobo.objects.get(pk=pk)
        except FonteRobo.DoesNotExist:
            return None

    def patch(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        s = FonteRoboSerializer(obj, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)

    def delete(self, request, pk):
        obj = self._get_obj(pk)
        if not obj:
            return Response(status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfigRoboView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        cfg, _ = ConfiguracaoRobo.objects.get_or_create(pk=1)
        return Response(ConfiguracaoRoboSerializer(cfg).data)

    def patch(self, request):
        cfg, _ = ConfiguracaoRobo.objects.get_or_create(pk=1)
        s = ConfiguracaoRoboSerializer(cfg, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(s.data)


class ExecucoesRoboView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = RegistroExecucaoIngestao.objects.all().order_by("-executado_em")[:50]
        return Response(RegistroExecucaoIngestaoSerializer(qs, many=True).data)


class ExecutarRoboView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def post(self, request):
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
            target=_executar_ingestao_thread,
            args=(rid,),
            daemon=True,
            name=f"ingestao-manual-{rid}",
        )
        thread.start()
        return Response(
            {"detail": "Ingestão iniciada em background.", "request_id": rid},
            status=status.HTTP_202_ACCEPTED,
        )
