"""Leitura da configuração do robô com snapshot por execução de ingestão.

O pipeline chama ``cfg_valor`` em vários pontos (limites, dedup, resumo e
orçamento). Fazer uma consulta a ``ConfiguracaoRobo`` em cada chamada era
desnecessário dentro da mesma rodada: o contexto abaixo captura uma única
linha no início e libera o snapshot ao terminar, inclusive em caso de
exceção. Fora de uma execução, o comportamento continua sendo o anterior
(uma consulta por chamada), para que endpoints administrativos não fiquem
com configuração obsoleta.
"""

from contextlib import contextmanager
from contextvars import ContextVar

from django.conf import settings


_SEM_CACHE = object()
_cfg_execucao: ContextVar[object] = ContextVar(
    "configuracao_robo_execucao", default=_SEM_CACHE
)


def _consultar_cfg():
    try:
        from catalogo_noticias.models import ConfiguracaoRobo

        return ConfiguracaoRobo.objects.filter(pk=1).first()
    except Exception:
        # Uma falha de banco/tabela não deve impedir o fallback para settings
        # (mesmo comportamento de cfg_valor antes do snapshot).
        return None


def _get_cfg():
    if _cfg_execucao.get() is not _SEM_CACHE:
        return _cfg_execucao.get()
    return _consultar_cfg()


@contextmanager
def cache_por_execucao():
    """Captura uma configuração para a duração de uma execução.

    O ContextVar isola execuções concorrentes (inclusive a thread da
    execução manual), e o token é restaurado para suportar aninhamento e
    evitar vazamento de configuração para a próxima tarefa/request.
    """

    token = _cfg_execucao.set(_consultar_cfg())
    try:
        yield
    finally:
        _cfg_execucao.reset(token)


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
            ativas = list(
                FonteRobo.objects.filter(ativo=True).values(
                    "id",
                    "nome",
                    "url",
                    "categoria_padrao",
                    "estado_padrao",
                    "etag",
                    "last_modified",
                    "ultima_revalidacao_completa",
                )
            )
            if ativas:
                return [
                    {
                        "id": r["id"],
                        "nome": r["nome"],
                        "url": r["url"],
                        "uf": (r["estado_padrao"] or "").strip().upper(),
                        "etag": r.get("etag") or "",
                        "last_modified": r.get("last_modified") or "",
                        "ultima_revalidacao_completa": r.get(
                            "ultima_revalidacao_completa"
                        ),
                    }
                    for r in ativas
                ]
            all_count = FonteRobo.objects.count()
            if all_count > 0:
                return []
    except Exception:
        pass
    return [
        {**f, "uf": (f.get("uf") or "").strip().upper()}
        for f in settings.CATALOGO_NOTICIAS_FONTES_RSS
    ]
