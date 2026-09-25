"""Consentimento assinado de analytics de produto + allowlist do payload.

Este módulo é a barreira de privacidade do `POST /api/metricas/eventos/`. Ele
existe porque a configuração de consentimento existia (`ANALYTICS_REQUIRE_CONSENT_TOKEN`,
`ANALYTICS_CONSENT_SIGNING_KEY`, `ANALYTICS_CONSENT_TTL_SECONDS`) sem NADA que a
aplicasse: o endpoint persistia o evento sem conferir token nenhum, ou seja,
o controle era decorativo (fail-open). Aqui a validação é real e fail-closed.

O que a assinatura PROVA — e o que não prova
--------------------------------------------
Prova que o payload foi **emitido por este backend** (que é o único detentor da
chave), que ele é da categoria correta, que ainda não expirou e que pertence a
um sujeito (sessão anônima) específico. Não prova que um humano leu os termos:
o gesto de consentimento é do cliente (`frontend/lib/cookie-consent.ts`) e é
inevitavelmente do lado do navegador. A assinatura não é um "botão de aceitar"
— é o que permite **revogar** (rotacionando a chave, todos os tokens pendentes
deixam de validar) e **atribuir** cada evento a um consentimento emitido, em vez
de aceitar qualquer string enviada por um terceiro.

Formato do token (o contrato que o frontend consome)
---------------------------------------------------
::

    v1.<payload_base64url>.<assinatura_base64url>

* ``v1`` — versão do envelope E das claims (rotacionável sem ambigüedad).
* ``payload_base64url`` — JSON canônico, UTF-8, **sem padding**, das claims
  ordenadas alfabeticamente e sem espaços::

      {"categoria":"analytics","exp":1758086400,"iat":1758000000,"sub":"s1-abc","v":1}

* ``assinatura_base64url`` — ``HMAC-SHA256(chave, "v1." + payload_base64url)``,
  também sem padding.

Claims obrigatórias: ``v`` (int = 1), ``categoria`` (str), ``iat`` (int, epoch
s), ``exp`` (int, epoch s), ``sub`` (str, sujeito pseudônimo de 6 a 64 chars em
``[A-Za-z0-9._-]``).

Verificações, todas fail-closed (qualquer uma reprova o evento):

1. envelope com 3 partes, tamanho limitado, base64url canônico;
2. assinatura HMAC válida em **tempo constante** (``hmac.compare_digest``),
   contra a chave ativa e contra as chaves anteriores declaradas (rotação);
3. claims com os tipos/formatos exatos acima (sem tipo frouxo, sem float, sem
   claim a mais, sem claim a menos);
4. ``categoria == "analytics"`` — um token de outra categoria é rejeitado;
5. ``exp > agora`` e ``exp - iat <= ANALYTICS_CONSENT_TTL_SECONDS`` — o cliente
   não pode pedir uma validade maior que a permitida, mesmo com token válido;
6. ``iat <= agora + CLOCK_SKEW_SECONDS`` — token emitido "no futuro" (relógio
   adiantado ou forjado) é rejeitado;
7. ``sub`` igual ao `sessao` do evento — o token não pode ser reaproveitado em
   outra sessão.

Nenhuma dessas respostas distingue "quem é o visitante": o endpoint devolve um
código estável e curto (`consent_<motivo>`) e nada mais, o suficiente para o
cliente renovar o token, e o motivo detalhado fica no log técnico + métrica.

Allowlist de payload
--------------------
O mesmo endpoint recebe tráfego anônimo e irrestrito, então o payload também é
uma superfície: só os campos de `CAMPOS_ACEITOS` chegam ao modelo, com tipo e
tamanho normalizados; `extra`/`filtros` passam pelo redactor de
`config.observability` (chave sensível ou valor com e-mail/JWT/Bearer vira
marcador, nunca o valor); `path` perde query string/fragment; e payload
excessivamente grande é recusado antes de tocar o banco.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings

from config.metrics import METRICS
from config.observability import redact_payload, redact_text, safe_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Contrato do token
# --------------------------------------------------------------------------

VERSAO_TOKEN = "v1"
VERSAO_CLAIMS = 1
CATEGORIA_ANALYTICS = "analytics"
CATEGORIAS_VALIDAS = {CATEGORIA_ANALYTICS}

# Tolerância de relógio entre o backend e o navegador. Existe para não
# reprovar o token do visitante cujo relógio está alguns segundos adiantado
# (NTP do celular, fuso, sleep do notebook) — mas é pequena de propósito: um
# `iat` muito no futuro é sinal de token forjado, não de dessincronização.
CLOCK_SKEW_SECONDS = 60

# Teto do token no transporte. Um token válido é ~200 bytes; 2048 absorve
# subjects longos sem transformar o endpoint num coletor de lixo.
MAX_TOKEN_BYTES = 2_048
# Teto do payload do evento (soma dos valores, sem materializar o JSON).
MAX_PAYLOAD_BYTES = 4_096
# Teto do `extra`/`filtros` já redigido.
MAX_EXTRA_BYTES = 512
MAX_EXTRA_CHAVES = 20

MIN_SUB_LEN = 6
MAX_SUB_LEN = 64
SUB_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SUB_LIMPO_RE = re.compile(r"[^A-Za-z0-9._-]")

# Motivos de recusa. Vocabulário FECHADO e de baixa cardinalidade: é ele que
# vira rótulo de métrica, então um motivo por exceção criaria série nova a
# cada erro diferente.
MOTIVO_AUSENTE = "ausente"
MOTIVO_MALFORMADO = "malformado"
MOTIVO_ASSINATURA = "assinatura_invalida"
MOTIVO_EXPIRADO = "expirado"
MOTIVO_CATEGORIA = "categoria_invalida"
MOTIVO_SUJEITO = "sujeito_invalido"
MOTIVO_TTL = "ttl_invalido"
MOTIVO_EMISSAO = "emissao_invalida"
MOTIVO_SEM_CHAVE = "sem_chave"
MOTIVO_TOKEN_GRANDE = "token_grande"
MOTIVOS_CONSENTIMENTO = frozenset(
    {
        MOTIVO_AUSENTE,
        MOTIVO_MALFORMADO,
        MOTIVO_ASSINATURA,
        MOTIVO_EXPIRADO,
        MOTIVO_CATEGORIA,
        MOTIVO_SUJEITO,
        MOTIVO_TTL,
        MOTIVO_EMISSAO,
        MOTIVO_SEM_CHAVE,
        MOTIVO_TOKEN_GRANDE,
    }
)
# Motivos de recusa do PAYLOAD (independentes do consentimento).
MOTIVO_CAMPO_EXCEDENTE = "campo_excedente"
MOTIVO_PAYLOAD_GRANDE = "payload_grande"
MOTIVO_PAYLOAD_INVALIDO = "payload_invalido"
MOTIVO_TIPO_DESCONHECIDO = "tipo_desconhecido"

# Janela mínima entre dois avisos de "consentimento desativado por config".
# O contador é a verdade (um incremento por evento); o log é amostrado para
# não virar flood de um endpoint público.
AVISO_BYPASS_A_CADA_SEGUNDOS = 300
_bypass_lock = threading.Lock()
_ultimo_aviso_bypass = 0.0

_CLAIMS_OBRIGATORIAS = {"v", "categoria", "iat", "exp", "sub"}


class ConsentError(ValueError):
    """Token não pôde ser emitido. Não carrega o valor do token no log."""

    def __init__(self, motivo: str) -> None:
        super().__init__(motivo)
        self.motivo = motivo


@dataclass(frozen=True)
class Verificacao:
    """Resultado da verificação: um motivo curto ou o payload decodificado."""

    ok: bool
    motivo: str = ""
    claims: dict[str, Any] = field(default_factory=dict)

    @property
    def sub(self) -> str:
        return str(self.claims.get("sub") or "")


# --------------------------------------------------------------------------
# Chave
# --------------------------------------------------------------------------


def _chave_ativa() -> str:
    """Chave de assinatura ativa.

    `ANALYTICS_CONSENT_SIGNING_KEY` é a configuração de fato; quando vazia cai
    na `SECRET_KEY`, que fora de DEBUG o próprio `settings.py` já se recusa a
    deixar fraca. Nunca inventa uma chave padrão aqui: sem chave, o
    consentimento é reprovado (`sem_chave`) em vez de ser aceito sem prova.
    """

    explicita = str(getattr(settings, "ANALYTICS_CONSENT_SIGNING_KEY", "") or "").strip()
    if explicita:
        return explicita
    try:
        return str(getattr(settings, "SECRET_KEY", "") or "").strip()
    except Exception:  # noqa: BLE001 — o Django recusa `SECRET_KEY` vazio com
        # `ImproperlyConfigured`; aqui isso é só "não há chave", que o chamador
        # trata como recusa (`sem_chave`) e não como exceção inesperada.
        return ""


def _chaves_anteriores() -> list[str]:
    """Chaves anteriores, para a rotação não derrubar o que está no navegador.

    A rotação é: `ANALYTICS_CONSENT_SIGNING_KEY` = chave nova (assina) e
    `ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS` = chave antiga separada por
    vírgula (ainda valida). Depois de `ANALYTICS_CONSENT_TTL_SECONDS` sem
    emissão, a antiga sai da lista — nesse momento os tokens pendentes dela
    passam a ser recusados, que é exatamente o efeito desejado de uma revogação.
    """

    brutas = str(getattr(settings, "ANALYTICS_CONSENT_SIGNING_KEY_PREVIOUS", "") or "")
    chaves = []
    for item in brutas.split(","):
        limpa = item.strip()
        if limpa:
            chaves.append(limpa)
    return chaves


def _ttl_configurado() -> int:
    try:
        return max(60, int(getattr(settings, "ANALYTICS_CONSENT_TTL_SECONDS", 86_400)))
    except (TypeError, ValueError):
        return 86_400


def consentimento_requerido() -> bool:
    """Se o endpoint exige token de consentimento.

    Default `True` (fail-closed). Desligar é decisão de uso local
    (`ANALYTICS_REQUIRE_CONSENT_TOKEN=false`) e nunca é silenciosa: quem desliga
    paga com contador e aviso técnico (ver `registrar_bypass`).
    """

    return bool(getattr(settings, "ANALYTICS_REQUIRE_CONSENT_TOKEN", True))


# --------------------------------------------------------------------------
# Codificação
# --------------------------------------------------------------------------


def _b64url(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).decode("ascii").rstrip("=")


def _b64url_decodigo(texto: str) -> bytes:
    """Decodifica base64url exigindo a forma canônica.

    Aceitar variantes (`=` de padding, `+`/`/` de base64 normal, mistura dos
    dois) criaria mais de uma representação do MESMO token: o que é bom para
    canonicalizar, é ruim para uma fronteira de verificação. Exigimos a forma
    exata que `gerar_token_consent` produz.
    """

    if not texto or len(texto) > MAX_TOKEN_BYTES:
        raise ValueError("base64url fora do formato")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", texto):
        raise ValueError("base64url fora do formato")
    padding = "=" * (-len(texto) % 4)
    try:
        return base64.urlsafe_b64decode(texto + padding)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("base64url inválido") from exc


def _payload_canonico(claims: dict[str, Any]) -> bytes:
    """Serialização canônica: ordenação de chaves, sem espaços, UTF-8.

    A canonicalização existe para que a mesma claim-set sempre produza o mesmo
    texto (e portanto a mesma assinatura) — sem ela, `json.dumps` aceitaria
    ordens diferentes de chaves e o par emitir/verificar dependeria da ordem
    de inserção.
    """

    return json.dumps(
        claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _assinatura(chave: str, mensagem: bytes) -> bytes:
    return hmac.new(chave.encode("utf-8"), mensagem, hashlib.sha256).digest()


# --------------------------------------------------------------------------
# Emissão (servidor)
# --------------------------------------------------------------------------


def normalizar_sub(valor: object) -> str:
    """Normaliza um sujeito pseudônimo para o alfabeto aceito no token."""

    limpo = SUB_LIMPO_RE.sub("", "" if valor is None else str(valor))
    return limpo[:MAX_SUB_LEN]


def sub_valido(valor: object) -> bool:
    texto = "" if valor is None else str(valor)
    return (
        MIN_SUB_LEN <= len(texto) <= MAX_SUB_LEN
        and bool(SUB_RE.fullmatch(texto))
    )


def gerar_token_consent(
    *,
    categoria: str = CATEGORIA_ANALYTICS,
    sub: object = "",
    ttl_seconds: int | None = None,
    agora: int | None = None,
) -> str:
    """Emite um token de consentimento. Somente no backend.

    `ttl_seconds` existe para operação/teste; o valor efetivo é limitado por
    `ANALYTICS_CONSENT_TTL_SECONDS`, então nem o chamador mais privilegiado
    emite um token de longa duração sem mudar a configuração.
    """

    token, _claims = emitir_consentimento(
        categoria=categoria, sub=sub, ttl_seconds=ttl_seconds, agora=agora
    )
    return token


def emitir_consentimento(
    *,
    categoria: str = CATEGORIA_ANALYTICS,
    sub: object = "",
    ttl_seconds: int | None = None,
    agora: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Emite o token e devolve também as claims, para o emissor ecoá-las.

    Evitar que o chamante decodifique o payload por conta própria é
    proposital: um "decodifique sem verificar" no meio do caminho é o tipo de
    atalho que um dia vira um bypass de assinatura.
    """

    chave = _chave_ativa()
    if not chave:
        raise ConsentError(MOTIVO_SEM_CHAVE)
    if categoria not in CATEGORIAS_VALIDAS:
        raise ConsentError(MOTIVO_CATEGORIA)
    if not sub_valido(sub):
        raise ConsentError(MOTIVO_SUJEITO)
    emitido = int(agora if agora is not None else time.time())
    ttl = int(ttl_seconds) if ttl_seconds is not None else _ttl_configurado()
    if ttl <= 0:
        ttl = _ttl_configurado()
    # O teto da configuração vence o pedido: é o que impede um token válido
    # com validade de anos (que continuaria funcionando depois de revogada a
    # configuração de retenção).
    ttl = min(ttl, _ttl_configurado())
    claims = {
        "v": VERSAO_CLAIMS,
        "categoria": categoria,
        "iat": emitido,
        "exp": emitido + ttl,
        "sub": str(sub),
    }
    payload = _b64url(_payload_canonico(claims))
    mensagem = f"{VERSAO_TOKEN}.{payload}".encode("ascii")
    token = f"{VERSAO_TOKEN}.{payload}.{_b64url(_assinatura(chave, mensagem))}"
    return token, claims



