"""
Endpoints de newsletter — `POST/DELETE /api/newsletter/inscrever/` e
`POST /api/newsletter/descadastrar/` (`newsletter/urls.py`, montado em
`config/urls.py:38`). P1-06.

O QUE ESTES ENDPOINTS GARANTEM
==============================
| endpoint                | quem pode                    | limite                    |
|-------------------------|------------------------------|---------------------------|
| `/inscrever/` POST      | autenticado (`IsAuthenticated`) | `EscritaPublicaAnonThrottle` |
| `/inscrever/` DELETE    | autenticado                  | idem                       |
| `/descadastrar/` POST   | qualquer um (`AllowAny`)     | idem                       |

O throttle é o MESMO escopo `escrita_publica` (20/min por IP,
`config/settings.py:526`) já usado por cadastro, lista de espera, criação de
publicação e `contato/`. O que ele de fato protege, com honestidade sobre o
alcance:

* **`/descadastrar/` (AllowAny) — é o limite efetivo.** É o único endpoint do
  módulo que aceita chamada anônima, e o único que valida um segredo: sem
  limite, um atacante testa tokens à vontade e o comprimento do segredo (43
  chars de `secrets.token_urlsafe`) é a única defesa que sobra. 60 POSTs
  seguidos devolviam 400 em todos — medido antes da correção.
* **`/inscrever/` (IsAuthenticated) — guarda de defesa em profundidade.**
  `AnonRateThrottle` só conta requisições de cliente **não autenticado**
  (`config/throttling.py:16-18`), e o DRF checa throttling depois das
  permissões, então quem não tem token já recebe 401 antes de a contagem
  existir. Aqui o limite NÃO segura o abuso por conta logada. Fica pelo mesmo
  motivo dos outros pontos de escrita pública do projeto: é a classe
  padronizada para escrita pública, e se esta view virar `AllowAny` — o que o
  próprio `frontend/app/newsletter/NewsletterForm.tsx:23-31` já prevê como
  próximo passo, com o caminho público hoje em `landing/` — ela já está
  limitada, sem uma segunda alteração.

DESCADASTRO NÃO REVELA CADASTRO (o ponto legal deste item)
==========================================================
O endpoint aceita um token e responde **uma única coisa**, igual para token
válido, inválido, expirado, já usado ou de outro e-mail: 200 com o mesmo corpo.
Não existe "não encontrado". A decisão é do titular (art. 8º, V da LGPD) e a
resposta não pode transformar o direito em mecanismo de consulta de cadastro —
uma resposta que distingue "inscrito" de "não inscrito" confirma a um terceiro
que o e-mail de alguém está na base do portal.

O único caso que responde diferente é **nenhum token ter sido enviado**, e ele é
400 sem tocar o banco: é erro de formulário (o campo veio vazio), não uma
resposta sobre cadastro. A distinção é constante e não carrega informação
nenhuma sobre nenhuma pessoa.

O texto do 200 é deliberadamente neutro e ainda assim útil: quem realmente se
descadastrou recebe a confirmação, e quem chegou com link velho recebe a
instrução de usar o e-mail mais recente em vez de um "não existe" que o
denunciaria.
"""

from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.throttling import EscritaPublicaAnonThrottle

from . import services
from .models import InscricaoNewsletter

logger = logging.getLogger(__name__)

DETALHE_SEM_TOKEN = "Informe o token de descadastro para concluir a operação."

# Corpo ÚNICO do descadastro. Mesmo texto, mesmo status, para token válido,
# inválido, expirado ou já usado. Não diz "não encontramos", não diz "já
# estava descadastrado", não confirma nada sobre o e-mail.
DETALHE_DESCADASTRO = (
    "Pedido de descadastro registrado. Se a inscrição existia, ela foi cancelada "
    "e nenhum outro e-mail será enviado. Se você continuar recebendo, use o link "
    "do e-mail mais recente — os links antigos expiram."
)

DETALHE_REINSCRICAO = "Inscrição atualizada com as escolhas enviadas."
DETALHE_OK = "Inscrição registrada."


class InscreverView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        tipo = request.data.get("tipo", InscricaoNewsletter.TIPO_PADRAO)
        categorias = request.data.get("categorias", [])
        periodo = request.data.get("periodo")
        try:
            inscricao, criado = services.inscrever_com_status(
                request.user, tipo, categorias, periodo=periodo
            )
        except services.RecursoGatedError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except services.ConsentimentoAusenteError as exc:
            # 403 e não 400: o pedido está bem formado, quem falta é a base
            # legal registrada para esta conta.
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(
            {
                "tipo": inscricao.tipo,
                "periodo": inscricao.periodo,
                "ativa": inscricao.ativa,
                # 201 só quando a linha foi CRIADA. Na segunda inscrição do mesmo
                # e-mail, 200 + `detail` — o mesmo contrato de `landing/`
                # (`landing/views.py:34-35`). Anunciar 201 sem criar nada é
                # dizer ao cliente que existe um recurso novo que não existe.
                "detail": DETALHE_OK if criado else DETALHE_REINSCRICAO,
            },
            status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK,
        )

    def delete(self, request):
        services.cancelar_inscricao(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DescadastrarView(APIView):
    """Descadastro pelo link do e-mail. Sem autenticação (P1-06)."""

    permission_classes = [AllowAny]
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        token = request.query_params.get("token") or request.data.get("token")
        if not token or not str(token).strip():
            # Nenhum token: erro de formulário, sem nenhuma consulta ao banco.
            return Response({"detail": DETALHE_SEM_TOKEN}, status=status.HTTP_400_BAD_REQUEST)

        # O retorno é ignorado de propósito. Ele distingue "token apresentado"
        # de "nenhum token", e essa é exatamente a distinção que a resposta
        # NÃO pode fazer: token válido, inválido, expirado e já usado caem
        # todos no mesmo 200 com o mesmo corpo. Logar o resultado aqui (e não o
        # token) é o que dá ao operador a trilha de auditoria sem reintroduzir
        # o oráculo na resposta.
        services.descadastrar_por_token(str(token))

        return Response({"detail": DETALHE_DESCADASTRO}, status=status.HTTP_200_OK)
