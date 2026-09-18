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