# --------------------------------------------------------------------------
# Verificação
# --------------------------------------------------------------------------


def _decodificar_envelope(token: object) -> tuple[bytes, bytes, bytes]:
    """Valida o envelope e devolve `(bytes_assinados, payload, assinatura)`.

    Devolver os bytes já montados (em vez de a string bruta) é o que garante
    que a mensagem comparada em tempo constante é exatamente a que foi gerada,
    sem depender de um `split` posterior sobre texto que o cliente controla.
    """

    bruto = "" if token is None else str(token).strip()
    if not bruto:
        raise ValueError("vazio")
    if len(bruto) > MAX_TOKEN_BYTES:
        raise ValueError("longo")
    partes = bruto.split(".")
    if len(partes) != 3:
        raise ValueError("partes")
    versao, payload_b64, assinatura_b64 = partes
    if versao != VERSAO_TOKEN:
        raise ValueError("versão")
    payload = _b64url_decodigo(payload_b64)
    assinatura = _b64url_decodigo(assinatura_b64)
    if len(assinatura) != hashlib.sha256().digest_size:
        raise ValueError("assinatura")
    return f"{versao}.{payload_b64}".encode("ascii"), payload, assinatura


def _claims_confiaveis(payload: bytes) -> dict[str, Any]:
    try:
        claims = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("json") from exc
    # Conjunto exato de claims: claim a mais (um `email`, um `escopo`) ou a
    # menos é sinal de envelope fora do contrato, não de "ignorar o que vier".
    if not isinstance(claims, dict) or set(claims) != _CLAIMS_OBRIGATORIAS:
        raise ValueError("claims")
    if claims.get("v") != VERSAO_CLAIMS or isinstance(claims.get("v"), bool):
        raise ValueError("v")
    for claim in ("iat", "exp"):
        # `bool` é subclasse de `int` em Python e `float` não é epoch: sem esta
        # guarda, `iat: true` valeria como 1 e `exp: 1.0` atravessaria a
        # comparação de expiração.
        if isinstance(claims[claim], bool) or not isinstance(claims[claim], int):
            raise ValueError(claim)
    if not isinstance(claims.get("categoria"), str):
        raise ValueError("categoria")
    if not sub_valido(claims.get("sub")):
        raise ValueError("sub")
    return claims


