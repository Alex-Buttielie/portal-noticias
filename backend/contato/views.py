"""`POST /api/contato/` — recebimento da mensagem do formulário de contato.

Este é o item P1-15b. Diagnóstico que motivou o item: o formulário do frontend
(`frontend/app/contato/ContatoForm.tsx`, branch `p1-15-rotas-formularios`) está
deliberadamente sem chamada de rede porque `POST /api/contato/` respondia 404 —
não existe endpoint de contato no backend. Este módulo fecha o lado do servidor.

CONTRATO
========
`POST /api/contato/` — JSON `{nome, email, mensagem}` (+ `website` só para
honeypot, ver abaixo).

| status | quando                                                            | corpo |
|--------|-------------------------------------------------------------------|-------|
| 200    | o provedor de e-mail **aceitou e entregou** a mensagem            | `{"detail": "...", "id": "<id opaco>"}` |
| 400    | payload inválido (campo faltando, e-mail inválido, tamanho) ou armadilha preenchida | `{"campo": ["..."]}` (DRF) ou `{"non_field_errors": ["Requisição rejeitada."]}` |
| 429    | mais de N mensagens do mesmo IP no intervalo configurado           | `{"detail": "Request was throttled."}` + `Retry-After` |
| 503    | **não foi entregue**: sem backend de entrega real, sem destino, sem chave do Resend, ou o provedor recusou | `{"detail": "<motivo acionável>", "request_id": "<id>"}` |

O `{"detail": ...}` é o formato que o cliente do frontend já sabe renderizar
(`frontend/lib/api.ts:32-56`: `extrairMensagemDeErro` lê `detail` e, se houver,
acrescenta o `request_id`), então o 503 aparece no `role="alert"` do formulário
com o texto real do motivo — a UI mostra a verdade em vez de um "enviado!"
falso.

POR QUE 200 E NÃO 201
=====================
O projeto usa 201 nas escritas que criam registro (`landing.views:36`,
`newsletter.views:21`). Aqui **nada é criado**: a mensagem não vira linha em
nenhuma tabela (ver a justificativa completa em `contato/services.py`, topo).
Responder 201 Created seria anunciar um recurso que não existe. 200 é o status
honesto para "ação executada com sucesso, sem recurso novo".

ALLOWANY + RATE LIMIT + VALIDAÇÃO + HONEYPOT
=============================================
`AllowAny` é inevitável (é um formulário público, sem conta), e por isso a
view é fechada pelos quatro lados que o projeto já usa:
  1. **Rate limit por IP** — `EscritaPublicaAnonThrottle`
     (`config/throttling.py:24-34`), o MESMO escopo `escrita_publica` (20/min
     por padrão, `config/settings.py:371`) já usado por cadastro, lista de
     espera e criação de publicação. Contato é, pelo perfil, exatamente isso:
     escrita pública de baixo volume. Reusar o escopo significa um único
     regulador, uma taxa já documentada e nenhuma configuração nova.
  2. **Validação** — `MensagemContatoSerializer`, com limites herdados da UI.
  3. **Honeypot** — o projeto não tem captcha nem honeypot em lugar nenhum
     (`grep -rniE "honeypot|captcha" backend/ --include=*.py` → nada), e
     contato é o endpoint mais atraente para spam (dispara e-mails, consome
     cota do provedor, serve de isca de phishing com o nome do portal). O
     campo `website` é invisível para o usuário legítimo; se vier preenchido,
     a mensagem é **descartada e a resposta é 400 genérica** — nunca 2xx, porque
     nada foi entregue.
  4. **Log mínimo** — identificador da tentativa, resultado e motivo. Nunca o
     corpo da mensagem, nunca o endereço de destino, nunca credencial.

SEM PERSISTÊNCIA — leia o topo de `contato/services.py`: a justificativa de por
que não há `models.py`/migration (e o que precisaria existir para haver) está
lá, justamente para ninguém "resolver" a ausência de persistência com um
`console.EmailBackend` daqui a seis meses.

O QUE O FRONTEND PRECISA ENVIAR (branch `p1-15-rotas-formularios`, follow-up)
===========================================================================
`POST /api/contato/` com `Content-Type: application/json` e
`{"nome": ..., "email": ..., "mensagem": ...}` — os mesmos nomes de campo dos
`name` do formulário (`ContatoForm.tsx:134,156,179`). Mais um campo
`website`, que precisa ser **invisível** para quem preenche (por exemplo
`<input className="hidden" tabIndex={-1} autoComplete="off" aria-hidden="true">`
dentro do form): o backend o ignora quando vem vazio e descarta a submissão
quando vem preenchido. Respostas: 200 `{"detail","id"}`, 400 `{campo:["..."]}`,
503 `{"detail","request_id"}` — todos os três são renderizáveis pelo
`extrairMensagemDeErro` de `frontend/lib/api.ts:32-56`.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttling import EscritaPublicaAnonThrottle

from . import services
from .serializers import MensagemContatoSerializer

logger = logging.getLogger(__name__)

# Mensagem exibida ao usuário quando a entrega não aconteceu. Diz o que está
# faltando (nome da configuração, nunca o valor) e que nada foi gravado, para
# a pessoa não ficar achando que a mensagem se perdeu em algum lugar.
DETALHE_SEM_CANAL = (
    "Sua mensagem não foi enviada e não foi gravada em lugar nenhum: o canal "
    "de contato do portal ainda não está com entrega de e-mail configurada. "
    "Motivo: {motivos}"
)

DETALHE_FALHA_ENTREGA = (
    "Sua mensagem não foi entregue: o provedor de e-mail recusou o envio. "
    "Nada foi gravado. Tente novamente em instantes ou use a newsletter."
)

DETALHE_OK = (
    "Mensagem enviada. A redação responde em até 2 dias úteis. Guarde o "
    "identificador abaixo caso precise citar esta mensagem."
)


class ContatoView(APIView):
    """Recebe e entrega a mensagem de contato. Sem autenticação, com throttle."""

    permission_classes = [AllowAny]
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        serializer = MensagemContatoSerializer(data=request.data)
        # `raise_exception=True` → 400 com o corpo padrão do DRF
        # ({campo: ["mensagem"]}), que é o que a UI já sabe mostrar.
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data

        identificador = services.novo_identificador()
        # O `request_id` vai no corpo da resposta de erro para o usuário poder
        # citar, e o LOGGING de `config/settings.py:936-971` já injeta
        # `request_id` em toda linha de log via `RequestIdLogFilter` — por isso
        # as mensagens de log abaixo não o repetem.
        request_id = getattr(request, "request_id", None) or ""

        try:
            services.enviar_mensagem(identificador=identificador, **dados)
        except services.CanalIndisponivel as exc:
            logger.warning(
                "contato: NÃO entregue (tentativa=%s) motivo=%s",
                identificador,
                str(exc),
            )
            return Response(
                {
                    "detail": DETALHE_SEM_CANAL.format(motivos="; ".join(exc.motivos)),
                    "request_id": request_id,
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except services.FalhaDeEntrega as exc:
            # O texto de `FalhaDeEntrega` é genérico de propósito: o log do
            # provedor (`contato/services.py`) não copia a mensagem de erro
            # dele, e o cliente recebe só o motivo genérico.
            logger.warning(
                "contato: NÃO entregue (tentativa=%s) motivo=%s",
                identificador,
                str(exc),
            )
            return Response(
                {"detail": DETALHE_FALHA_ENTREGA, "request_id": request_id},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info("contato: entregue (id=%s)", identificador)
        return Response({"detail": DETALHE_OK, "id": identificador})
