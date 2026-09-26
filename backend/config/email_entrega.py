"""A REGRA INEGOCIÁVEL: NUNCA 2xx (NEM NENHUM "ENTREGUE") SEM ENTREGA REAL.

Este é o ÚNICO lugar do projeto que decide se existe canal de entrega de
e-mail de verdade. Ele nasceu aqui (P1-04) e foi extraído de
`contato/services.py`, que já o aplicava só para o formulário de contato.

O que o P0-02c documentou e que ninguém fechava
=================================================
`DJANGO_EMAIL_BACKEND` tem como padrão `console.EmailBackend`
(`config/settings.py:615-617`). Com ele, `django.core.mail.send_mail`
**devolve 1 e imprime a mensagem no stdout** — o chamador, sem saber,
"entregou" o e-mail. Quem traduzia isso em resposta HTTP eram os caminhos do
módulo `identidade/`:

  * `identidade/views.py` `CadastroView` respondia **201** ("Verifique seu
    e-mail para confirmar a conta") com o e-mail de verificação apenas
    impresso no stdout do container;
  * `identidade/views.py` `RecuperarSenhaView` respondia **200** ("enviaremos
    instruções de redefinição de senha") sem enviar nada;
  * `newsletter/services.py` contava `total_enviados += 1` para cada
    impressão em stdout — e é esse contador que o operador lê.

O sintoma é o pior possível: o usuário fica esperando um e-mail que nunca
chega, não tem como recuperar, e o deploy reporta sucesso.

O QUE ESTE MÓDULO FAZ
======================
Duas verificações, porque cada uma pega uma mentira diferente:

1. **Antes de qualquer trabalho** (`verificar_canal_email`): o
   `EMAIL_BACKEND` está na lista de backends que **aceitam a mensagem e não a
   entregam a ninguém**? Se estiver, levanta `CanalIndisponivel` — sem
   gerar token, sem montar e-mail, sem tocar na rede. É o que impede a
   impressão no stdout e o que impede o vazamento do token no log.
2. **Depois do envio** (`entregar_email`): o provedor devolveu ≥ 1? Se
   devolveu 0, levanta `FalhaDeEntrega`. Pega o outro caso, o provedor que
   aceita a conexão e descarta a mensagem.

Qualquer caminho que só verifica (1) aceita um provedor que engole; só
verifica (2) aceita o stdout. As duas são obrigatórias.

ESCOPO E O QUE ESTE MÓDULO NÃO DECIDE
=====================================
  * Destino é específico de cada fluxo (`contato` tem `CONTATO_DESTINO`), e
    por isso NÃO mora aqui — `contato/services.py` acrescenta a checagem
    própria do destino à checagem de canal daqui.
  * Enumeração de conta é problema do endpoint, não do canal. A verificação
    e a redefinição de senha **não podem** virar 503 por causa do e-mail ter
    conta ou não (a resposta tem de ser indistinguível), então elas não
    reportam falha de entrega ao cliente: registram em log/métrica/health e
    mantêm a resposta neutra. Ver `identidade/views.py`.
  * A lista de backends recusados é a mesma que a de `contato` — por isso
    `contato/services.py` importa daqui, e não o contrário. Uma lista só.
    A `newsletter/` também importa daqui (P1-04), e pelos mesmos dois motivos:
    o gate é o mesmo e um app de newsletter não depende de um app de contato.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMessage

from .health import METRICAS

logger = logging.getLogger(__name__)

#: Caminho pontilhado do backend de e-mail que entrega de verdade.
BACKEND_RESEND = "config.email_resend.ResendEmailBackend"

#: Backends que NÃO entregam nada a ninguém: escrevem no stdout (console),
#: num dicionário em memória (locmem), em disco local (filebased) ou
#: simplesmente jogam fora (dummy). Um envio "entregue" por qualquer um
#: deles não chegou a nenhuma caixa de entrada, então o chamador tem de
#: responder erro em vez de 2xx.
#:
#: `""` está aqui porque `EMAIL_BACKEND` vazio cai no default do Django,
#: que é `smtp` apontando para o host local — não é um canal configurado, é
#: um envio que falha em tempo de conexão, sempre.
BACKENDS_SEM_ENTREGA_REAL = frozenset(
    {
        "",
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
    }
)

#: Motivo usado quando o envio foi TENTADO e falhou. É o texto que vai para o
#: log e para a resposta de erro: NÃO é `str(exc)` do provedor, porque o
#: texto de erro de um provedor real pode ecoar o payload enviado — e o
#: payload do e-mail de verificação/redefinição CONTÉM o token de uso único.
#: Copiar o texto do provedor para o log é, literalmente, vazar o token.
MOTIVO_FALHA_GENERICO = "o provedor de e-mail recusou ou não respondeu ao envio"


def orientacao_de_configuracao() -> str:
    """Frase que diz QUAL configuração falta — e nunca o valor dela.

    `verificar_canal_email` diz o que está errado (`motivos`); esta diz o que
    fazer. Os dois moram aqui porque são o mesmo segredo operacional: um caminho
    que recusa entrega e não diz o que definir obriga o operador a caçar a
    configuração sozinho, e foi exatamente o que o P0-02c registrou.

    É texto de LOG e de resposta de erro, então são só NOMES de variável e o
    caminho do backend: nenhum endereço, nenhuma chave, nenhum token. Chave de
    verdade é `re_...` no texto — o valor nunca sai daqui.
    """
    return (
        f"Para que exista entrega real: defina DJANGO_EMAIL_BACKEND="
        f"{BACKEND_RESEND} e RESEND_API_KEY=re_... (chave em "
        f"https://resend.com/api-keys, com o remetente de domínio verificado) "
        f"antes de tratar o envio como entregue. Estado da integração: "
        f"PROD_DECISOES.md, item 2."
    )


class CanalIndisponivel(Exception):
    """Não há canal de entrega real — a mensagem NÃO foi entregue.

    `motivos` é o que o operador precisa ver no log ("o motivo da falha") e o
    que a resposta de erro mostra ao cliente ("o que está faltando"): as duas
    pessoas precisam da mesma frase. Os motivos são construídos só com NOMES
    de configuração (`DJANGO_EMAIL_BACKEND`, `RESEND_API_KEY`) e com o caminho
    do backend — nunca com o endereço de destino, nunca com a chave, nunca
    com o token.
    """

    def __init__(self, motivos: tuple[str, ...]):
        self.motivos = motivos
        super().__init__("; ".join(motivos))


class FalhaDeEntrega(Exception):
    """Há canal configurado, mas o envio concreto falhou — NÃO foi entregue."""


@dataclass(frozen=True)
class Canal:
    """Resultado da verificação de "existe entrega real?".

    `destino` fica de fora de propósito: destino é de cada fluxo, e esta
    estrutura é compartilhada.
    """

    disponivel: bool
    motivos: tuple[str, ...]


def verificar_canal_email() -> Canal:
    """Diz se existe um canal que entrega e-mail de verdade, e o que falta.

    Chamado ANTES de montar/enviar o e-mail: um `console.EmailBackend` não
    custaria nada para "enviar", e é exatamente aí que nasce a mentira de
    entrega.
    """
    backend = (getattr(settings, "EMAIL_BACKEND", "") or "").strip()
    motivos: list[str] = []

    if backend in BACKENDS_SEM_ENTREGA_REAL:
        motivos.append(
            f"DJANGO_EMAIL_BACKEND está em '{backend or '(vazio)'}', que não "
            "entrega e-mail a ninguém (só imprime ou descarta)"
        )
    if backend == BACKEND_RESEND and not (getattr(settings, "RESEND_API_KEY", "") or "").strip():
        # `config/email_resend.py:28-33` levanta ValueError sem chave: melhor
        # dizer isso com erro claro do que estourar um 500 dentro do send().
        motivos.append("RESEND_API_KEY não está configurada, exigida pelo backend Resend")

    return Canal(disponivel=not motivos, motivos=tuple(motivos))


def registrar_evento(destino: str, situacao: str) -> None:
    """Conta o desfecho de uma tentativa de entrega em `/metrics`.

    `situacao` é um rótulo fechado (`entregue`, `sem_canal`, `falha`) e
    `destino` também é fechado (`cadastro`, `verificacao`, `redefinicao`,
    `newsletter`, `contato`). Nenhum dos dois recebe dado do usuário: a
    métrica é agregada e não pode virar um oráculo de existência de conta.
    """
    METRICAS.incrementar(
        "portal_email_entrega_total", 1.0, destino=destino, situacao=situacao
    )


def entregar_email(mensagem: EmailMessage, *, destino: str) -> int:
    """Entrega UM e-mail. Retorna SÓ se o provedor aceitou.

    Levanta `CanalIndisponivel` (não há entrega configurada) ou
    `FalhaDeEntrega` (o envio concreto não deu certo). Em nenhum dos casos a
    mensagem foi entregue — quem chama (a view) transforma em erro.

    `destino` é só o rótulo da métrica, nunca o endereço.
    """
    canal = verificar_canal_email()
    if not canal.disponivel:
        registrar_evento(destino, "sem_canal")
        raise CanalIndisponivel(canal.motivos)

    try:
        enviados = mensagem.send(fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — qualquer falha é "não entregue"
        # Log mínimo: tipo da exceção, sem `str(exc)` (o texto de erro do
        # provedor pode ecoar o payload — que no e-mail de verificação
        # carrega o token) e sem traceback (que repetiria esse texto).
        # Nenhum corpo de mensagem, nenhum endereço, nenhuma credencial.
        METRICAS.incrementar(
            "portal_email_falha_provedor_total", 1.0, destino=destino, tipo=type(exc).__name__
        )
        logger.error(
            "email: exceção do provedor ao entregar (destino=%s tipo=%s)",
            destino,
            type(exc).__name__,
        )
        registrar_evento(destino, "falha")
        raise FalhaDeEntrega(MOTIVO_FALHA_GENERICO) from None

    if not enviados:
        # Provedor aceitou a conexão e não entregou nada. Também é mentira de
        # entrega, e é por isso que a checagem pós-envio existe.
        logger.error(
            "email: o provedor aceitou a conexão e não entregou nada (destino=%s)",
            destino,
        )
        registrar_evento(destino, "falha")
        raise FalhaDeEntrega(MOTIVO_FALHA_GENERICO)

    registrar_evento(destino, "entregue")
    return enviados