def verificar_consentimento(
    token: object,
    *,
    sub_esperado: object = None,
    agora: int | None = None,
) -> Verificacao:
    """Verifica o token e devolve o motivo da recusa, se houver.

    `sub_esperado` é o sujeito do evento (`sessao`): quando informado, o token
    precisa ser DAQUELA sessão. Sem essa amarra, o token valeria como um bem
    público — copiável de um evento para outro, de um visitante para outro.
    """

    bruto = "" if token is None else str(token).strip()
    if not bruto:
        return Verificacao(False, MOTIVO_AUSENTE)
    if len(bruto) > MAX_TOKEN_BYTES:
        return Verificacao(False, MOTIVO_TOKEN_GRANDE)
    try:
        mensagem, payload, assinatura = _decodificar_envelope(bruto)
    except ValueError:
        return Verificacao(False, MOTIVO_MALFORMADO)

    if not _chave_ativa():
        return Verificacao(False, MOTIVO_SEM_CHAVE)

    # `compare_digest` só é constante (e seguro) para dois `bytes`. Percorrer as
    # chaves candidatas inteiro é proposital: um atacante não consegue medir
    # "acertou na 1ª chave" para decidir qual das suas tentativas parar de fazer.
    valido = any(
        hmac.compare_digest(_assinatura(candidata, mensagem), assinatura)
        for candidata in [_chave_ativa(), *_chaves_anteriores()]
    )
    if not valido:
        return Verificacao(False, MOTIVO_ASSINATURA)

    try:
        claims = _claims_confiaveis(payload)
    except ValueError:
        return Verificacao(False, MOTIVO_MALFORMADO)

    if claims["categoria"] not in CATEGORIAS_VALIDAS:
        return Verificacao(False, MOTIVO_CATEGORIA)

    momento = int(agora if agora is not None else time.time())
    if claims["iat"] > momento + CLOCK_SKEW_SECONDS:
        return Verificacao(False, MOTIVO_EMISSAO)
    if claims["exp"] <= momento:
        return Verificacao(False, MOTIVO_EXPIRADO)
    # Validade maior que a configurada significa token emitido sob outra
    # política de retenção (ou forjado): a configuração manda.
    if claims["exp"] - claims["iat"] > _ttl_configurado():
        return Verificacao(False, MOTIVO_TTL)
    if sub_esperado is not None and not sub_valido(sub_esperado):
        return Verificacao(False, MOTIVO_SUJEITO)
    if sub_esperado is not None and claims["sub"] != str(sub_esperado):
        return Verificacao(False, MOTIVO_SUJEITO)
    return Verificacao(True, "", claims)


