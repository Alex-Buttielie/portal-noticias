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

from config.email_entrega import CanalIndisponivel, FalhaDeEntrega
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

# ---------------------------------------------------------------------------
# DOUBLE OPT-IN — os três estados na resposta, e o 503 que é o quarto caminho
# ---------------------------------------------------------------------------

#: A inscrição foi criada/atualizada e está **aguardando o clique**. É a nova
#: resposta de sucesso, e o texto é o que a pessoa precisa para saber o que
#: fazer nos próximos 7 dias.
#:
#: O texto NÃO promete envio. Diz o que aconteceu ("pedido registrado"), o que
#: acontece agora ("nada é enviado") e o que fazer ("confirme pelo e-mail"). Se
#: o e-mail de confirmação não fosse enviado, este texto seria uma mentira — e
#: é por isso que `inscrever_com_status` tem o portão antes de gravar: este
#: corpo só é alcançado quando a entrega aconteceu de verdade.
DETALHE_PENDENTE = (
    "Pedido de inscrição registrado. Enviamos um e-mail para {destino} com o "
    "link de confirmação: nada da newsletter é enviado para este endereço até "
    "você clicar nesse link. Se não o receber em alguns instantes, confira o "
    "spam ou refaça o pedido."
)
#: A inscrição já estava confirmada e continua. Só acontece quando a pessoa
#: reenvia o formulário e o link de confirmação anterior ainda não foi usado.
DETALHE_CONFIRMADA = (
    "Sua inscrição na newsletter já está confirmada. Você continua recebendo o "
    "resumo normalmente e pode mudar as editorias aqui a qualquer momento."
)

#: Recusa por ausência de canal, com o que FALTA e a garantia de que nada foi
#: gravado.
#:
#: A frase segue o desenho de `identidade.DETALHE_SEM_CANAL` e
#: `contato.DETALHE_SEM_CANAL`: nome do que falta (nunca valor), e a afirmação
#: explícita de que nada foi gravado. Sem essa segunda parte, a pessoa que
#: receber 503 voltaria em dez minutos e tentaria de novo — e não teria como
#: saber se o primeiro pedido tinha ficado pendente para sempre.
DETALHE_SEM_CANAL = (
    "Sua inscrição na newsletter não foi registrada e nada foi gravado: o canal "
    "de e-mail do portal ainda não está com entrega configurada, e uma "
    "inscrição pendente sem e-mail de confirmação seria uma promessa que o "
    "portal não pode cumprir. Motivo: {motivos}"
)

#: Falha de entrega DEPOIS da gravação. Só existe porque o portão é uma
#: verificação e o envio é outra coisa: entre as duas, o provedor pode recusar.
#: A transação reverte, então a resposta é a mesma da ausência de canal — nada
#: foi gravado — com a palavra "gravado" mantida porque ela é a verdade nos
#: dois casos.
DETALHE_FALHA_ENTREGA = (
    "Sua inscrição na newsletter não foi registrada e nada foi gravado: o "
    "provedor de e-mail recusou o envio da confirmação. Tente novamente em "
    "instantes."
)

#: Corpo ÚNICO da confirmação. Mesmo texto, mesmo status, para token válido,
#: inválido, expirado, já usado e de inscrição inexistente.
#:
#: É a MESMA propriedade do descadastro (`DETALHE_DESCADASTRO`), e a razão é a
#: mesma: este endpoint é `AllowAny` e aceita um segredo. Um atacante que
#: conseguisse distinguir "confirmou" de "token inválido" transformaria o clique
#: em um mecanismo de consulta de cadastro — e o que ele conseguiria aprender é
#: que um endereço TEM inscrição pendente no portal. Esse é um dado do titular,
#: e a resposta do portal não pode entregá-lo a quem não é o titular.
#:
#: O texto é redigido para ser útil nos DOIS casos: quem confirmou de verdade lê
#: "está confirmada"; quem clica em link velho ou errado lê "se o link era
#: válido, a inscrição está confirmada" — e nenhuma das duas leituras está
#: errada, porque nenhuma delas afirma que houve confirmação.
DETALHE_CONFIRMACAO = (
    "Pedido de confirmação processado. Se o link que você abriu era válido, a "
    "inscrição está confirmada e o resumo passa a chegar no horário escolhido. "
    "Links antigos deixam de funcionar: se você pedir a inscrição de novo, use o "
    "e-mail mais recente."
)

