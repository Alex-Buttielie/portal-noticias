"""
Controles de segurança do login social via Google — módulo `identidade`.

POR QUE ESTE MÓDULO EXISTE
--------------------------
O login social deste projeto **não** é o Authorization Code flow do
OAuth 2.0. Não existe redirect do backend para o Google, não existe `code`
para trocar, não existe `redirect_uri` enviado ao Google e não existe
callback do Google no backend. A UI resolve o OAuth no navegador com o
Google Identity Services e o front envia para `POST /api/auth/google/` o
`id_token` (JWT) que o Google assinou.

Isso tem duas consequências que este módulo resolve:

1. **Não existe `state`.** O anti-CSRF clássico do OAuth é o `state`:
   um valor aleatório emitido pelo backend, amarrado à sessão do
   navegador, de uso único, verificado no retorno e não previsível. Como
   este fluxo não redireciona o navegador, o `state` não tem onde "morar"
   no protocolo. O equivalente correto aqui é o par **`state` emitido pelo
   backend + `nonce` assinado dentro do `id_token`**: o backend emite o
   nonce, o front o passa ao Google no botão do GIS, o Google o devolve
   dentro do `id_token` assinado, e o backend confere os dois. Isso
   entrega, de fato, tudo o que o `state` entregaria: amarração à sessão
   do navegador (quem não tem a sessão não tem o nonce), uso único
   (replay de um `id_token` capturado é rejeitado), não previsível
   (`secrets.token_urlsafe`, 256 bits) e verificação contra uma
   asserção assinada pelo provedor (não apenas contra o corpo do POST,
   que um site terceiro poderia forjar).

   Sem esse par, o endpoint `POST /api/auth/google/` é um POST anônimo
   sem proteção CSRF (DRF só exige CSRF em requisição autenticada por
   sessão) que devolve um token de API válido. Um site atacante poderia
   forçar o navegador da vítima a executar esse POST com um `id_token`
   que ele próprio possui e **vincular a conta Google do atacante à
   conta da vítima** — um backdoor durável, porque a vinculação fica
   persistida no banco. Com o nonce, o site atacante não consegue ler a
   resposta de `/api/auth/google/iniciar/` (CORS só libera a origem do
   próprio front), logo não consegue obter o nonce, logo o POST forçado
   é rejeitado.

2. **Não existe troca de `code`, então o `code` não é o problema — o
   `email_verified` é.** `django-allauth` já valida assinatura (RS256
   contra os certificados do Google), `iss`, `aud` (o `client_id`) e
   `exp` do `id_token`, e o próprio allauth só auto-conecta por e-mail
   quando o endereço veio marcado como verificado. Mas a view deste
   projeto fazia a busca de conta local por e-mail **por conta própria**,
   sem olhar o `email_verified`, e vinculava a conta encontrada. Um
   `id_token` com `email_verified: false` — que o Google emite de
   verdade para contas de domínio que o administrador ainda não
   verificou — virava login com token válido na conta local de outra
   pessoa, sem senha e sem prova de posse. `email_do_provider_verificado`
   fecha isso.

AUDITORIA
---------
`auditar_login_google` registra todo desfecho (sucesso e falha) com um
conjunto **fixo** de campos. O `id_token` — e qualquer access token —
nunca entra no log: o `logger.exception` que existia antes foi
substituído pelo tipo da exceção, justamente porque traceback de
biblioteca é o tipo de coisa que um dia passa a carregar o valor que
recebeu.
"""

from __future__ import annotations

import logging
import secrets
import time

from django.conf import settings

logger = logging.getLogger("identidade.google_oauth")

# Chave sob a qual o `state`/nonce pendente fica guardado na sessão do
# navegador. Namespace com o nome do app de propósito: a sessão é
# compartilhada com o resto do site.
CHAVE_SESSAO_NONCE = "identidade:google:nonce"

# Evento de auditoria (um único valor, para facilitar o filtro no
# agregador de logs).
EVENTO = "identidade.google_oauth"

# Motivos de recusa — valores estáveis, sem PII e sem credencial.
MOTIVO_OK = "ok"
MOTIVO_NONCE_AUSENTE = "nonce_ausente"
MOTIVO_NONCE_INVALIDO = "nonce_invalido"
MOTIVO_NONCE_EXPIRADO = "nonce_expirado"
MOTIVO_NONCE_CLAIM_AUSENTE = "nonce_claim_ausente"
MOTIVO_NONCE_CLAIM_DIVERGENTE = "nonce_claim_divergente"
MOTIVO_CLIENT_ID_NAO_CONFIGURADO = "client_id_nao_configurado"
MOTIVO_TOKEN_INVALIDO = "token_invalido"
MOTIVO_EMAIL_NAO_VERIFICADO = "email_nao_verificado_no_provedor"
MOTIVO_CONTA_LOCAL_NAO_VERIFICADA = "conta_local_sem_email_verificado"
MOTIVO_CONTA_INATIVA = "conta_inativa"
MOTIVO_SEM_ACEITE = "sem_aceite_de_termos"