# --------------------------------------------------------------------------
# Sinal técnico das recusas
# --------------------------------------------------------------------------


def registrar_recusa(motivo: str, *, tipo: object = "", origem: str = "evento") -> None:
    """Conta e registra o descarte, sem carregar o token nem dado do visitante.

    `origem="evento"` é a ingestão (o evento não persistido); `origem="token"` é
    o emissor recusando-se a entregar um token. O log técnico leva o motivo e o
    tipo do evento (texto redigido e limitado): é o que permite responder "por
    que perdi os eventos do meu portal?" sem transformar o log de aplicação em
    um log de conteúdo de visitante.
    """

    rotulo = str(motivo or "desconhecido")[:32]
    METRICS.inc("portal_analytics_consent_rejections_total", reason=rotulo, origin=origem[:16])
    if origem == "evento":
        METRICS.inc("portal_analytics_events_rejected_total", reason=rotulo)
        logger.info(
            "analytics: evento NÃO persistido (motivo=%s tipo=%s)",
            rotulo,
            redact_text(tipo, limit=40) or "-",
        )
    else:
        # Recusa na emissão é rara (erro de cliente ou de configuração): merece
        # WARNING, e o corpo do pedido também não entra no log.
        logger.warning("analytics: token de consentimento NÃO emitido (motivo=%s)", rotulo)


