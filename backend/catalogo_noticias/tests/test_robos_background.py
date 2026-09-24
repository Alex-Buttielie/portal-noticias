"""Testes do contrato HTTP 202 + execução em background dos robôs."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from catalogo_noticias import robos_views
from catalogo_noticias.models import RegistroExecucaoIngestao

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_executar_robo_responde_202_e_expoe_execucao_apos_background():
    """POST responde imediatamente e o registro fica visível no GET posterior.

    ``executar_ingestao`` é mockado para manter o teste offline e rápido. O
    mock grava um registro real no banco, sinaliza sua conclusão e o teste
    faz polling do endpoint de execuções. Assim a prova não depende de uma
    ingestão real nem deixa a thread daemon pendente no encerramento.
    """
    admin = User.objects.create_user(
        email="admin-background-robos@example.com",
        password="senha123",
        papel="admin",
    )
    client = APIClient()
    client.force_authenticate(user=admin)

    execution_allowed = threading.Event()
    background_started = threading.Event()
    background_finished = threading.Event()
    registro_id: int | None = None
    background_error: Exception | None = None

    def fake_executar_ingestao():
        nonlocal registro_id, background_error
        background_started.set()
        try:
            # O teste segura deliberadamente a execução até depois da resposta
            # HTTP. Uma implementação síncrona ficaria bloqueada aqui e não
            # poderia provar o contrato 202+background.
            if not execution_allowed.wait(timeout=10):
                raise TimeoutError("mock de ingestão não foi liberado pelo teste")
            registro = RegistroExecucaoIngestao.objects.create(
                itens_por_fonte={"Mock": 1},
                total_itens_ingeridos=1,
                total_grupos_formados=1,
            )
            registro_id = registro.id
            return registro
        except Exception as exc:  # pragma: no cover - apenas em falha inesperada
            background_error = exc
            raise
        finally:
            background_finished.set()

    with patch.object(
        robos_views,
        "executar_ingestao",
        side_effect=fake_executar_ingestao,
    ) as executar_mock:
        try:
            resposta = client.post(
                "/api/admin/robos/executar/",
                format="json",
                HTTP_X_REQUEST_ID="req-background-test-202",
            )

            assert resposta.status_code == 202
            assert resposta.data == {
                "detail": "Ingestão iniciada em background.",
                "request_id": "req-background-test-202",
            }
            assert background_started.wait(timeout=10), (
                "a thread de ingestão não iniciou dentro do timeout"
            )
            assert not background_finished.is_set(), (
                "a resposta 202 foi devolvida somente depois da ingestão terminar"
            )
        finally:
            # Libera o mock mesmo se uma asserção falhar, evitando deixar uma
            # thread daemon bloqueada no encerramento do teste.
            execution_allowed.set()

        # A thread pode terminar logo após a liberação; aguardamos com timeout
        # para não testar apenas o start() e não depender de sleep fixo.
        assert background_finished.wait(timeout=10), (
            "a thread de ingestão não concluiu dentro do timeout"
        )
        if background_error is not None:
            raise background_error
        assert executar_mock.call_count == 1
        assert registro_id is not None

        # Polling explícito: prova que a execução aparece no contrato público
        # somente depois de concluída, sem depender de sleep fixo.
        deadline = time.monotonic() + 10
        encontrado = False
        lista = None
        while time.monotonic() < deadline:
            lista = client.get("/api/admin/robos/execucoes/")
            if lista.status_code == 200 and any(
                item["id"] == registro_id for item in lista.data
            ):
                encontrado = True
                break
            time.sleep(0.05)

        assert encontrado, "a execução não apareceu em /api/admin/robos/execucoes/"
        assert lista is not None
        assert lista.status_code == 200

        # A execução já terminou, mas garantimos também que a thread daemon
        # não ficou viva quando o teste devolve o controle ao pytest.
        thread_name = "ingestao-manual-req-background-test-202"
        deadline_thread = time.monotonic() + 10
        while time.monotonic() < deadline_thread and any(
            thread.name == thread_name and thread.is_alive()
            for thread in threading.enumerate()
        ):
            time.sleep(0.01)
        assert not any(
            thread.name == thread_name and thread.is_alive()
            for thread in threading.enumerate()
        ), "a thread daemon de ingestão continuou pendente"