# ---------------------------------------------------------------------------
# Configuração do provedor
# ---------------------------------------------------------------------------

def client_id_configurado() -> bool:
    """
    Diz se `GOOGLE_OAUTH_CLIENT_ID` chegou a ser configurado neste ambiente.

    Existe porque o allauth usa o `client_id` como **audience** na
    verificação do `id_token`. Sem ele, o `aud` de qualquer token real
    não bate e o PyJWT rejeita com `InvalidAudienceError`, que o allauth
    converte em "token inválido" — exatamente a mesma resposta de um
    token de fato inválido. Ou seja: um ambiente que esqueceu a
    variável falha de forma total e **indistinguível** de um ataque,
    que é a pior forma de quebrar o critério de aceite "OAuth funciona
    em DEV/HOMOLOG/PROD". A view usa isto para responder 503 (serviço
    não configurado) em vez de 400 (credencial recusada).
    """
    provedores = getattr(settings, "SOCIALACCOUNT_PROVIDERS", None) or {}
    app = (provedores.get("google") or {}).get("APP") or {}
    return bool((app.get("client_id") or "").strip())


# ---------------------------------------------------------------------------
# `state`/`nonce` — o anti-CSRF e o anti-replay deste fluxo
# ---------------------------------------------------------------------------

def max_age_seconds() -> int:
    return int(getattr(settings, "GOOGLE_OAUTH_NONCE_MAX_AGE_SECONDS", 600))


def emitir_nonce(request) -> str:
    """
    Emite um `state`/`nonce` para o login Google começar e o amarra à
    sessão deste navegador.

    - **não previsível**: `secrets.token_urlsafe(32)` = 256 bits de
      entropia do `os.urandom`; não deriva de horário, IP, id de sessão
      nem de contador.
    - **atrelado à sessão**: guardado em `request.session`. Um cliente
      HTTP diferente (outro navegador, outra máquina) não tem a chave.
    - **de uso único**: `motivo_recusa_nonce` faz `pop`, então a segunda
      tentativa com o mesmo valor sempre falha, mesmo depois de uma
      tentativa que já havia falhado por outro motivo.

    Uma emissão substitui a anterior e o nonce é gasto mesmo numa
    tentativa errada. Consequência aceita e conhecida: duas abas do botão
    de login não produzem dois nonces válidos ao mesmo tempo — a segunda
    aba invalida a primeira, e o front que quiser relogar chama
    `/iniciar/` de novo. A alternativa (guardar uma lista de nonces
    pendentes) seria mais amigável e igualmente segura, e não foi feita
    porque aumenta a superfície de um gate de segurança em troca de um
    ganho de conveniência que o usuário nem percebe.
    """
    nonce = secrets.token_urlsafe(32)
    request.session[CHAVE_SESSAO_NONCE] = {
        "valor": nonce,
        "criado_em": time.time(),
    }
    # `request.session` pode vir de um backend de cookie assinado, onde
    # a gravação não é detectada por atribuição em dict aninhado.
    request.session.modified = True
    return nonce