def registrar_bypass() -> None:
    """Deixa visível que a validação está desligada por configuração.

    Contador por evento (a verdade) + aviso em log no máximo a cada
    `AVISO_BYPASS_A_CADA_SEGUNDOS` (o log é amostrado de propósito: um
    endpoint público chamando isso por evento inundaria o Loki).
    """

    METRICS.inc("portal_analytics_consent_bypass_total")
    global _ultimo_aviso_bypass
    momento = time.monotonic()
    with _bypass_lock:
        if momento - _ultimo_aviso_bypass < AVISO_BYPASS_A_CADA_SEGUNDOS:
            return
        _ultimo_aviso_bypass = momento
    logger.warning(
        "analytics: ANALYTICS_REQUIRE_CONSENT_TOKEN está desligado — eventos de "
        "produto são persistidos SEM prova de consentimento (uso local)"
    )


# --------------------------------------------------------------------------
# Allowlist do payload
# --------------------------------------------------------------------------

# Campos aceitos no corpo do evento. Qualquer outro campo é DESCARTADO
# (não persistido, não repassado a `extra`) e contabilizado. `consent_token` é
# transporte do token (header ou corpo), nunca conteúdo de evento.
CAMPOS_ACEITOS = frozenset(
    {
        "tipo",
        "path",
        "sessao",
        "entry_tipo",
        "entry_id",
        "categoria",
        "autor_ref",
        "autor",
        "secao_home",
        "secao",
        "origem",
        "dispositivo",
        "pais",
        "estado",
        "cidade",
        "regiao",
        "tempo_permanencia_seg",
        "tempo_leitura_seg",
        "scroll_max_pct",
        "resultados",
        "termo",
        "query",
        "extra",
        "filtros",
    }
)
CAMPOS_TRANSPORTE = frozenset({"consent_token"})

