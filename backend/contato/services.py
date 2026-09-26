"""Entrega da mensagem de contato por e-mail — P1-15b.

POR QUE NÃO HÁ PERSISTÊNCIA NESTE MÓDULO
=========================================
Este módulo é o ÚNICO caminho de entrega do formulário de contato e ele é
**sem estado**: não importa `models`, não abre transação, não escreve em
tabela. Isso é deliberado, e a razão vale mais que o código:

1. **Este item não pode criar migration.** A restrição é explícita: nada de
   migration, nada de schema novo. Sem tabela, não há onde guardar a mensagem
   — e a única alternativa honesta seria mentir para quem preencheu o
   formulário.
2. **Não existe decisão de produto sobre onde a mensagem fica.** Persistir
   significa decidir e implementar: modelo `MensagemContato`, política de
   retenção/LGPD (o BRD e a política de privacidade são rascunho —
   `PROD_DECISOES.md` item 4 "Revisão jurídica da privacidade: pendente"),
   rotina de resposta humana, quem lê a fila, e se o histórico é auditável.
   Nenhuma dessas respostas existe hoje. Inventar uma seria decisão de produto
   disfarçada de código.
3. **A mensagem é um e-mail, não um registro.** O canal pretendido pelo BRD é
   "fale com a redação": entregar por e-mail resolve o caso de uso sem criar
   obrigação de retenção de dado pessoal.

O QUE SERIA PRECISO PARA HAVER PERSISTÊNCIA (não fazer sem decisão do Alex):
  a. `backend/contato/migrations/0001_mensagem_contato.py` + `models.py` com
     `nome`, `email`, `mensagem`, `recebida_em`, `respondida_em`, `ip_hash`;
  b. registrar `contato` em `INSTALLED_APPS` (`config/settings.py:103`);
  c. política de retenção e base legal LGPD aprovadas;
  d. rota de leitura pela redação (admin ou painel), com autorização;
  e. decidir se a resposta ao usuário passa a citar o id do registro
     persistido em vez do id opaco gerado aqui (`novo_identificador`).

A REGRA INEGOCIÁVEL: NUNCA 2xx SEM ENTREGA
==========================================
`enviar_mensagem()` só retorna quando `EmailMessage.send()` devolveu ≥ 1
mensagem entregue a um backend que NÃO está na lista de backends que não
entregam nada (`BACKENDS_SEM_ENTREGA_REAL`). Nos demais casos — backend
ausente/console/locmem, destino não configurado, chave do Resend faltando,
provedor recusando, exceção de rede — ela levanta `CanalIndisponivel` ou
`FalhaDeEntrega`, e a view responde **503** (nunca 200/201).

`console.EmailBackend` escrever no stdout é o furo documentado no P0-02c: dá a
impressão de entrega sem entrega nenhuma. Aqui ele é explicitamente recusado.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email

logger = logging.getLogger(__name__)

ASSUNTO = "[Contato] Nova mensagem pelo formulário do portal"
BACKEND_RESEND = "config.email_resend.ResendEmailBackend"

# Backends que NÃO entregam nada a ninguém: escrevem no stdout (console), num
# dicionário em memória (locmem), em disco local (filebased) ou simplesmente
# jogam fora (dummy). Um envio "entregue" por qualquer um deles não chegou a
# nenhuma caixa de entrada, então o endpoint responde 503 em vez de 2xx.
BACKENDS_SEM_ENTREGA_REAL = frozenset(
    {
        "",
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    }
)

# Motivo usado quando o envio foi TENTADO e falhou. É o texto que vai para o
# log e para o 503: NÃO é `str(exc)` do provedor, porque o texto de erro de um
# provedor real pode ecoar o payload enviado, e o corpo da mensagem do usuário
# não pode aparecer em log.
MOTIVO_FALHA_GENERICO = "o provedor de e-mail recusou ou não respondeu ao envio"


class CanalIndisponivel(Exception):
    """Não há canal de entrega real — a mensagem NÃO foi entregue.

    `motivos` é o que o operador precisa ver no log ("o motivo da falha") e o
    que o usuário lê no 503 ("o que está faltando"): as duas pessoas precisam
    da mesma frase. Os motivos são construídos só com NOMES de configuração
    (`DJANGO_EMAIL_BACKEND`, `CONTATO_DESTINO_EMAIL`, `RESEND_API_KEY`) e com o
    caminho do backend — nunca com o endereço de destino nem com chave.
    """

    def __init__(self, motivos: tuple[str, ...]):
        self.motivos = motivos
        super().__init__("; ".join(motivos))


class FalhaDeEntrega(Exception):
    """Há canal configurado, mas o envio concreto falhou — NÃO foi entregue."""


@dataclass(frozen=True)
class Canal:
    """Resultado da verificação de "existe entrega real?".

    `destino` é o endereço já validado (vazio quando indisponível). Ele viaja
    junto do veredito para que o envio use exatamente o endereço que foi
    verificado, e nunca sai daqui: a resposta 503 ao cliente diz *qual*
    configuração falta, nunca o valor.
    """

    disponivel: bool
    motivos: tuple[str, ...]
    destino: str = ""


def novo_identificador() -> str:
    """Id opaco da mensagem, devolvido ao usuário no 2xx.

    Não é id de registro (nada é persistido) e não carrega PII: só serve para
    correlacionar a resposta com a linha de log do envio. `secrets` (não `uuid`)
    porque é opaco e não-sequencial, sem custo de dependência.
    """
    return secrets.token_urlsafe(9)


def _destino_configurado() -> str:
    """Endereço que recebe as mensagens, validado. Vazio se ausente/inválido.

    O valor NUNCA é devolvido ao cliente nem logado: a resposta 503 diz *qual*
    configuração falta, não qual é o endereço.
    """
    destino = (getattr(settings, "CONTATO_DESTINO", "") or "").strip()
    if not destino:
        return ""
    try:
        validate_email(destino)
    except DjangoValidationError:
        return ""
    return destino


def verificar_canal() -> Canal:
    """Diz se existe um canal que entrega e-mail de verdade, e o que falta.

    Chamado ANTES de montar/enviar o e-mail: um `console.EmailBackend` não
    custaria nada para "enviar", e é exatamente aí que nasce a mentira de
    entrega.
    """
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    destino = _destino_configurado()
    motivos: list[str] = []

    if backend in BACKENDS_SEM_ENTREGA_REAL:
        motivos.append(
            f"DJANGO_EMAIL_BACKEND está em '{backend or '(vazio)'}', que não "
            "entrega e-mail a ninguém (só imprime ou descarta)"
        )
    if not destino:
        motivos.append(
            "CONTATO_DESTINO_EMAIL (o endereço que receberia as mensagens) não "
            "está configurado ou não é um e-mail válido"
        )
    if backend == BACKEND_RESEND and not (getattr(settings, "RESEND_API_KEY", "") or "").strip():
        # `config/email_resend.py:27-31` levanta ValueError sem chave: melhor
        # dizer isso com 503 do que estourar um 500 dentro do send().
        motivos.append("RESEND_API_KEY não está configurada, exigida pelo backend Resend")

    return Canal(disponivel=not motivos, motivos=tuple(motivos), destino=destino)


def montar_corpo(*, nome: str, email: str, mensagem: str, identificador: str) -> str:
    """Corpo `text/plain` da mensagem, sem nada que possa virar markup."""
    linhas = [
        "Nova mensagem recebida pelo formulário de contato do portal.",
        "",
        f"Nome informado: {nome}",
        f"E-mail informado: {email}",
        "",
        "Mensagem:",
        mensagem,
        "",
        f"Identificador: {identificador}",
        "",
        "Responda a este e-mail para falar com quem escreveu.",
    ]
    return "\n".join(linhas)


def enviar_mensagem(*, identificador: str, nome: str, email: str, mensagem: str) -> None:
    """Entrega a mensagem. Retorna SÓ se o provedor aceitou.

    Levanta `CanalIndisponivel` (não há entrega configurada) ou
    `FalhaDeEntrega` (o envio concreto não deu certo). Em nenhum dos casos a
    mensagem foi entregue — quem chama (a view) transforma em 503.
    """
    canal = verificar_canal()
    if not canal.disponivel:
        raise CanalIndisponivel(canal.motivos)

    corpo = montar_corpo(
        nome=nome, email=email, mensagem=mensagem, identificador=identificador
    )
    # `EmailMessage` (e não `EmailMultiAlternatives`): o corpo é
    # text/plain e NENHUMA alternativa text/html é anexada. É o que neutraliza
    # `<script>`/`<img onerror>` no corpo do usuário — o HTML viaja como
    # texto inerte, e nenhum cliente de e-mail o interpreta. Nenhum dado
    # fornecido pelo usuário entra em header além do `reply_to` (validado como
    # e-mail pelo serializer, sem quebras de linha — logo, sem injeção de
    # header); o assunto é constante.
    email_msg = EmailMessage(
        subject=ASSUNTO,
        body=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[canal.destino],
        reply_to=[email],
    )

    try:
        enviados = email_msg.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — qualquer falha de entrega é 503
        # Log mínimo: tipo da exceção, sem `str(exc)` (o texto de erro do
        # provedor pode ecoar o payload) e sem traceback (que repetiria esse
        # texto). Nenhum corpo de mensagem, nenhuma credencial.
        logger.error(
            "contato: exceção do provedor de e-mail (tipo=%s)", type(exc).__name__
        )
        raise FalhaDeEntrega(MOTIVO_FALHA_GENERICO) from None

    if not enviados:
        raise FalhaDeEntrega(MOTIVO_FALHA_GENERICO)
