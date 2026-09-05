from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConfiguracaoRobo, FonteRobo, RegistroExecucaoIngestao
from .robos_serializers import ConfiguracaoRoboSerializer, FonteRoboSerializer, RegistroExecucaoIngestaoSerializer
from .services.ingestao import executar_ingestao


def _eh_admin(user):
    return getattr(user, "papel", None) == "admin"


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
        try:
            registro = executar_ingestao()
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(RegistroExecucaoIngestaoSerializer(registro).data, status=status.HTTP_201_CREATED)