# Limites por campo, espelhando `max_length` do modelo: normalizar aqui evita
# truncamento silencioso pelo banco e mantém um valor de 8 KB fora do campo.
LIMITES_TEXTO = {
    "path": 500,
    "categoria": 100,
    "autor_ref": 200,
    "secao_home": 60,
    "dispositivo": 20,
    "origem": 20,
    "pais": 100,
    "estado": 100,
    "cidade": 150,
    "regiao": 150,
    "termo": 300,
}
LIMITES_INTEIRO = {
    "entry_id": (0, 2_147_483_647),
    "tempo_permanencia_seg": (0, 86_400),
    "tempo_leitura_seg": (0, 86_400),
    "scroll_max_pct": (0, 100),
    "resultados": (0, 1_000_000),
}

# Quantos campos do corpo o sanitizador inspeciona antes de desistir. Um corpo
# com 10 mil chaves é abuso, não evento: verificar tudo custaria CPU de graça
# para quem não vai persistir nada.
MAX_CAMPOS_INSPECIONADOS = 200


def _texto(valor: object, limite: int) -> str:
    """Texto livre normalizado: sem caractere de controle e sem dado pessoal.

    `redact_text` já é a barreira do projeto para log/Sentry (e-mail, JWT,
    Bearer, `token=...`, query string) — reaproveitar em vez de duplicar é o
    que garante que o mesmo dado não vaze por dois caminhos diferentes.
    """

    if valor is None or isinstance(valor, (dict, list, tuple, set)):
        return ""
    return redact_text(valor, limit=limite).strip()


def _inteiro(valor: object, minimo: int, maximo: int) -> int:
    if isinstance(valor, bool) or valor is None:
        return 0
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return 0
    return max(minimo, min(maximo, numero))


def _dicionario_limitado(valor: object) -> dict[str, Any]:
    """`extra`/`filtros`: dicionário, com teto de chaves, já redigido.

    O redactor do projeto trata chave sensível e valor com formato de e-mail/
    JWT/Bearer. O que sobra pode ainda ser um objeto aninhado arbitrário, daí
    o teto de chaves e de tamanho: o JSONField do modelo não aceita payload
    ilimitado e um `extra` de 1 MB por evento é negação de serviço.
    """

    if not isinstance(valor, dict):
        return {}
    seguro = redact_payload({str(k): v for k, v in list(valor.items())[:MAX_EXTRA_CHAVES]})
    if not isinstance(seguro, dict):
        return {}
    if len(seguro) > MAX_EXTRA_CHAVES:
        seguro = dict(list(seguro.items())[:MAX_EXTRA_CHAVES])
    try:
        tamanho = len(json.dumps(seguro, default=str).encode("utf-8"))
    except (TypeError, ValueError):
        return {}
    if tamanho > MAX_EXTRA_BYTES:
        return {}
    return seguro


def _tamanho_aproximado(dados: dict) -> int:
    """Soma o tamanho do payload sem materializar JSON do corpo inteiro."""

    total = 0
    for indice, (chave, valor) in enumerate(dados.items()):
        if indice >= MAX_CAMPOS_INSPECIONADOS:
            total = MAX_PAYLOAD_BYTES + 1
            break
        total += len(str(chave))
        if isinstance(valor, (dict, list, tuple, set)):
            total += MAX_EXTRA_BYTES
        else:
            total += len(str(valor))
        if total > MAX_PAYLOAD_BYTES:
            break
    return total


