"""Proxy com cache para ViaCEP/IBGE (FRENTE 5 — endereços inteligentes).

Por que existe um proxy em vez de chamar ViaCEP/IBGE direto do navegador
(como `frontend/lib/cep.ts` e `frontend/lib/ibge.ts` fazem hoje)?

- ViaCEP/IBGE são públicos e não exigem credencial — o proxy NÃO guarda
  segredo nenhum. Ele existe para: (1) cache compartilhado entre todos os
  visitantes (o cache do frontend é por navegador); (2) rate-limit no
  servidor (`EnderecosAnonThrottle`), evitando rajadas de um único cliente;
  (3) ponto único para trocar de provedor (ex.: Correios com credencial)
  sem reimplantar o frontend — a credencial, quando existir, fica só aqui.
- O frontend continua funcionando SEM o backend (fallback direto), então
  este proxy é progressivo, não obrigatório — ver `frontend/lib/cep.ts`.
"""

from __future__ import annotations

import hashlib
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class EnderecoInvalidoError(ValueError):
    """CEP/endereço malformado (400)."""


class CepNaoEncontradoError(LookupError):
    """CEP inexistente ou sem resultados (404)."""


class ServicoEnderecoIndisponivelError(RuntimeError):
    """Upstream fora do ar, timeout ou resposta inválida (502)."""


def normalizar_cep(cep: str) -> str:
    return re.sub(r"\D", "", cep or "")[:8]


def validar_cep(n: str) -> None:
    if len(n) != 8 or not n.isdigit():
        raise EnderecoInvalidoError("CEP inválido. Informe 8 dígitos (ex: 01310-100).")


def _base_viacep() -> str:
    return getattr(settings, "ENDERECOS_VIACEP_BASE_URL", "https://viacep.com.br").rstrip("/")


def _base_ibge() -> str:
    return getattr(
        settings, "ENDERECOS_IBGE_BASE_URL", "https://servicodados.ibge.gov.br/api/v1"
    ).rstrip("/")


def _timeout() -> int:
    return int(getattr(settings, "ENDERECOS_UPSTREAM_TIMEOUT_SEGUNDOS", 8))


def _get_json(url: str):
    try:
        resposta = requests.get(url, timeout=_timeout())
    except requests.RequestException as exc:
        logger.warning("enderecos upstream inalcançável: %s (%s)", url, exc)
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível consultar o serviço de endereços. Tente novamente em instantes."
        ) from exc
    if resposta.status_code >= 400:
        logger.warning("enderecos upstream HTTP %s: %s", resposta.status_code, url)
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível consultar o serviço de endereços. Tente novamente em instantes."
        )
    try:
        return resposta.json()
    except ValueError as exc:
        raise ServicoEnderecoIndisponivelError("Resposta inválida do serviço de endereços.") from exc


def consultar_cep(cep: str) -> dict:
    """Consulta um CEP (8 dígitos). Resultado é o JSON do ViaCEP, cacheado 24h."""
    n = normalizar_cep(cep)
    validar_cep(n)
    chave = f"enderecos:cep:{n}"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    dados = _get_json(f"{_base_viacep()}/ws/{n}/json/")
    if isinstance(dados, dict) and dados.get("erro"):
        raise CepNaoEncontradoError("CEP não encontrado. Verifique o número digitado.")
    if not isinstance(dados, dict) or not dados.get("cep"):
        raise CepNaoEncontradoError("CEP não encontrado. Verifique o número digitado.")
    cache.set(chave, dados, timeout=int(getattr(settings, "ENDERECOS_CACHE_CEP_SEGUNDOS", 86400)))
    return dados


