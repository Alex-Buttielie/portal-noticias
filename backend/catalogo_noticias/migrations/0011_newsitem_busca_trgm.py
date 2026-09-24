"""
Run 20260923-1216-p1-feed-cache-indices (P1-2): extensão `pg_trgm` + índice
GIN trigram sobre os campos de busca textual (`feed/busca.py` filtra com
`icontains`/`LIKE` sobre eles — o índice acelera sem reescrever as queries).

Isolada em migração própria com guarda por `connection.vendor`: no sqlite
(dev/teste local) vira no-op sem falhar o `migrate`; o caminho real só
executa em PostgreSQL (CI/prod). Reversível no Postgres (`DROP INDEX IF
EXISTS`; a extensão é mantida — outros apps podem usá-la).

Operação: rodar `migrate` em janela fria — `CREATE INDEX` (não-CONCURRENTLY)
bloqueia escrita em `catalogo_noticias_newsitem` durante a construção do GIN
(tabela com `conteudo_completo` = índice pesado). `CONCURRENTLY` não roda
dentro da transação de migração do Django sem esquema especial, por isso o
bloqueio é aceito conscientemente.
"""

from django.db import migrations


_CAMPOS_TRGM = ("titulo", "resumo_proprio", "conteudo_completo")
_INDICE_GIN = "newsitem_busca_trgm"
_TABELA = "catalogo_noticias_newsitem"


def aplicar_trgm(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        colunas = ", ".join(f"{campo} gin_trgm_ops" for campo in _CAMPOS_TRGM)
        cursor.execute(
            f"CREATE INDEX IF NOT EXISTS {_INDICE_GIN} "
            f"ON {_TABELA} USING gin ({colunas})"
        )


def remover_trgm(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP INDEX IF EXISTS {_INDICE_GIN}")


class Migration(migrations.Migration):

    dependencies = [
        ("catalogo_noticias", "0010_newsitem_feed_status_ingestao_and_more"),
    ]

    operations = [
        migrations.RunPython(aplicar_trgm, remover_trgm),
    ]
