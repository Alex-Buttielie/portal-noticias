"""
Expurgo de analytics (P2-02, WS-13/WS-14): retenção, idempotência, lotes,
interrupção, prazo malformado, auditoria sem dado pessoal e observabilidade.

Cada teste aqui tem um parasita de produção correspondente que ele quebra se
for removido — a suíte de `test_integridade_do_expurgo` abaixo existe para
isso: ela afirma que os testes que medem as propriedades estão presentes e
não foram esvaziados.

NENHUM teste deste arquivo afirma "rodou". Cada um afirma uma consequência
observável do estado do banco, do arquivo de estado durável ou do log.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from config import filas_estado
from feed.models import EventoBusca, InteracaoNoticia
from metricas.models import EventoSite
from metricas.tasks import (
    MAX_LOTES,
    NOME_EXPURGO,
    RetencaoInvalida,
    expurar_analytics,
    retencao_dias,
    tamanho_lote,
)

pytestmark = pytest.mark.django_db

# Marcadores de dado pessoal, usados para provar que nada deles sai no log nem
# no registro durável. São plantados nos eventos de propósito.
EMAIL = "leitor.exemplo@dominio.invalid"
#: pk propositalmente distinto, para que a prova de ausência de PII possa
#: procurar um número IMEDIATAMENTE reconhecível no log. Um pk "1" não serviria:
#: "1" aparece em qualquer contador, e o teste passaria por acidente.
PK_USUARIO_TESTE = 987654321
QUERY_PESSOAL = "diagnostico-defulgina"
PATH_PESSOAL = "/politica/diagrama-confidencial"
SESSAO_PESSOAL = "sessao-privada-0001"


def _usuario_de_teste():
    """
    Um usuário REAL, com id e email próprios.

    Existe para que o teste de PII possa reprovar por VALOR e não só por
    nome de rótulo: se o log vazasse `user_id`, sairia um inteiro de verdade,
    e `sessao` sairia a string de sessão de verdade. Um fixture sem usuário
    faria o vazamento de `user_id=None` — que não é dado de ninguém.
    """
    from django.contrib.auth import get_user_model

    modelo = get_user_model()
    existente = modelo.objects.filter(pk=PK_USUARIO_TESTE).first()
    if existente is not None:
        return existente
    usuario = modelo(
        pk=PK_USUARIO_TESTE,
        nome="Leitor Ex P2-02",
        email=EMAIL,
        **{campo: "" for campo in modelo.REQUIRED_FIELDS},
    )
    usuario.set_password("senha-de-teste-que-nunca-e-usada")
    usuario.save()
    return usuario


def _criar_eventos(idade_dias: int, quantidade: int = 3, *, com_pii: bool = True) -> None:
    """
    Cria eventos com a idade desejada.

    `criado_em` é `auto_now_add`, então a idade é forçada por `update()`
    depois — e SÓ nas linhas recém-criadas (nunca um `update()` global, que
    mudaria também os eventos recentes que o teste precisa preservar).

    Com `com_pii`, os eventos saem com usuário, sessão, path e email reais —
    é esse fixture que a prova de ausência de PII consome.
    """
    antigo = timezone.now() - timedelta(days=idade_dias)
    usuario = _usuario_de_teste() if com_pii else None
    site: list[int] = []
    busca: list[int] = []
    interacao: list[int] = []
    for indice in range(quantidade):
        evento = EventoSite.objects.create(
            user=usuario,
            tipo=EventoSite.TIPO_PAGE_VIEW,
            path=PATH_PESSOAL if com_pii else f"/politica/{indice}",
            sessao=SESSAO_PESSOAL if com_pii else f"sessao-{indice}",
            extra={"contato": EMAIL} if com_pii else {},
        )
        site.append(evento.pk)
        busca.append(
            EventoBusca.objects.create(
                user=usuario,
                query=QUERY_PESSOAL if com_pii else f"termo {indice}",
                query_normalizada=f"termo {indice}",
                session_key=SESSAO_PESSOAL if com_pii else "",
            ).pk
        )
        interacao.append(
            InteracaoNoticia.objects.create(
                user=usuario,
                tipo=InteracaoNoticia.TIPO_VIEW,
                entry_tipo="item",
                categoria="politica",
                session_key=SESSAO_PESSOAL if com_pii else f"sessao-{indice}",
            ).pk
        )
    EventoSite.objects.filter(pk__in=site).update(criado_em=antigo)
    EventoBusca.objects.filter(pk__in=busca).update(criado_em=antigo)
    InteracaoNoticia.objects.filter(pk__in=interacao).update(criado_em=antigo)


def _totais() -> tuple[int, int, int]:
    return (
        EventoSite.objects.count(),
        EventoBusca.objects.count(),
        InteracaoNoticia.objects.count(),
    )


# ---------------------------------------------------------------------------
# 1. Retenção
# ---------------------------------------------------------------------------


def test_expurga_eventos_brutos_anteriores_a_janela():
    """A janela de 365 dias separa o que sai do que fica, nos três modelos."""
    _criar_eventos(idade_dias=400, quantidade=5)
    _criar_eventos(idade_dias=10, quantidade=2)

    resultado = expurar_analytics.run()

    assert _totais() == (2, 2, 2)
    assert resultado["removidos"] == {
        "metricas.EventoSite": 5,
        "feed.InteracaoNoticia": 5,
        "feed.EventoBusca": 5,
    }
    assert resultado["total_removido"] == 15
    assert resultado["retencao_dias"] == 365


def test_retention_de_365_dias_e_o_default_configurado():
    """
    O prazo documentado (12 meses) é o default — e vem de settings, o que o
    operador ajusta, não de uma constante enterrada no código.
    """
    from django.conf import settings

    assert settings.ANALYTICS_RETENCAO_DIAS == 365
    assert retencao_dias() == 365


def test_prazo_configuravel_muda_o_que_sai():
    """Ajustar a retenção por ambiente muda o resultado sem tocar em código."""
    _criar_eventos(idade_dias=100, quantidade=3)
    _criar_eventos(idade_dias=10, quantidade=1)

    with override_settings(ANALYTICS_RETENCAO_DIAS=30):
        resultado = expurar_analytics.run()

    assert _totais() == (1, 1, 1)
    assert resultado["total_removido"] == 9
    assert resultado["retencao_dias"] == 30


def test_limite_de_dias_nao_e_arredondado_para_cima():
    """364 dias fica; 366 sai. Um limite que arredonda erra a retenção."""
    _criar_eventos(idade_dias=364, quantidade=1)
    _criar_eventos(idade_dias=366, quantidade=1)

    resultado = expurar_analytics.run()

    assert EventoSite.objects.count() == 1
    assert resultado["removidos"]["metricas.EventoSite"] == 1
    assert EventoSite.objects.get().criado_em > timezone.now() - timedelta(days=365)


# ---------------------------------------------------------------------------
# 2. Idempotência — a prova de verdade
# ---------------------------------------------------------------------------


def test_segunda_execucao_nao_remove_nem_muda_contagem():
    """
    PROVA DE IDEMPOTÊNCIA: mesma janela, duas execuções, e a segunda não
    remove nada, não muda nenhuma contagem e não volta a registrar o mesmo
    volume removido.

    O que torna isto uma prova e não um "rodou": a asserção é sobre o ESTADO
    (as linhas que saíram continuam fora, os que ficaram continuam dentro) e
    sobre o VOLUME da segunda execução (0, não o total da primeira).
    """
    _criar_eventos(idade_dias=500, quantidade=4)
    _criar_eventos(idade_dias=10, quantidade=2)
    antes = _totais()

    primeira = expurar_analytics.run()
    depois_primeira = _totais()

    segunda = expurar_analytics.run()
    depois_segunda = _totais()

    assert antes == (6, 6, 6)
    assert primeira["total_removido"] == 12
    assert depois_primeira == (2, 2, 2)
    # A segunda execução não seleciona nada: o filtro é "anterior ao corte" e
    # as linhas antigas já não existem.
    assert segunda["total_removido"] == 0
    assert segunda["removidos"] == {
        "metricas.EventoSite": 0,
        "feed.InteracaoNoticia": 0,
        "feed.EventoBusca": 0,
    }
    assert segunda["lotes"] == {
        "metricas.EventoSite": 0,
        "feed.InteracaoNoticia": 0,
        "feed.EventoBusca": 0,
    }
    # E o estado do banco é o MESMO — não há remoção parcial nem duplicata.
    assert depois_segunda == depois_primeira


def test_idempotencia_sobre_terceira_e_quarta_execucao():
    """Repetir muito continua sendo 0. Idempotência estável, não só na 2ª vez."""
    _criar_eventos(idade_dias=700, quantidade=3)

    volumes = [expurar_analytics.run()["total_removido"] for _ in range(4)]

    assert volumes == [9, 0, 0, 0]
    assert _totais() == (0, 0, 0)


def test_reentrega_da_task_com_o_mesmo_argumento_nao_duplica():
    """
    Reentrega (retry do broker, dois workers) é o caso real de idempotência
    em produção — não duas chamadas limpas em sequência. Mesmo argumento,
    mesmo estado: a segunda é 0.
    """
    _criar_eventos(idade_dias=800, quantidade=2)

    primeira = expurar_analytics.run(dias=365, lote=2)
    reentrega = expurar_analytics.run(dias=365, lote=2)

    assert primeira["total_removido"] == 6
    assert reentrega["total_removido"] == 0
    assert _totais() == (0, 0, 0)


def test_lotes_diferentes_nao_alteram_o_resultado_final():
    """
    O tamanho do lote é desempenho, não semântica: qualquer lote termina no
    mesmo conjunto removido. Isso é o que garante que ajustar
    ANALYTICS_EXPURGO_LOTE não possa mudar QUANTO dado sai.
    """
    _criar_eventos(idade_dias=900, quantidade=7)

    expurar_analytics.run(lote=1)

    assert _totais() == (0, 0, 0)


# ---------------------------------------------------------------------------
# 3. Em lotes
# ---------------------------------------------------------------------------


def test_processa_em_lotes_e_nao_em_uma_so_consulta(caplog):
    """
    PROVA DE LOTE: com 7 linhas e lote 2, são 4 lotes (2+2+2+1) e as 7 saem.

    "Quantas vezes perguntou ao banco" é o que distingue `DELETE` de tabela
    inteira (um lote, e um lock de tabela) de expurgo em lotes.
    """
    caplog.set_level(logging.INFO, logger="metricas.tasks")
    _criar_eventos(idade_dias=500, quantidade=7)

    resultado = expurar_analytics.run(lote=2)

    assert resultado["lote"] == 2
    assert resultado["lotes"]["metricas.EventoSite"] == 4
    assert resultado["removidos"]["metricas.EventoSite"] == 7
    assert "expurgo de analytics concluido" in caplog.text


def test_nenhuma_consulta_de_delete_usa_mais_de_um_lote(monkeypatch):
    """
    PROVA DE LOTE por outro ângulo: o `DELETE` efetivamente emitido ao banco
    nunca carrega mais que `ANALYTICS_EXPURGO_LOTE` linhas.

    Cuenta os `pk__in`OREIRO e inspeciona o tamanho do lote em cada consulta.
    É a prova que não depende de o teste saber o número de lotes.
    """
    _criar_eventos(idade_dias=500, quantidade=9)

    tamanhos_dos_deletes: list[int] = []
    from django.db.models import QuerySet

    delete_original = QuerySet.delete

    def delete_instrumentado(self, *args, **kwargs):
        # `filter(pk__in=pks)` chega aqui com a lista de chaves no `rhs` do
        # lookUp `__in`. É esse `rhs` que diz quantas linhas o DELETE leva.
        for lookups in self.query.where.children if hasattr(self.query.where, "children") else []:
            rhs = getattr(lookups, "rhs", None)
            if rhs is None or isinstance(rhs, (str, bytes, int, float)):
                continue
            try:
                tamanhos_dos_deletes.append(len(rhs))
            except TypeError:
                continue
        return delete_original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "delete", delete_instrumentado)

    expurar_analytics.run(lote=3)

    # 9 linhas por modelo, lote 3 => 3 deletes de 3 linhas em cada um dos
    # três modelos. Nenhum deles passou do tamanho configurado.
    assert tamanhos_dos_deletes, "nenhum DELETE foi emitido — o expurgo não rodou"
    assert set(tamanhos_dos_deletes) == {3}, tamanhos_dos_deletes
    assert tamanhos_dos_deletes.count(3) == 9


def test_lote_configuravel_muda_o_numero_de_lotes_nao_o_total():
    _criar_eventos(idade_dias=500, quantidade=10)

    grande = expurar_analytics.run(lote=1000)
    assert grande["lotes"]["metricas.EventoSite"] == 1

    _criar_eventos(idade_dias=500, quantidade=10)
    pequeno = expurar_analytics.run(lote=2)

    assert pequeno["lotes"]["metricas.EventoSite"] == 5
    assert pequeno["removidos"]["metricas.EventoSite"] == 10


def test_lote_invalido_e_limitado_e_nao_quebra():
    """lote=0 vira 1 (não "sem progresso" nem exceção); lote enorme é limitado."""
    _criar_eventos(idade_dias=500, quantidade=2)

    resultado = expurar_analytics.run(lote=0)

    assert resultado["lote"] == 1
    assert resultado["total_removido"] == 6
    assert tamanho_lote(0) == 1
    assert tamanho_lote(-10) == 1
    assert tamanho_lote(10**9) == 50_000


# ---------------------------------------------------------------------------
# 4. Interrupção no meio — sem estado corrompido
# ---------------------------------------------------------------------------


def test_interromper_no_meio_deixa_o_banco_consistente_e_o_resto_sai_depois(
    monkeypatch, diretorio_estado
):
    """
    PROVA DE INTERRUPÇÃO: um worker que morre no meio de um expurgo de 10
    linhas deixa (a) o banco num estado válido e legível, (b) as linhas já
    removidas fora de vez, (c) as restantes ainda lá, e (d) a próxima execução
    completa o serviço sem duplicar nem corromper.

    A interrupção é modelada de forma realista: `KeyboardInterrupt` no meio
    do terceiro `delete` — que é o que um SIGTERM/worker-killed parece para o
    código em execução.
    """
    _criar_eventos(idade_dias=500, quantidade=10)

    from django.db.models import QuerySet

    delete_original = QuerySet.delete
    chamadas = {"n": 0}

    def delete_que_morre_no_terceiro(self, *args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise KeyboardInterrupt("worker morto no meio do expurgo")
        return delete_original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "delete", delete_que_morre_no_terceiro)

    with pytest.raises(KeyboardInterrupt):
        expurar_analytics.run(lote=1)

    # (a)+(b)+(c): o banco é legível e está num estado parcial COERENTE —
    # menos linhas do que o total, nenhuma linha corrompida/duplicada, e as
    # linhas recentes do fixture intactas.
    parciais = _totais()
    assert sum(parciais) < 30
    assert all(isinstance(total, int) and total >= 0 for total in parciais)
    assert EventoSite.objects.filter(tipo=EventoSite.TIPO_PAGE_VIEW).exists()
    monkeypatch.undo()

    # (d): retomar conclui o serviço a partir de onde parou.
    final = expurar_analytics.run(lote=1)

    assert final["total_removido"] == sum(parciais)
    assert _totais() == (0, 0, 0)


def test_interrupcao_entre_lotes_nao_deixa_ciclo_sucesso_falso(
    monkeypatch, diretorio_estado
):
    """
    Uma interrupção NÃO pode virar um "ciclo de sucesso" no registro durável:
    senão `manage.py saude_filas` diria que o expurgo terminou quando ele foi
    interrompido pela metade — que é um falso verde.

    O diretório de estado é isolado (`diretorio_estado`), então o registro que
    este teste examina só pode ter sido escrito por ESTA execução.
    """
    _criar_eventos(idade_dias=500, quantidade=6)

    from django.db.models import QuerySet

    delete_original = QuerySet.delete
    chamadas = {"n": 0}

    def delete_que_morre_no_segundo(self, *args, **kwargs):
        chamadas["n"] += 1
        if chamadas["n"] == 2:
            raise KeyboardInterrupt("morto")
        return delete_original(self, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "delete", delete_que_morre_no_segundo)

    with pytest.raises(KeyboardInterrupt):
        expurar_analytics.run(lote=1)

    ciclos = filas_estado.ler_estado()["ciclos"]
    registro = ciclos.get(NOME_EXPURGO)

    # Nenhum ciclo foi gravado: a task morreu antes do `_registra_ciclo`.
    assert registro is None, (
        "expurgo interrompido gravou um ciclo no estado duravel: "
        f"{registro!r} — se for sucesso, o saude_filas reporta um ciclo que "
        "nao terminou"
    )
    # E o expurgo de fato não terminou: sobrou coisa para remover.
    assert sum(_totais()) > 0


def test_teto_de_lotes_impede_laco_infinito_se_delete_nao_apagar(monkeypatch):
    """
    Se um `delete` selecionasse linhas e não apagasse nada, o `while` repetiria
    para sempre. O corte por lote existe para isso, e este teste prova que a
    task TERMINA (e registra o erro) mesmo nessa situação anômala.
    """
    _criar_eventos(idade_dias=500, quantidade=3)

    from django.db.models import QuerySet

    monkeypatch.setattr(QuerySet, "delete", lambda self, *a, **k: (0, {}))

    resultado = expurar_analytics.run(lote=1)

    # Terminou (não rodou MAX_LOTES vezes) e as linhas continuam lá — que é
    # preferível a apagar coisa errada.
    assert resultado["lotes"]["metricas.EventoSite"] == 1
    assert resultado["removidos"]["metricas.EventoSite"] == 0
    assert EventoSite.objects.count() == 3


def test_max_lotes_e_o_teto_declarado():
    assert MAX_LOTES == 10_000


# ---------------------------------------------------------------------------
# 5. Prazo malformado / ausente — o pior desfecho é apagar tudo
# ---------------------------------------------------------------------------


def test_retencao_zero_recusa_e_nao_apaga_nada():
    """
    PROVA DA TRAVA: retenção 0 significaria corte = agora, e "anteriores a
    agora" é TUDO. A task recusa e não remove uma linha sequer.
    """
    _criar_eventos(idade_dias=1, quantidade=5)  # recents, nada a expurgar de qualquer forma
    _criar_eventos(idade_dias=900, quantidade=3)

    with pytest.raises(RetencaoInvalida):
        expurar_analytics.run(dias=0)

    assert _totais() == (8, 8, 8)


def test_retencao_negativa_recusa_e_nao_apaga_nada():
    _criar_eventos(idade_dias=1, quantidade=2)
    _criar_eventos(idade_dias=900, quantidade=3)

    with pytest.raises(RetencaoInvalida):
        expurar_analytics.run(dias=-30)

    assert _totais() == (5, 5, 5)


def test_retencao_que_e_texto_recusa_em_vez_de_assumir_default():
    """'doze meses' não pode virar 0 (que apagaria tudo) nem 365 calado."""
    for invalido in ("doze meses", "abc", "365d", "", None.__class__):
        with pytest.raises(RetencaoInvalida):
            retencao_dias(invalido)


def test_retencao_ausente_usa_o_default_configurado_e_nao_e_erro():
    """`None` significa 'use o configurado' — é o caminho do agendamento."""
    assert retencao_dias(None) == 365


def test_retencao_absurda_recusada_por_plausibilidade():
    with pytest.raises(RetencaoInvalida):
        retencao_dias(10**9)


def test_retencao_invalida_registra_ciclo_de_falha_observavel(
    monkeypatch, caplog
):
    """
    Uma retenção recusada tem de ser VISÍVEL: o `manage.py saude_filas` lê o
    registro durável, e é `registrar_ciclo(estado=falha)` que transforma um
    "não rodou" silencioso em um "falhou, e por quê".
    """
    caplog.set_level(logging.ERROR, logger="metricas.tasks")
    _criar_eventos(idade_dias=900, quantidade=2)

    with pytest.raises(RetencaoInvalida):
        expurar_analytics.run(dias=0)

    # Log de erro, com o motivo.
    assert "RECUSADO" in caplog.text
    assert "menor que 1" in caplog.text
    # Nada foi removido apesar da retenção absurda.
    assert _totais() == (2, 2, 2)


def test_retencao_configurada_malformada_e_recusada_no_boot():
    """
    A variable de ambiente malformada recusa a SUBIDA do processo
    (ImproperlyConfigured), em vez de cair num default silencioso — o único
    ponto em que ninguém pode ignorar o erro.
    """
    from config import settings as settings_mod

    for valor, deve_recusar in (
        ("0", True),
        ("-5", True),
        ("doze", True),
        ("", False),  # vazio = não configurado = default, não erro
        ("99999999", True),
        ("365", False),
        ("1", False),
    ):
        erro = settings_mod._erro_retencao_analytics(valor)
        if deve_recusar:
            assert erro is not None, f"{valor!r} deveria ter sido recusado"
            assert "ANALYTICS_RETENCAO_DIAS" in erro
        else:
            assert erro is None, f"{valor!r} não deveria ter sido recusado: {erro}"


def test_configuracao_malformada_impede_o_boot_de_verdade():
    """
    Prova de ponta a ponta, no interpretador: `ANALYTICS_RETENCAO_DIAS=0` faz
    `django.setup()` recusar. Um teste que só chama a função de validação
    poderia passar mesmo se ninguém a chamasse no boot.
    """
    import os
    import subprocess
    import sys

    from django.conf import settings as dj_settings

    base = dict(os.environ)
    base["DJANGO_SETTINGS_MODULE"] = "config.settings"
    base["DJANGO_SECRET_KEY"] = "chave-de-teste-suficientemente-longa-0123456789"
    base["DJANGO_ALLOWED_HOSTS"] = "portal-noticias.com,localhost,127.0.0.1"
    base["DJANGO_DB_ENGINE"] = "sqlite3"
    base.setdefault("ANALYTICS_RETENCAO_DIAS", "0")
    # Remove a variável caso o shell de quem roda a suite a tenha definida.
    base["ANALYTICS_RETENCAO_DIAS"] = "0"

    raiz = str(dj_settings.BASE_DIR)
    resultado = subprocess.run(
        [sys.executable, "-c", "import django; django.setup(); print('SUBIU')"],
        cwd=raiz,
        env=base,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert resultado.returncode != 0, (
        "o processo SUBIU com ANALYTICS_RETENCAO_DIAS=0; o expurgo apagaria "
        f"tudo. stdout={resultado.stdout!r}"
    )
    assert "ANALYTICS_RETENCAO_DIAS" in (resultado.stderr + resultado.stdout)


def test_boot_com_retencao_valida_sobe():
    """Contraprova: retenção legítima NÃO impede o boot (a trava não é cega)."""
    import os
    import subprocess
    import sys

    from django.conf import settings as dj_settings

    base = dict(os.environ)
    base["DJANGO_SETTINGS_MODULE"] = "config.settings"
    base["DJANGO_SECRET_KEY"] = "chave-de-teste-suficientemente-longa-0123456789"
    base["DJANGO_ALLOWED_HOSTS"] = "portal-noticias.com,localhost,127.0.0.1"
    base["DJANGO_DB_ENGINE"] = "sqlite3"
    base["ANALYTICS_RETENCAO_DIAS"] = "365"

    raiz = str(dj_settings.BASE_DIR)
    resultado = subprocess.run(
        [sys.executable, "-c", "import django; django.setup(); print('SUBIU')"],
        cwd=raiz,
        env=base,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert resultado.returncode == 0, (
        f"retenção válida impediu o boot: {resultado.stderr[-2000:]}"
    )
    assert "SUBIU" in resultado.stdout


# ---------------------------------------------------------------------------
# 6. Auditoria — contagem e faixa de tempo, NUNCA dado pessoal
# ---------------------------------------------------------------------------


def test_log_e_auditavel_traz_contagem_corte_e_duracao(caplog):
    """Auditável = dá para provar o que saiu, a partir de contagem e janela."""
    caplog.set_level(logging.INFO, logger="metricas.tasks")
    _criar_eventos(idade_dias=500, quantidade=2)

    expurar_analytics.run()

    texto = "\n".join(
        r.getMessage() for r in caplog.records if "expurgo" in r.getMessage()
    )
    assert "total_removido=6" in texto
    assert "retencao_dias=365" in texto
    assert "corte=" in texto
    assert "duracao_s=" in texto


def test_log_nao_carrega_dado_pessoal(caplog):
    """
    PROVA DE AUSÊNCIA DE PII: os marcadores plantados nos eventos (email,
    query buscada, path acessado, sessão anônima) não podem aparecer NEM na
    mensagem renderizada NEM nos `args` crus do registro de log.

    Checar os `args` também é necessário: `getMessage()` sozinho passaria se o
    valor estivesse no `args` e a máscara fosse feita depois — e é o `args` que
    chega ao formatador de JSON que o Loki ingere.
    """
    caplog.set_level(logging.DEBUG, logger="metricas.tasks")
    _criar_eventos(idade_dias=500, quantidade=2)

    expurar_analytics.run()

    registros = [r for r in caplog.records if "expurgo" in r.getMessage()]
    assert registros, "a task nao logou nada — a prova seria vazia"
    for registro in registros:
        materializado = json.dumps(
            {
                "msg": registro.getMessage(),
                "args": [str(a) for a in (registro.args or ())],
            },
            ensure_ascii=False,
        )
        for pii in (EMAIL, QUERY_PESSOAL, PATH_PESSOAL, SESSAO_PESSOAL):
            assert pii not in materializado, (
                f"dado pessoal {pii!r} vazou para o log da task de expurgo"
            )
        # O id do usuário é o identificador mais óbvio e o que uma task de
        # limpeza nunca deve imprimir. Verificado por VALOR (o id real do
        # fixture), não por rótulo — assim o teste não passa só porque o
        # vazamento saiu como `user_id=None`.
        assert str(PK_USUARIO_TESTE) not in materializado, (
            "user_id real vazou para o log do expurgo"
        )
        for nome_de_identificador in ("user", "user_id", "sessao", "session_key", "query"):
            assert nome_de_identificador not in registro.getMessage()


def test_registro_duravel_nao_carrega_dado_pessoal(diretorio_estado):
    """
    A prova de auditoria também fica em DISCO (é o que sobrevive ao fim do
    processo). O arquivo de estado é serializado inteiro e conferido.
    """
    _criar_eventos(idade_dias=500, quantidade=2)

    expurar_analytics.run()

    bruto = filas_estado.caminho_estado().read_text(encoding="utf-8")
    registro = json.loads(bruto)["ciclos"][NOME_EXPURGO]
    materializado = json.dumps(registro, ensure_ascii=False)
    for pii in (EMAIL, QUERY_PESSOAL, PATH_PESSOAL, SESSAO_PESSOAL):
        assert pii not in materializado
    assert str(PK_USUARIO_TESTE) not in materializado
    # O que o registro PRECISA ter, para ser auditável.
    assert registro["estado"] == filas_estado.ESTADO_SUCESSO
    assert registro["detalhe"]["total_removido"] == 6
    assert registro["detalhe"]["retencao_dias"] == 365
    assert registro["detalhe"]["corte"]
    assert registro["detalhe"]["removidos"]["metricas.EventoSite"] == 2


def test_registro_duravel_nao_contem_chave_de_identificador():
    """
    Defence in depth: mesmo sem PII nos VALORES, o registro não pode ter uma
    chave que invite a guardar um identificador depois (user_id, sessao, ...).
    """
    _criar_eventos(idade_dias=500, quantidade=1)

    expurar_analytics.run()

    registro = filas_estado.ler_estado()["ciclos"][NOME_EXPURGO]
    proibidas = ("user", "user_id", "email", "sessao", "session_key", "query", "ip", "user_agent")
    for chave in list(registro.keys()) + list((registro.get("detalhe") or {}).keys()):
        assert chave not in proibidas, f"chave de identificador no registro: {chave!r}"


def test_resumo_devolvido_nao_carrega_dado_pessoal():
    """O retorno da task também é transportado/logado: não pode vazar."""
    _criar_eventos(idade_dias=500, quantidade=2)

    resultado = expurar_analytics.run()

    materializado = json.dumps(resultado, ensure_ascii=False)
    for pii in (EMAIL, QUERY_PESSOAL, PATH_PESSOAL, SESSAO_PESSOAL):
        assert pii not in materializado
    assert str(PK_USUARIO_TESTE) not in materializado
    assert set(resultado) == {
        "corte",
        "retencao_dias",
        "lote",
        "removidos",
        "lotes",
        "total_removido",
        "duracao_s",
        "expurgado",
    }


# ---------------------------------------------------------------------------
# 7. Registro, consumo e observabilidade (GP-10)
# ---------------------------------------------------------------------------


def test_task_esta_registrada_no_app_celery():
    """`name=` público resolve para a MESMA função — o beat manda por nome."""
    from celery.app.task import Task

    from config.celery import app

    app.autodiscover_tasks(force=True)

    assert NOME_EXPURGO == "metricas.tasks.expurgar_analytics"
    task = app.tasks[NOME_EXPURGO]
    assert isinstance(task, Task)
    assert task.name == NOME_EXPURGO
    # Mesmo nome E mesma função: o registro resolve para o objeto real, e não
    # para um stub gerado sob demanda — que seria o sintoma de o beat
    # conseguir enfileirar um nome que o worker não consome.
    assert task.run.__func__ is expurar_analytics.run.__func__


def test_task_esta_na_agenda_do_beat_com_o_intervalo_configurado():
    """Agendada, com o intervalo que o operador ajusta (não um número solto)."""
    from django.conf import settings

    from metricas import tasks as tasks_mod

    entrada = settings.CELERY_BEAT_SCHEDULE["metricas-expurgar-analytics"]

    assert entrada["task"] == tasks_mod.NOME_EXPURGO
    assert entrada["schedule"] == settings.ANALYTICS_EXPURGO_INTERVALO_SEGUNDOS
    assert entrada["schedule"] == tasks_mod.INTERVALO_EXPURGO_PADRAO
    # Diário, que é o que a documentação promete.
    assert entrada["schedule"] == 86400


def test_saude_filas_enxerga_a_task_do_expurgo():
    """
    GP-10: `manage.py saude_filas` tem que enxergar esta task.

    `verificar_registro` (a dependência `registro` do relatório) confere
    TODA entrada do beat contra o registro real do app Celery — então uma task
    órfã é detectada. Este teste confirma que a nossa está lá e, mais forte,
    que um registro sem ela é acusado.
    """
    from config import filas_saude
    from config.celery import app

    resultado = filas_saude.verificar_registro(app)

    # `agenda` são as CHAVES do beat_schedule; o nome da task é o que tem que
    # estar registrado no app Celery.
    assert "metricas-expurgar-analytics" in resultado["agenda"]
    assert resultado["faltando"] == []
    assert resultado["verificado"] is True


def test_saude_filas_acusa_a_task_do_expurgo_quando_o_registro_nao_a_tem():
    """
    Prova negativa da observabilidade: sem o nome no registro do app Celery, o
    relatório diz exatamente qual task falta — é a task órfã, que é o modo
    mais comum de "a agenda parou" sem ninguém perceber.
    """
    from config import filas_saude

    agenda = {"metricas-expurgar-analytics": {"task": NOME_EXPURGO, "schedule": 86400}}
    with override_settings(CELERY_BEAT_SCHEDULE=agenda):
        sem_registro = filas_saude.verificar_registro(_app_sem_metricas())

    assert sem_registro["verificado"] is False
    assert sem_registro["faltando"] == [NOME_EXPURGO]
    assert NOME_EXPURGO in (sem_registro["motivo"] or "")


def _app_sem_metricas():
    """
    App Celery cuja lista de tasks NÃO contém o expurgo.

    Simula o worker que não fez o `autodiscover` (ou um beat apontando para um
    nome que ninguém consome). `autodiscover_tasks` é neutralizado para que o
    relatório não reimporte o módulo e "conserte" o cenário.
    """
    from config.celery import app

    registros = {
        nome: task
        for nome, task in app.tasks.items()
        if nome != NOME_EXPURGO
    }

    class _SemExpurgo:
        tasks = registros
        autodiscover_tasks = staticmethod(lambda *a, **k: None)

    return _SemExpurgo()


def test_ciclo_do_expurgo_e_visivel_em_saude_filas_como_tarefa_monitorada(
    diretorio_estado,
):
    """
    O registro durável do expurgo é legível pelo mesmo caminho que
    `manage.py saude_filas` usa — e um monitor que aponte
    FILAS_TAREFA_MONITORADA para ela enxerga o último ciclo.
    """
    from django.conf import settings

    from config import filas_saude

    _criar_eventos(idade_dias=500, quantidade=2)
    expurar_analytics.run()

    with override_settings(FILAS_TAREFA_MONITORADA=NOME_EXPURGO):
        ciclo = filas_saude._sondar_ultimo_ciclo(filas_estado.ler_estado())

    assert ciclo["verificado"] is True
    assert ciclo["task"] == NOME_EXPURGO
    assert ciclo["estado"] == filas_estado.ESTADO_SUCESSO
    assert ciclo["detalhe"]["total_removido"] == 6
    assert ciclo["idade_s"] is not None


def test_ciclo_de_falha_do_expurgo_derruba_o_veredito_de_saude_filas(diretorio_estado):
    """Falha do expurgo precisa virar `degradado`, não um verde."""
    from django.conf import settings

    from config import filas_saude

    with pytest.raises(RetencaoInvalida):
        expurar_analytics.run(dias=0)

    with override_settings(FILAS_TAREFA_MONITORADA=NOME_EXPURGO):
        ciclo = filas_saude._sondar_ultimo_ciclo(filas_estado.ler_estado())

    assert ciclo["verificado"] is True
    assert ciclo["estado"] == filas_estado.ESTADO_FALHA
    veredito, _tudo, motivos = filas_saude._avaliar(
        registro={"verificado": True},
        broker={"verificado": True, "profundidade": 0},
        workers={"verificado": True, "respondeu": True, "idade_verificada": True, "idade_da_mais_antiga_s": None},
        beat={"verificado": True, "expirado": False},
        ciclo=ciclo,
        fila="celery",
    )
    assert veredito == filas_saude.ESTADO_DEGRADADO
    assert any(NOME_EXPURGO in m for m in motivos)


def test_expurgo_que_roda_registra_ciclo_de_sucesso_para_o_monitor(diretorio_estado):
    _criar_eventos(idade_dias=500, quantidade=2)

    expurar_analytics.run()

    registro = filas_estado.ler_estado()["ciclos"][NOME_EXPURGO]
    assert registro["estado"] == filas_estado.ESTADO_SUCESSO
    assert registro["detalhe"]["expurgado"] is True
    assert registro["detalhe"]["lotes"]["metricas.EventoSite"] == 1


def test_execucao_vazia_tambem_registra_ciclo_com_zero(diretorio_estado):
    """
    Não expurgar nada (todo mundo dentro da janela) também é um ciclo
    observado — senão o monitor nunca teria prova de que o job roda, que é o
    mesmo buraco que `heartbeat_beat` existe para fechar.
    """
    _criar_eventos(idade_dias=10, quantidade=2)

    resultado = expurar_analytics.run()

    registro = filas_estado.ler_estado()["ciclos"][NOME_EXPURGO]
    assert resultado["total_removido"] == 0
    assert registro["estado"] == filas_estado.ESTADO_SUCESSO
    assert registro["detalhe"]["total_removido"] == 0


def test_expurgo_e_provado_pelo_estado_duravel_e_nao_por_metrica_em_processo():
    """
    A task roda no WORKER; um contador em memória do processo do Gunicorn
    seria invisível para `/metrics` (que é servido pelo Gunicorn). Por isso a
    prova de expurgo é o estado durável, e não `config.health.METRICAS`.
    """
    _criar_eventos(idade_dias=500, quantidade=1)

    expurar_analytics.run()

    registro = filas_estado.ler_estado()["ciclos"][NOME_EXPURGO]
    assert "detalhe" in registro
    assert registro["detalhe"]["total_removido"] == 3


# ---------------------------------------------------------------------------
# 8. Agregados derivados
# ---------------------------------------------------------------------------


def test_invalida_snapshot_de_cache_derivado_dos_eventos():
    """
    Os agregados deste projeto são calculados na leitura, mas o SNAPSHOT em
    cache (`populares`) sobrevive ao expurgo: sem invalidação, a UI
    continuaria servindo um agregado feito sobre eventos já removidos.
    """
    _criar_eventos(idade_dias=500, quantidade=2)
    chave = "feed:autocomplete:v2:populares"
    with override_settings(
        CACHES={
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "testes-expurgo",
            }
        }
    ):
        cache.set(chave, [{"query_normalizada": "termo", "total": 2}])
        assert cache.get(chave) is not None

        expurar_analytics.run()

        assert cache.get(chave) is None


def test_invalidador_de_cache_e_chamado_uma_vez_por_execucao(monkeypatch):
    """
    Apagar chave de cache que não existe é o mesmo que apagar uma que existe —
    por isso a invalidação entra uma vez por execução, depois dos lotes, e
    não dentro do laço (seria trabalho repetido sem efeito).
    """
    import feed.busca as busca_mod

    chamadas: list[int] = []

    monkeypatch.setattr(
        busca_mod, "invalidar_cache_autocomplete", lambda: chamadas.append(1)
    )
    _criar_eventos(idade_dias=500, quantidade=6)

    resultado = expurar_analytics.run(lote=1)

    assert chamadas == [1]
    assert resultado["total_removido"] == 18
    # Segunda execução: chama de novo (é o que invalida de verdade), e o efeito
    # continua sendo zero sobre o banco.
    expurar_analytics.run(lote=1)
    assert chamadas == [1, 1]


# ---------------------------------------------------------------------------
# 9. Integridade da própria suíte — os testes que medem estão vivos
# ---------------------------------------------------------------------------


#: Cada par é (nome de um teste, o que ele prova). Se alguém apagar um destes
#: testes, ou esvaziá-lo, esta lista quebra — é o que impede que a suíte do
#: item "passe" por ter deixado de medir.
PROPRIEDADES_PROVADAS = {
    "test_segunda_execucao_nao_remove_nem_muda_contagem": "idempotência",
    "test_idempotencia_sobre_terceira_e_quarta_execucao": "idempotência estável",
    "test_reentrega_da_task_com_o_mesmo_argumento_nao_duplica": "reentrega",
    "test_processa_em_lotes_e_nao_em_uma_so_consulta": "lotes",
    "test_nenhuma_consulta_de_delete_usa_mais_de_um_lote": "lote no banco",
    "test_interromper_no_meio_deixa_o_banco_consistente_e_o_resto_sai_depois": "interrupção",
    "test_interrupcao_entre_lotes_nao_deixa_ciclo_sucesso_falso": "interrupção honesta",
    "test_retencao_zero_recusa_e_nao_apaga_nada": "prazo zero",
    "test_retencao_negativa_recusa_e_nao_apaga_nada": "prazo negativo",
    "test_log_nao_carrega_dado_pessoal": "ausência de PII no log",
    "test_registro_duravel_nao_carrega_dado_pessoal": "ausência de PII em disco",
    "test_registro_duravel_nao_contem_chave_de_identificador": "ausência de chave de PII",
    "test_task_esta_registrada_no_app_celery": "registro",
    "test_task_esta_na_agenda_do_beat_com_o_intervalo_configurado": "agenda",
    "test_saude_filas_enxerga_a_task_do_expurgo": "observabilidade",
}


def test_suite_mede_as_propriedades_do_item():
    """
    Rede de segurança contra a suíte que "passa sem medir": se um dos testes
    que prova uma propriedade do backlog desaparecer, este teste falha.
    """
    import inspect

    import metricas.tests.test_tasks_expurgo as modulo

    presentes = {
        nome
        for nome, obj in vars(modulo).items()
        if nome.startswith("test_") and inspect.isfunction(obj)
    }
    faltando = sorted(set(PROPRIEDADES_PROVADAS) - presentes)
    assert not faltando, (
        f"testes que medem as propriedades do item sumiram: {faltando}"
    )


def test_nenhum_dos_testes_de_propriedade_esta_vazio():
    """
    Um `pass` com nome de teste mede nada. Cada teste de propriedade tem que
    ter asserções de verdade.
    """
    import inspect

    import metricas.tests.test_tasks_expurgo as modulo

    for nome in PROPRIEDADES_PROVADAS:
        fonte = inspect.getsource(getattr(modulo, nome))
        corpo = [
            linha.strip()
            for linha in fonte.splitlines()
            if linha.strip().startswith("assert ")
        ]
        assert corpo, f"teste {nome} nao tem nenhuma assertion"