def buscar_por_endereco(uf: str, cidade: str, logradouro: str) -> list:
    """Busca CEPS por UF/cidade/logradouro (mín. 3 letras cada). Cache 24h."""
    u = (uf or "").strip().upper()
    c = (cidade or "").strip()
    l = (logradouro or "").strip()
    if not re.fullmatch(r"[A-Z]{2}", u):
        raise EnderecoInvalidoError("UF inválida. Use a sigla com 2 letras (ex: SP).")
    if len(c) < 3:
        raise EnderecoInvalidoError("Informe a cidade com ao menos 3 letras.")
    if len(l) < 3:
        raise EnderecoInvalidoError("Informe o logradouro com ao menos 3 letras.")
    chave = f"enderecos:busca:{u}:{hashlib.md5(f'{c.lower()}|{l.lower()}'.encode('utf-8')).hexdigest()}"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    from urllib.parse import quote

    dados = _get_json(
        f"{_base_viacep()}/ws/{quote(u)}/{quote(c)}/{quote(l)}/json/"
    )
    if not isinstance(dados, list) or len(dados) == 0:
        raise CepNaoEncontradoError("Nenhum endereço encontrado. Ajuste a busca.")
    cache.set(chave, dados, timeout=int(getattr(settings, "ENDERECOS_CACHE_CEP_SEGUNDOS", 86400)))
    return dados


def listar_estados() -> list:
    """Lista {sigla, nome} dos estados (IBGE). Cache 7 dias."""
    chave = "enderecos:ibge:estados"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    dados = _get_json(f"{_base_ibge()}/localidades/estados?orderBy=nome")
    if not isinstance(dados, list):
        raise ServicoEnderecoIndisponivelError("Resposta inválida do serviço de endereços.")
    lista = [{"sigla": e.get("sigla"), "nome": e.get("nome")} for e in dados if isinstance(e, dict)]
    cache.set(chave, lista, timeout=int(getattr(settings, "ENDERECOS_CACHE_IBGE_SEGUNDOS", 604800)))
    return lista


def listar_municipios(uf: str) -> list:
    """Lista nomes de municípios de uma UF (IBGE). Cache 7 dias."""
    u = (uf or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", u):
        raise EnderecoInvalidoError("UF inválida.")
    chave = f"enderecos:ibge:municipios:{u}"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    dados = _get_json(f"{_base_ibge()}/localidades/estados/{u}/municipios?orderBy=nome")
    if not isinstance(dados, list):
        raise ServicoEnderecoIndisponivelError("Resposta inválida do serviço de endereços.")
    lista = [m.get("nome") for m in dados if isinstance(m, dict) and m.get("nome")]
    cache.set(chave, lista, timeout=int(getattr(settings, "ENDERECOS_CACHE_IBGE_SEGUNDOS", 604800)))
    return lista


def _base_nominatim() -> str:
    return getattr(settings, "ENDERECOS_NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org").rstrip("/")


def reverter_coordenadas(lat: float, lon: float) -> dict:
    """Geocodificação reversa (lat/lon → cidade/UF): usada pelo botão
    "Compartilhar minha localização" (Perto de Você + Radar).

    Por que um proxy em vez de chamar o Nominatim direto do navegador?
    O Nominatim exige User-Agent identificável e limita por IP — no
    navegador ele responde 403/429 com frequência (foi a causa do
    "Não foi possível obter sua localização" em produção). Aqui o
    User-Agent é identificável, a resposta é cacheada 7 dias (coordenadas
    arredondadas a ~100m) e há rate-limit no servidor. O frontend mantém
    fallback direto caso o backend esteja fora (ver `lib/regiao.ts`).
    """
    try:
        la, lo = float(lat), float(lon)
    except (TypeError, ValueError):
        raise EnderecoInvalidoError("Coordenadas inválidas. Informe latitude e longitude numéricas.")
    if not (-90 <= la <= 90) or not (-180 <= lo <= 180):
        raise EnderecoInvalidoError("Coordenadas fora do intervalo válido.")
    chave = f"enderecos:reverso:{round(la, 3)}:{round(lo, 3)}"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    url = f"{_base_nominatim()}/reverse?format=json&lat={la}&lon={lo}&zoom=10&addressdetails=1"
    try:
        resposta = requests.get(
            url,
            timeout=_timeout(),
            headers={"User-Agent": "BRDPortalNoticias/1.0 (+https://portal-noticias.com.br)", "Accept": "application/json"},
        )
    except requests.RequestException as exc:
        logger.warning("enderecos reverso inalcançável: %s (%s)", url, exc)
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível identificar sua cidade agora. Tente de novo ou digite seu CEP."
        ) from exc
    if resposta.status_code >= 400:
        logger.warning("enderecos reverso HTTP %s", resposta.status_code)
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível identificar sua cidade agora. Tente de novo ou digite seu CEP."
        )
    try:
        dados = resposta.json()
    except ValueError as exc:
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível identificar sua cidade agora. Tente de novo ou digite seu CEP."
        ) from exc
    a = (dados or {}).get("address", {}) if isinstance(dados, dict) else {}
    if not isinstance(a, dict):
        a = {}
    cidade = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or ""
    estado = a.get("state_code") or a.get("state") or a.get("region") or ""
    if len(estado) > 2:
        estado = ""
    resultado = {
        "cidade": cidade,
        "estado": (estado or "").upper(),
        "pais": a.get("country") or "Brasil",
        "cep": a.get("postcode"),
        "bairro": a.get("suburb") or a.get("neighbourhood") or a.get("quarter"),
        "logradouro": a.get("road"),
        "lat": la,
        "lon": lo,
    }
    if not cidade and not estado:
        raise CepNaoEncontradoError(
            "Não foi possível identificar sua cidade. Digite seu CEP abaixo."
        )
    cache.set(chave, resultado, timeout=int(getattr(settings, "ENDERECOS_CACHE_IBGE_SEGUNDOS", 604800)))
    return resultado


