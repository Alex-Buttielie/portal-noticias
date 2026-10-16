"""FRENTE 6 — Central de Métricas/Inteligência.

`EventoSite` cobre os eventos COMPORTAMENTAIS que NÃO estão nos modelos do
`feed` (FRENTE 3: `InteracaoNoticia` = view/click/read/save/share/search_click
por entrada + `EventoBusca` = buscas). Nada aqui duplica aqueles sinais:

- `feed.InteracaoNoticia`/`EventoBusca` continuam sendo a ÚNICA fonte para
  news_view/news_click/share/save/search/search_result_click (o endpoint de
  ingestão `POST /api/metricas/eventos/` roteia esses tipos para lá);
- `EventoSite` guarda o restante da taxonomia: page_view, category_view/
  click, author_view/columnist_view, radar_view, location_permission/
  location_selected, home_section_view/click, community_view/interaction.

LGPD: localização (pais/estado/cidade/regiao) só é enviada pelo frontend
depois de consentimento explícito (`analytics` em `cookie-consent.ts` + gesto
de permissão/seleção de região). O backend NUNCA inventa localização nem
deriva de IP — armazena só o que recebeu. Sem IP, sem user-agent bruto.
"""

from django.conf import settings
from django.db import models


class EventoSite(models.Model):
    TIPO_PAGE_VIEW = "page_view"
    TIPO_CATEGORY_VIEW = "category_view"
    TIPO_CATEGORY_CLICK = "category_click"
    TIPO_AUTHOR_VIEW = "author_view"
    TIPO_COLUMNIST_VIEW = "columnist_view"
    TIPO_RADAR_VIEW = "radar_view"
    TIPO_LOCATION_PERMISSION = "location_permission"
    TIPO_LOCATION_SELECTED = "location_selected"
    TIPO_HOME_SECTION_VIEW = "home_section_view"
    TIPO_HOME_SECTION_CLICK = "home_section_click"
    TIPO_COMMUNITY_VIEW = "community_view"
    TIPO_COMMUNITY_INTERACTION = "community_interaction"
    # M-10 (run 20261012-1806-monetizacao-sprint1) — impressão/clique de
    # `PatrocinioSlot` (frontend). Mesma regra de consentimento das demais
    # entradas desta tabela: só registrado com `analytics` concedido.
    TIPO_PATROCINIO_VIEW = "patrocinio_view"
    TIPO_PATROCINIO_CLICK = "patrocinio_click"

    TIPO_CHOICES = [
        (TIPO_PAGE_VIEW, "Visualização de página"),
        (TIPO_CATEGORY_VIEW, "Visualização de categoria/editoria"),
        (TIPO_CATEGORY_CLICK, "Clique em categoria/editoria"),
        (TIPO_AUTHOR_VIEW, "Visualização de autor"),
        (TIPO_COLUMNIST_VIEW, "Visualização de colunista"),
        (TIPO_RADAR_VIEW, "Visualização do radar"),
        (TIPO_LOCATION_PERMISSION, "Permissão de localização"),
        (TIPO_LOCATION_SELECTED, "Região selecionada"),
        (TIPO_HOME_SECTION_VIEW, "Visualização de seção da Home"),
        (TIPO_HOME_SECTION_CLICK, "Clique em seção da Home"),
        (TIPO_COMMUNITY_VIEW, "Visualização da comunidade"),
        (TIPO_COMMUNITY_INTERACTION, "Interação na comunidade"),
        (TIPO_PATROCINIO_VIEW, "Visualização de patrocínio"),
        (TIPO_PATROCINIO_CLICK, "Clique em patrocínio"),
    ]
    TIPOS_VALIDOS = {c[0] for c in TIPO_CHOICES}

    ORIGEM_BUSCA = "busca"
    ORIGEM_SOCIAL = "social"
    ORIGEM_DIRETO = "direto"
    ORIGEM_REFERENCIA = "referencia"
    ORIGEM_CAMPANHA = "campanha"
    ORIGEM_CHOICES = [
        (ORIGEM_BUSCA, "Busca"),
        (ORIGEM_SOCIAL, "Social"),
        (ORIGEM_DIRETO, "Direto"),
        (ORIGEM_REFERENCIA, "Referência"),
        (ORIGEM_CAMPANHA, "Campanha"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="eventos_site",
    )
    # Sessão anônima (gerada no navegador, `analytics.ts`) — permite contar
    # sessões/usuários recorrentes sem identificar ninguém.
    sessao = models.CharField(max_length=64, blank=True, db_index=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, db_index=True)
    path = models.CharField(max_length=500, blank=True)
    categoria = models.CharField(max_length=100, blank=True, db_index=True)
    # Referência textual a autor/colunista (nome ou id) — nunca inventada.
    autor_ref = models.CharField(max_length=200, blank=True)
    # Seção da Home: manchetes|em_alta|ultimas|portfolio|perto|radar|comunidade...
    secao_home = models.CharField(max_length=60, blank=True, db_index=True)
    origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES, blank=True, db_index=True)
    dispositivo = models.CharField(max_length=20, blank=True, db_index=True)
    # Localização — SÓ quando consentida/selecionada (ver docstring do módulo).
    pais = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=150, blank=True)
    regiao = models.CharField(max_length=150, blank=True)
    tempo_permanencia_seg = models.PositiveIntegerField(default=0)
    scroll_max_pct = models.PositiveIntegerField(default=0)
    extra = models.JSONField(default=dict, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "evento do site"
        verbose_name_plural = "eventos do site"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["tipo", "-criado_em"]),
            models.Index(fields=["sessao", "-criado_em"]),
            models.Index(fields=["categoria", "-criado_em"]),
        ]

    def __str__(self):
        return f"{self.tipo} {self.path or '-'} ({self.criado_em:%d/%m %H:%M})"