#: 400 do endpoint de confirmação quando nenhum token veio. Mesmo tratamento do
#: descadastrar: erro de formulário, sem tocar o banco, e a distinção é
#: constante — não carrega informação sobre nenhuma inscrição.
DETALHE_SEM_TOKEN_CONFIRMACAO = (
    "Informe o token de confirmação para concluir a operação."
)


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
        except services.CanalDeConfirmacaoIndisponivel as exc:
            # O PORTÃO, e a única resposta 503 do caminho de escrita. O que
            # importa, e o que o teste
            # `test_sem_canal_a_inscricao_e_recusada_e_nada_e_gravado` prova:
            # `InscricaoNewsletter.objects.count()` não mudou.
            logger.error(
                "newsletter: inscrição recusada (usuario_id=%s) motivo=%s",
                request.user.pk,
                str(exc),
            )
            return Response(
                {"detail": DETALHE_SEM_CANAL.format(motivos="; ".join(exc.motivos))},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except (CanalIndisponivel, FalhaDeEntrega) as exc:
            # O portão passou (o canal existe), mas o envio concreto falhou.
            # `inscrever_com_status` roda a gravação e o envio em
            # `transaction.atomic`, então a linha foi revertida e a resposta é a
            # mesma da ausência de canal: nada foi gravado.
            logger.error(
                "newsletter: inscrição revertida por falha de entrega "
                "(usuario_id=%s) motivo=%s",
                request.user.pk,
                type(exc).__name__,
            )
            return Response(
                {"detail": DETALHE_FALHA_ENTREGA},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "tipo": inscricao.tipo,
                "periodo": inscricao.periodo,
                # `ativa` volta a ser TRUE só depois do clique. Ver
                # `services.inscrever_com_status`.
                "ativa": inscricao.ativa,
                # NOVO no double opt-in, e é o campo que o frontend usa para
                # escolher entre os dois textos de sucesso. Sem ele, a UI teria
                # de adivinhar pelo `ativa` — e adivinhar por um booleano que
                # significa "pode receber" já é um erro conceitual, porque
                # "não pode receber" tem três causas diferentes.
                "estado": inscricao.estado(),
                "confirmada": inscricao.confirmado_em is not None,
                # 201 só quando a linha foi CRIADA. Na segunda inscrição do mesmo
                # e-mail, 200 + `detail` — o mesmo contrato de `landing/`
                # (`landing/views.py:34-35`). Anunciar 201 sem criar nada é
                # dizer ao cliente que existe um recurso novo que não existe.
                #
                # E o texto NÃO é único: os dois estados de sucesso têm textos
                # diferentes, porque a pessoa precisa saber se tem de abrir o
                # e-mail agora ou se já está recebendo. A inspeção de linguagem
                # do frontend (`verificar-*.mjs`) não olha para cá.
                "detail": (
                    DETALHE_CONFIRMADA
                    if inscricao.confirmado_em is not None
                    else DETALHE_PENDENTE.format(destino="o seu e-mail")
                ),
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


class ConfirmarView(APIView):
    """Confirma a inscrição pelo link do e-mail. Sem autenticação (double opt-in).

    Mesmo desenho de `DescadastrarView` — `AllowAny`, mesmo throttle, mesma
    recusa de token vazio, mesma resposta única — e por exatamente os mesmos
    motivos: este endpoint também valida um segredo e também é público, então
    ele também não pode ser uma máquina de dizer "esta pessoa está inscrita".

    A diferença em relação ao descadastro é que aqui a ação NÃO é destrutiva: o
    clique liga a assinatura. Uma resposta neutra seria frustrante demais, e a
    solução não é uma resposta que distinga casos (isso seria o oráculo de
    volta) e sim um texto que seja verdadeiro em todos eles.
    """

    permission_classes = [AllowAny]
    throttle_classes = [EscritaPublicaAnonThrottle]

    def post(self, request):
        token = request.query_params.get("token") or request.data.get("token")
        if not token or not str(token).strip():
            return Response(
                {"detail": DETALHE_SEM_TOKEN_CONFIRMACAO},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # O estado devolvido é IGNORADO de propósito, pelo mesmo motivo que o
        # retorno de `descadastrar_por_token` é ignorado acima: distinguir
        # "confirmada" de "rejeitada" na resposta seria o oráculo. Ele fica no
        # log, que é o lugar certo para a trilha de auditoria.
        estado = services.confirmar_por_token(str(token))

        logger.info(
            "newsletter: resposta de confirmação enviada (estado=%s)", estado
        )
        return Response({"detail": DETALHE_CONFIRMACAO}, status=status.HTTP_200_OK)
