"""Coordenadas de referência das UFs brasileiras + distância Haversine.

R-02 (run 20261013-1048-home-radar-central-ux): `NewsItem` não tem
latitude/longitude por notícia (não-objetivo explícito do contrato — ver
implementation-contract.md), só `estado`/`pais` (e `cidade`, que a
ingestão real nunca popula). Para ordenar o Radar por proximidade sem
fabricar coordenada de notícia, usamos a coordenada da CAPITAL de cada UF
como representante dessa UF — é geografia pública, documentada abaixo.

FONTE: coordenadas aproximadas (graus decimais, WGS84) das capitais dos 26
estados + Distrito Federal, tal como amplamente publicadas por fontes
cartográficas públicas (ex. IBGE, Wikipedia) — não fabricadas por esta
aplicação. Precisão de ~4 casas decimais é suficiente para "distância até a
UF", não para geolocalização fina.
"""

from __future__ import annotations

import math

# UF -> (latitude, longitude) da capital.
UF_COORDENADAS: dict[str, tuple[float, float]] = {
    "AC": (-9.9750, -67.8243),   # Rio Branco
    "AL": (-9.6498, -35.7089),   # Maceió
    "AP": (0.0349, -51.0694),    # Macapá
    "AM": (-3.1190, -60.0217),   # Manaus
    "BA": (-12.9777, -38.5016),  # Salvador
    "CE": (-3.7172, -38.5433),   # Fortaleza
    "DF": (-15.7801, -47.9292),  # Brasília
    "ES": (-20.3155, -40.3128),  # Vitória
    "GO": (-16.6869, -49.2648),  # Goiânia
    "MA": (-2.5307, -44.3068),   # São Luís
    "MT": (-15.6014, -56.0979),  # Cuiabá
    "MS": (-20.4697, -54.6201),  # Campo Grande
    "MG": (-19.9167, -43.9345),  # Belo Horizonte
    "PA": (-1.4558, -48.4902),   # Belém
    "PB": (-7.1195, -34.8450),   # João Pessoa
    "PR": (-25.4284, -49.2733),  # Curitiba
    "PE": (-8.0476, -34.8770),   # Recife
    "PI": (-5.0892, -42.8019),   # Teresina
    "RJ": (-22.9068, -43.1729),  # Rio de Janeiro
    "RN": (-5.7945, -35.2110),   # Natal
    "RS": (-30.0346, -51.2177),  # Porto Alegre
    "RO": (-8.7619, -63.9039),   # Porto Velho
    "RR": (2.8235, -60.6758),    # Boa Vista
    "SC": (-27.5954, -48.5480),  # Florianópolis
    "SP": (-23.5505, -46.6333),  # São Paulo
    "SE": (-10.9472, -37.0731),  # Aracaju
    "TO": (-10.1689, -48.3317),  # Palmas
}

#: Raio médio da Terra (km, WGS84 aproximado) — constante de geociência
#: pública, usada por qualquer implementação padrão de Haversine.
RAIO_TERRA_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância em linha reta (km) entre duas coordenadas, fórmula de
    Haversine (aproxima a Terra como esfera — suficiente para "distância
    até a capital da UF", não para navegação de precisão)."""
    lat1r, lon1r, lat2r, lon2r = (math.radians(v) for v in (lat1, lon1, lat2, lon2))
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1r) * math.cos(lat2r) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(min(1.0, math.sqrt(a)))
    return RAIO_TERRA_KM * c


def distancia_km_uf(uf: str | None, lat: float | None, lon: float | None) -> float | None:
    """Distância (km) entre `(lat, lon)` e a capital da UF informada.
    `None` quando a UF é desconhecida/vazia ou a coordenada não veio —
    nunca inventa um valor."""
    if not uf or lat is None or lon is None:
        return None
    coords = UF_COORDENADAS.get(uf.strip().upper())
    if not coords:
        return None
    return round(haversine_km(lat, lon, coords[0], coords[1]), 1)