def motivo_recusa_nonce(request, nonce) -> str:
    """
    Consome o nonce pendente desta sessão e devolve o motivo da recusa
    (`MOTIVO_OK` quando o nonce casou).

    Preferi um único ponto de consumo em vez de dois ("valida" e "depois
    explica por quê falhou"): dois caminhos de consumo num gate de
    segurança é a forma mais fácil de alguém chamar o errado depois. O
    retorno é o motivo, e a view decide a resposta a partir dele.

    O `pop` acontece **antes** de validar: uma tentativa malsucedida
    invalida o nonce, de modo que não existe janela para tentar adivinhar o
    valor um a um (com 256 bits não haveria mesmo, mas a propriedade
    "não há segunda tentativa" é a que importa). `secrets.compare_digest`
    evita ainda que o tempo de resposta revele quantos caracteres já
    casaram.

    As guardas de `isinstance` não são decorativas: a sessão é um dado
    serializado do lado do cliente (em alguns deploys, cookie assinado).
    Um valor corrompido ou forjado ali precisa cair em "inválido", nunca
    em exceção.
    """
    pendente = request.session.pop(CHAVE_SESSAO_NONCE, None)
    request.session.modified = True

    if pendente is None:
        return MOTIVO_NONCE_AUSENTE
    if not isinstance(pendente, dict):
        return MOTIVO_NONCE_INVALIDO
    esperado = pendente.get("valor")
    criado_em = pendente.get("criado_em")
    if not isinstance(esperado, str) or not esperado:
        return MOTIVO_NONCE_INVALIDO
    if not isinstance(criado_em, (int, float)):
        return MOTIVO_NONCE_INVALIDO
    if (time.time() - criado_em) > max_age_seconds():
        return MOTIVO_NONCE_EXPIRADO
    if not isinstance(nonce, str) or not nonce:
        return MOTIVO_NONCE_INVALIDO
    if not secrets.compare_digest(esperado, nonce):
        return MOTIVO_NONCE_INVALIDO
    return MOTIVO_OK


def claim_nonce_do_id_token(sociallogin) -> str | None:
    """
    Lê o claim `nonce` de dentro do `id_token` **já verificado**.

    O `extra_data` do `SocialAccount` é preenchido pelo allauth com o
    payload decodificado por `jwtkit.verify_and_decode`, que valida
    assinatura/iss/aud/exp. Ler o claim daqui é, portanto, ler uma
    asserção assinada pelo Google — e não o corpo do POST, que um site
    terceiro comeria sem dificuldade.
    """
    account = getattr(sociallogin, "account", None)
    extra_data = getattr(account, "extra_data", None)
    if not isinstance(extra_data, dict):
        return None
    claim = extra_data.get("nonce")
    if isinstance(claim, str) and claim:
        return claim
    return None


def nonce_do_id_token_confere(sociallogin, esperado: str) -> str:
    """
    Confere o `nonce` assinado contra o `state` que esta sessão emitiu.
    Devolve um motivo de `MOTIVO_OK` ou a razão da recusa.
    """
    claim = claim_nonce_do_id_token(sociallogin)
    if claim is None:
        return MOTIVO_NONCE_CLAIM_AUSENTE
    if not secrets.compare_digest(esperado, claim):
        return MOTIVO_NONCE_CLAIM_DIVERGENTE
    return MOTIVO_OK


# ---------------------------------------------------------------------------
# `email_verified` — identidade só por e-mail que o provedor verificou
# ---------------------------------------------------------------------------

def email_do_provider_verificado(sociallogin) -> bool:
    """
    O provedor afirmou que verificou a titularidade da caixa postal?

    O allauth marca `EmailAddress.verified` a partir do claim
    `email_verified` (ou `verified_email`) do `id_token` — ver
    `GoogleProvider.extract_email_addresses`. Não confiamos no campo
    `sociallogin.user.email`: ele vem do mesmo payload, mas o que
    interessa é o bit de verificação.
    """
    for endereco in getattr(sociallogin, "email_addresses", None) or []:
        if getattr(endereco, "verified", False):
            return True
    return False


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------

def auditar_login_google(
    *,
    desfecho: str,
    motivo: str,
    usuario_id=None,
    conta_nova: bool | None = None,
    erro_tipo: str | None = None,
) -> None:
    """
    Registra o desfecho de um login Google em `identidade.google_oauth`.

    Campos emitted: **fixos**. Nenhum parâmetro opcional livre, e
    nenhum deles pode carregar a credencial — o `id_token` simplesmente
    não tem por onde entrar nesta função. O e-mail também não: o
    suficiente para correlacionar é o id do usuário quando ele já
    existe, e o resto vira "mês que um modal de suporte".

    `erro_tipo` é o nome da **classe** da exceção, nunca a exceção nem o
    traceback: num caminho que recebe a credencial, a forma mais barata
    de nunca vazar o `id_token` em log é não logar nada que dependa do
    valor que a biblioteca recebeu.

    Sucesso vai para `info`, falha para `warning`, para que um dashboard
    de login social funcione com um `WHERE level >= warning`.
    """
    nivel = logging.INFO if desfecho == "sucesso" else logging.WARNING
    logger.log(
        nivel,
        EVENTO,
        extra={
            "oauth_event": EVENTO,
            "oauth_desfecho": desfecho,
            "oauth_motivo": motivo,
            "oauth_usuario_id": usuario_id,
            "oauth_conta_nova": conta_nova,
            "oauth_erro_tipo": erro_tipo,
        },
    )
