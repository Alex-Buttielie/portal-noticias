from django.conf import settings


def _get_cfg():
    try:
        from catalogo_noticias.models import ConfiguracaoRobo

        cfg = ConfiguracaoRobo.objects.filter(pk=1).first()
        return cfg
    except Exception:
        return None


def cfg_valor(campo_settings, campo_modelo, cast=None):
    cfg = _get_cfg()
    if cfg is None:
        return getattr(settings, campo_settings)
    try:
        v = getattr(cfg, campo_modelo)
        return cast(v) if cast else v
    except Exception:
        return getattr(settings, campo_settings)


def categorias_sensiveis():
    cfg = _get_cfg()
    if cfg is None:
        return settings.CATALOGO_NOTICIAS_CATEGORIAS_SENSIVEIS
    raw = (cfg.categorias_sensiveis or "").strip()
    if not raw:
        return []
    return [c.strip().lower() for c in raw.split(",") if c.strip()]


def fontes_rss():
    try:
        from catalogo_noticias.models import FonteRobo

        if FonteRobo.objects.exists():
            ativas = list(FonteRobo.objects.filter(ativo=True).values("nome", "url", "categoria_padrao"))
            if ativas:
                return [{"nome": r["nome"], "url": r["url"]} for r in ativas]
            all_count = FonteRobo.objects.count()
            if all_count > 0:
                return []
    except Exception:
        pass
    return settings.CATALOGO_NOTICIAS_FONTES_RSS