def _base_ipapi() -> str:
    # Tier gratuito: HTTP (não HTTPS). Chamada só server-side, nunca do
    # navegador (evita mixed-content). 45 req/min por IP — o cache abaixo
    # (24h por IP) + throttle do endpoint mantêm o uso folgado.
    return getattr(settings, "ENDERECOS_IPAPI_BASE_URL", "http://ip-api.com").rstrip("/")


def localizar_por_ip(ip: str) -> dict:
    """Cidade/UF aproximada pela conexão (sem GPS, sem permissão).

    Fallback automático quando o navegador bloqueia a geolocalização: o
    frontend pergunta ao USUÁRIO (diálogo próprio) se aceita a região
    detectada — o sistema sempre pergunta, mesmo sem prompt nativo.
    Retorna {cidade, estado, pais} ou levanta CepNaoEncontradoError (vira
    404: frontend cai para o CEP manual).
    """
    ip_limpo = (ip or "").strip()
    if not ip_limpo or ip_limpo in ("127.0.0.1", "::1"):
        raise CepNaoEncontradoError(
            "Não foi possível detectar sua região pela conexão. Digite seu CEP abaixo."
        )
    chave = f"enderecos:ip:{ip_limpo}"
    cached = cache.get(chave)
    if cached is not None:
        return cached
    url = f"{_base_ipapi()}/json/{ip_limpo}?fields=status,city,region,regionName,country,countryCode,zip,query"
    try:
        resposta = requests.get(url, timeout=_timeout())
    except requests.RequestException as exc:
        logger.warning("enderecos ip-api inalcançável (%s)", exc)
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível detectar sua região agora. Digite seu CEP abaixo."
        ) from exc
    if resposta.status_code >= 400:
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível detectar sua região agora. Digite seu CEP abaixo."
        )
    try:
        dados = resposta.json()
    except ValueError as exc:
        raise ServicoEnderecoIndisponivelError(
            "Não foi possível detectar sua região agora. Digite seu CEP abaixo."
        ) from exc
    if not isinstance(dados, dict) or dados.get("status") != "success":
        raise CepNaoEncontradoError(
            "Não foi possível detectar sua região pela conexão. Digite seu CEP abaixo."
        )
    cidade = (dados.get("city") or "").strip()
    estado = (dados.get("region") or "").strip().upper()
    pais_nome = (dados.get("country") or "").strip()
    if not cidade and not estado:
        raise CepNaoEncontradoError(
            "Não foi possível detectar sua região pela conexão. Digite seu CEP abaixo."
        )
    resultado = {
        "cidade": cidade,
        "estado": estado if len(estado) == 2 else "",
        "pais": pais_nome or "Brasil",
        "cep": (dados.get("zip") or "").strip() or None,
        "fonte": "ip",
    }
    cache.set(chave, resultado, timeout=int(getattr(settings, "ENDERECOS_CACHE_CEP_SEGUNDOS", 86400)))
    return resultado