@dataclass(frozen=True)
class Sanitizacao:
    """Payload normalizado + o que foi descartado."""

    dados: dict[str, Any]
    campos_excedentes: tuple[str, ...] = ()
    motivo: str = ""
    ok: bool = True


def sanear_payload(bruto: object) -> Sanitizacao:
    """Aplica a allowlist: só o que está na lista chega ao modelo.

    Não persiste nada — a sanitização é pura e roda ANTES da checagem de
    consentimento, para que o sujeito esperado (`sessao`) já esteja normalizado
    quando o token é verificado.
    """

    if not isinstance(bruto, dict):
        return Sanitizacao({}, motivo=MOTIVO_PAYLOAD_INVALIDO, ok=False)
    if len(bruto) > MAX_CAMPOS_INSPECIONADOS:
        return Sanitizacao({}, motivo=MOTIVO_PAYLOAD_GRANDE, ok=False)
    if _tamanho_aproximado(bruto) > MAX_PAYLOAD_BYTES:
        return Sanitizacao({}, motivo=MOTIVO_PAYLOAD_GRANDE, ok=False)

    excedentes = tuple(
        sorted(str(c)[:40] for c in bruto if str(c) not in CAMPOS_ACEITOS | CAMPOS_TRANSPORTE)
    )
    dados: dict[str, Any] = {}
    for campo in CAMPOS_ACEITOS:
        if campo not in bruto:
            continue
        valor = bruto[campo]
        if campo == "sessao":
            dados[campo] = normalizar_sub(valor)
        elif campo == "path":
            dados[campo] = safe_path(valor, limit=500)
        elif campo in LIMITES_TEXTO:
            dados[campo] = _texto(valor, LIMITES_TEXTO[campo])
        elif campo in LIMITES_INTEIRO:
            minimo, maximo = LIMITES_INTEIRO[campo]
            dados[campo] = _inteiro(valor, minimo, maximo)
        elif campo in {"extra", "filtros"}:
            dados[campo] = _dicionario_limitado(valor)
        elif campo == "entry_tipo":
            candidato = _texto(valor, 10)
            dados[campo] = candidato if candidato in {"item", "cluster"} else "item"
        else:  # `tipo`/`autor` — texto livre com teto do próprio campo
            dados[campo] = _texto(valor, 40 if campo == "tipo" else LIMITES_TEXTO["autor_ref"])
    if excedentes:
        METRICS.inc(
            "portal_analytics_payload_fields_dropped_total",
            count=min(len(excedentes), 10),
        )
    return Sanitizacao(dados, excedentes)


__all__ = [
    "AVISO_BYPASS_A_CADA_SEGUNDOS",
    "CAMPOS_ACEITOS",
    "CAMPOS_TRANSPORTE",
    "CATEGORIA_ANALYTICS",
    "CLOCK_SKEW_SECONDS",
    "MAX_EXTRA_BYTES",
    "MAX_EXTRA_CHAVES",
    "MAX_PAYLOAD_BYTES",
    "MAX_TOKEN_BYTES",
    "MOTIVOS_CONSENTIMENTO",
    "MOTIVO_ASSINATURA",
    "MOTIVO_AUSENTE",
    "MOTIVO_CAMPO_EXCEDENTE",
    "MOTIVO_CATEGORIA",
    "MOTIVO_EMISSAO",
    "MOTIVO_EXPIRADO",
    "MOTIVO_MALFORMADO",
    "MOTIVO_PAYLOAD_GRANDE",
    "MOTIVO_PAYLOAD_INVALIDO",
    "MOTIVO_SEM_CHAVE",
    "MOTIVO_SUJEITO",
    "MOTIVO_TIPO_DESCONHECIDO",
    "MOTIVO_TOKEN_GRANDE",
    "MOTIVO_TTL",
    "VERSAO_TOKEN",
    "ConsentError",
    "Sanitizacao",
    "Verificacao",
    "consentimento_requerido",
    "emitir_consentimento",
    "gerar_token_consent",
    "normalizar_sub",
    "registrar_bypass",
    "registrar_recusa",
    "sanear_payload",
    "sub_valido",
    "verificar_consentimento",
]
