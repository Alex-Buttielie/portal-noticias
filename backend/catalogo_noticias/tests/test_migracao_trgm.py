"""
Run 20260923-1216-p1-feed-cache-indices (P1-2) — critério de aceite 7:
a migração `pg_trgm`/GIN (`0011_newsitem_busca_trgm.py`) existe, aplica
limpo no sqlite (dev/teste local) e emite o SQL correto para Postgres.

- Parte sqlite: o grafo de migrações do banco de teste não tem pendências
  (todas — inclusive 0009/0010/0011 — foram aplicadas do zero pelo
  pytest-django) e `aplicar_trgm`/`remover_trgm` são no-op fora do
  Postgres (guarda por `connection.vendor`, sem falhar o `migrate`).
- Parte Postgres: a validade real sai no CI (job backend-tests com serviço
  postgres:16). Aqui validamos o SQL que a migração emitiria usando um
  schema_editor FAKE com `vendor="postgresql"` — `CREATE EXTENSION IF NOT
  EXISTS pg_trgm` + `CREATE INDEX ... USING gin` sobre os campos da busca;
  `DROP INDEX IF EXISTS` no reverso. Nenhum banco de verdade é tocado.

Teste somente-leitura sobre comportamento (verificação pré-deploy):
nenhum código de produção é alterado aqui.
"""

from __future__ import annotations

import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = pytest.mark.django_db

# O nome do módulo começa com dígito (padrão Django de numeração de
# migração), então a importação precisa ser via `importlib` — mesmo padrão
# de `feed/tests/test_p1_feed_cache_indices.py` para a migração 0009.
_MIGRACAO_TRGM = "catalogo_noticias.migrations.0011_newsitem_busca_trgm"

_CAMPOS_BUSCA = ("titulo", "resumo_proprio", "conteudo_completo")


class _CursorFake:
    """Captura o SQL que a migração emitiria, sem tocar banco de verdade."""

    def __init__(self):
        self.sql_emitido: list[str] = []

    def execute(self, sql, params=None):
        self.sql_emitido.append(sql)

    # `aplicar_trgm` usa `with ...cursor() as cursor:` — o fake precisa
    # funcionar como context manager.
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _ConexaoFake:
    def __init__(self, vendor):
        self.vendor = vendor
        self._cursor = _CursorFake()

    def cursor(self):
        return self._cursor


class _SchemaEditorFake:
    """Substituto mínimo do `SchemaEditor` — só expõe `.connection`."""

    def __init__(self, vendor):
        self.connection = _ConexaoFake(vendor)


def _migracao():
    return importlib.import_module(_MIGRACAO_TRGM)


class TestGrafoMigracoesSqlite:
    def test_migracoes_novas_aplicam_limpo_no_banco_de_teste(self):
        # Crit. 7 (parte sqlite): o plano de migração vazio prova que TODAS
        # as migrações — inclusive 0009 (coluna + backfill), 0010 (índices)
        # e 0011 (pg_trgm/GIN com guarda) — foram aplicadas do zero no
        # sqlite do banco de teste criado pelo pytest-django.
        executor = MigrationExecutor(connection)
        plano = executor.migration_plan(executor.loader.graph.leaf_nodes())
        assert plano == []

    def test_aplicar_trgm_e_noop_no_sqlite(self):
        # Guarda por vendor: em sqlite (dev/teste local) a migração NÃO
        # emite SQL e NÃO falha — é exatamente o no-op que o contrato pede
        # (sem CREATE EXTENSION fora do postgresql).
        schema_editor = _SchemaEditorFake("sqlite")
        _migracao().aplicar_trgm(None, schema_editor)
        assert schema_editor.connection._cursor.sql_emitido == []

    def test_remover_trgm_e_noop_no_sqlite(self):
        # Reverso também no-op em sqlite (migração reversível sem efeito
        # fora do Postgres).
        schema_editor = _SchemaEditorFake("sqlite")
        _migracao().remover_trgm(None, schema_editor)
        assert schema_editor.connection._cursor.sql_emitido == []


class TestSqlPostgresTrgm:
    def test_aplicar_trgm_emite_create_extension_e_gin(self):
        # Crit. 7 (parte Postgres, via SQL emitido): com vendor postgresql a
        # migração cria a extensão pg_trgm (IF NOT EXISTS — idempotente) e o
        # índice GIN trigram sobre EXATAMENTE os campos da busca usados por
        # `feed/busca.py` (icontains/LIKE).
        schema_editor = _SchemaEditorFake("postgresql")
        _migracao().aplicar_trgm(None, schema_editor)
        sql = schema_editor.connection._cursor.sql_emitido
        assert len(sql) == 2
        assert "CREATE EXTENSION IF NOT EXISTS pg_trgm" in sql[0]
        assert "CREATE INDEX IF NOT EXISTS newsitem_busca_trgm" in sql[1]
        assert "USING gin" in sql[1]
        for campo in _CAMPOS_BUSCA:
            assert f"{campo} gin_trgm_ops" in sql[1], campo

    def test_remover_trgm_emite_drop_index(self):
        # Reverso no Postgres: dropa o índice (IF EXISTS) — a extensão é
        # mantida (comentário da própria migração: outros apps podem usá-la).
        schema_editor = _SchemaEditorFake("postgresql")
        _migracao().remover_trgm(None, schema_editor)
        sql = schema_editor.connection._cursor.sql_emitido
        assert len(sql) == 1
        assert "DROP INDEX IF EXISTS newsitem_busca_trgm" in sql[0]

    def test_guarda_nao_emite_nada_em_outro_vendor(self):
        # Defesa em profundidade: qualquer vendor que não seja postgresql
        # (ex.: sqlite3, mysql) não recebe nenhum SQL da migração.
        schema_editor = _SchemaEditorFake("mysql")
        _migracao().aplicar_trgm(None, schema_editor)
        _migracao().remover_trgm(None, schema_editor)
        assert schema_editor.connection._cursor.sql_emitido == []