def mascarar_ip(ip: str) -> str:
    """Mascara um IP para exibição/armazenamento — o valor completo NUNCA
    existe fora desta função: quem chama passa o IP cru e recebe só o
    mascarado, que é o único valor que `AcessoIP.save()` vê.

    IPv4: mantém os 2 primeiros octetos, mascara os 2 últimos
    ("203.0.xxx.xxx") — o suficiente para reconhecer faixa/provedor sem
    identificar o host. IPv6: mantém os 2 primeiros grupos. Entrada vazia ou
    não reconhecida como IP vira string vazia (quem chama decide se grava).
    """
    ip = (ip or "").strip()
    if not ip:
        return ""
    if ":" in ip:
        grupos = [g for g in ip.split(":") if g][:2]
        if not grupos:
            return ""
        return ":".join(grupos) + ":xxxx:xxxx"
    partes = ip.split(".")
    if len(partes) == 4 and all(p.isdigit() for p in partes):
        return f"{partes[0]}.{partes[1]}.xxx.xxx"
    return ""


class AcessoIP(models.Model):
    """Contagem de acessos ao site por IP MASCARADO.

    Gravado só em `page_view` (ver `EventoIngestaoView._registrar_site`) —
    mesmo portão de consentimento do resto de `EventoSite`: `track()` em
    `frontend/lib/analytics.ts` é fail-closed sem `permiteCategoria
    ("analytics")`, então esta tabela só recebe linha quando a mesma pessoa
    que teria um `page_view` registrado também consentiu.

    O IP completo nunca chega a existir aqui: `mascarar_ip()` corta os dois
    últimos octetos/grupos ANTES do `.create()` — a mesma garantia de "sem
    IP" do resto do módulo, só que aqui o residual mascarado tem valor de
    produto (reconhecer padrão de acesso por faixa) que o resto da tabela
    não precisa.
    """

    ip_mascarado = models.CharField(max_length=48, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "acesso por IP"
        verbose_name_plural = "acessos por IP"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["ip_mascarado", "-criado_em"])]

    def __str__(self):
        return f"{self.ip_mascarado} ({self.criado_em:%d/%m %H:%M})"
