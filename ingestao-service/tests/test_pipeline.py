"""Testes do pipeline Frente B — sem rede (fixtures RSS fake, HTTP mockado)."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from app.collectors import rss
from app.collectors.rss import FonteIndisponivelError, buscar_itens, extrair_imagem_url
from app.pipeline import curadoria, dedup
from app.pipeline.curadoria import decidir_status
from app.pipeline.execucao import executar_ingestao
from app.pipeline import execucao as execucao_mod
from app.pipeline.summarizer import SemLLMError, resumir_em_lote
from app.pipeline.texto import extrair_conteudo_completo, limpar_html_para_texto


def cfg_base(**over) -> dict:
    cfg = {
        "categorias_sensiveis": "politica,crime,saude,eleicoes",
        "limiar_fontes_alta_relevancia": 3,
        "dedup_limiar": 0.55,
        "dedup_janela_horas": 24.0,
        "dedup_max_itens": 300,
        "resumo_sim_max": 0.6,
        "resumo_trecho_max": 0.6,
        "cluster_sempre_revisao": True,
        "llm_model": "gpt-4o-mini",
        "llm_base_url": "https://api.fake.local/v1",
        "llm_api_key": "test-key",
        "llm_lote": 10,
        "llm_max_tokens": 220,
        "llm_teto_usd": 5.0,
        "llm_preco_1k": 0.15,
        "llm_timeout": 30,
    }
    cfg.update(over)
    return cfg


def bruto(url="https://g1.globo.com/x", titulo="Titulo valido da noticia com tamanho", **over) -> dict:
    d = {
        "titulo": titulo,
        "url": url,
        "nome_fonte": "G1",
        "summary": "Conteudo original da materia com detalhes suficientes para analise.",
        "content_html": "Conteudo original da materia com detalhes suficientes para analise.",
        "imagem_url": "",
        "categoria": "geral",
        "publicado_em": None,
    }
    d.update(over)
    return d


def fake_resp(content: bytes = b"<rss/>") -> SimpleNamespace:
    return SimpleNamespace(content=content, raise_for_status=lambda: None)


def fake_entry(**over) -> SimpleNamespace:
    d = {
        "title": "Titulo da noticia com tamanho suficiente",
        "link": "https://exemplo.com/noticia-1",
        "summary": "Resumo da noticia em texto simples.",
        "tags": [],
        "published_parsed": None,
    }
    d.update(over)
    return SimpleNamespace(**d)


# ---------- rss.buscar_itens ----------

def test_buscar_itens_normaliza_chaves_congeladas(monkeypatch):
    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: fake_resp())
    monkeypatch.setattr(
        rss.feedparser, "parse", lambda content: SimpleNamespace(entries=[fake_entry()], bozo=False)
    )
    itens = buscar_itens({"nome": "G1", "url": "https://g1.globo.com/rss"})
    assert len(itens) == 1
    assert set(itens[0]) == {"titulo", "url", "nome_fonte", "summary", "content_html", "imagem_url", "categoria", "publicado_em"}
    assert itens[0]["nome_fonte"] == "G1"


def test_buscar_itens_descarta_sem_titulo_ou_url(monkeypatch):
    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: fake_resp())
    entries = [fake_entry(), fake_entry(title=""), fake_entry(link="")]
    monkeypatch.setattr(rss.feedparser, "parse", lambda content: SimpleNamespace(entries=entries, bozo=False))
    assert len(buscar_itens({"nome": "G1", "url": "https://x"})) == 1


def test_buscar_itens_falha_rede_levanta_fonte_indisponivel(monkeypatch):
    import requests as _rq

    def _boom(*a, **k):
        raise _rq.ConnectionError("dns fail")

    monkeypatch.setattr(rss.requests, "get", _boom)
    with pytest.raises(FonteIndisponivelError):
        buscar_itens({"nome": "G1", "url": "https://x"})


def test_buscar_itens_feed_malformado_sem_entries_levanta(monkeypatch):
    monkeypatch.setattr(rss.requests, "get", lambda *a, **k: fake_resp(b"lixo"))
    monkeypatch.setattr(
        rss.feedparser, "parse", lambda content: SimpleNamespace(entries=[], bozo=True, bozo_exception="sax")
    )
    with pytest.raises(FonteIndisponivelError):
        buscar_itens({"nome": "G1", "url": "https://x"})


def test_extrair_imagem_url_enclosure_media_e_img(monkeypatch):
    e1 = SimpleNamespace(enclosures=[{"url": "https://img.com/a.jpg"}], media_content=[], media_thumbnail=[], links=[], summary="")
    assert extrair_imagem_url(e1) == "https://img.com/a.jpg"
    e2 = SimpleNamespace(enclosures=[], media_content=[{"url": "https://img.com/b.png"}], media_thumbnail=[], links=[], summary="")
    assert extrair_imagem_url(e2) == "https://img.com/b.png"
    e3 = SimpleNamespace(enclosures=[], media_content=[], media_thumbnail=[], links=[], summary='<p>x</p><img src="https://img.com/c.gif"/>')
    assert extrair_imagem_url(e3) == "https://img.com/c.gif"
    e4 = SimpleNamespace(enclosures=[], media_content=[], media_thumbnail=[], links=[], summary="sem imagem")
    assert extrair_imagem_url(e4) == ""


# ---------- texto ----------

def test_limpar_html_remove_script_e_tags():
    html = "<script>alert(1)</script><p>Ol&aacute; <b>mundo</b></p>"
    texto = limpar_html_para_texto(html)
    assert "alert" not in texto
    assert texto == "Olá mundo"


def test_extrair_conteudo_prefere_content_e_respeita_teto():
    entry = {"content": [{"value": "<p>COMPLETO longo</p>"}], "summary": "curto", "content_html": ""}
    assert extrair_conteudo_completo(entry) == "COMPLETO longo"
    entry2 = {"summary": "<p>só summary</p>"}
    assert extrair_conteudo_completo(entry2) == "só summary"
    entry3 = {"summary": "x" * 9000}
    assert len(extrair_conteudo_completo(entry3)) == 8000


# ---------- dedup ----------

def test_dedup_similaridade_identicos_alta_e_diferentes_baixa():
    assert dedup.similaridade("Governo anuncia pacote fiscal emergencial", "Governo anuncia pacote fiscal emergencial") == pytest.approx(1.0)
    assert dedup.similaridade("Governo anuncia pacote fiscal emergencial", "Time vence final do campeonato estadual") < 0.3


def test_dedup_agrupa_mesmo_fato_e_separa_fatos_diferentes():
    a = {"titulo": "Chuva forte causa alagamento no centro de São Paulo"}
    b = {"titulo": "Alagamento no centro de Sao Paulo após chuva forte"}
    c = {"titulo": "Prefeitura de São Paulo anuncia novo plano de segurança pública"}
    d = {"titulo": "Prefeitura de São Paulo anuncia novo plano de mobilidade urbana"}
    grupos = dedup.agrupar([a, b, c, d], limiar=0.55)
    tamanhos = sorted(len(g) for g in grupos)
    assert tamanhos == [1, 1, 2]  # a+b juntos; c/d separados (falso-positivo do portal)
    juntos = next(g for g in grupos if len(g) == 2)
    assert {id(x) for x in juntos} == {id(a), id(b)}


# ---------- curadoria ----------

RESUMO_BOM = "Texto autoral que sintetiza o fato com palavras proprias e contexto adicional relevante aqui."


def test_curadoria_sem_resumo_vai_pendente():
    assert decidir_status(bruto(), "", 1, cfg_base()) == "pendente"
    assert decidir_status(bruto(), {"resumo": "  ", "categoria": "geral", "urgente": False}, 1, cfg_base()) == "pendente"


def test_curadoria_copia_ratio_alto_vai_pendente():
    item = bruto(content_html="texto integral copiado literalmente aqui")
    assert decidir_status(item, "texto integral copiado literalmente aqui", 1, cfg_base()) == "pendente"


def test_curadoria_trecho_copiado_verbatim_vai_pendente():
    bruto_longo = (
        "A prefeitura informou nesta manha que o novo corredor de onibus comecara a operar "
        "na proxima segunda-feira com cinco novas linhas expressas atendendo a zona leste "
        "da capital paulista segundo o secretario municipal de transportes em entrevista."
    )
    trecho = "o novo corredor de onibus comecara a operar na proxima segunda-feira com cinco novas linhas expressas"
    item = bruto(content_html=bruto_longo)
    resumo = trecho + " e isso deve reduzir o tempo de viagem dos passageiros."
    assert curadoria._proporcao_copiada(trecho, bruto_longo) > 0.9
    assert decidir_status(item, resumo, 1, cfg_base()) == "pendente"


def test_curadoria_categoria_sensivel_vai_pendente():
    item = bruto(categoria="crime")
    assert decidir_status(item, RESUMO_BOM, 1, cfg_base()) == "pendente"


def test_curadoria_n_fontes_no_limiar_vai_pendente():
    assert decidir_status(bruto(), RESUMO_BOM, 3, cfg_base()) == "pendente"
    assert decidir_status(bruto(), RESUMO_BOM, 2, cfg_base(cluster_sempre_revisao=False, limiar_fontes_alta_relevancia=5)) == "aprovado"


def test_curadoria_cluster_2_itens_exige_revisao_por_padrao():
    assert decidir_status(bruto(), RESUMO_BOM, 2, cfg_base()) == "pendente"
    assert decidir_status(bruto(), RESUMO_BOM, 2, cfg_base(cluster_sempre_revisao=False)) == "aprovado"


def test_curadoria_item_bom_unitario_aprova():
    item = bruto(categoria="esportes")
    res = {"resumo": RESUMO_BOM, "categoria": "esportes", "urgente": False}
    assert decidir_status(item, res, 1, cfg_base()) == "aprovado"


def test_curadoria_regras_novas_titulo_curto_e_maiusculas():
    assert decidir_status(bruto(titulo="Curto"), RESUMO_BOM, 1, cfg_base()) == "pendente"
    assert decidir_status(bruto(titulo="GOVERNO ANUNCIA PACOTE FISCAL EMERGENCIAL AGORA"), RESUMO_BOM, 1, cfg_base(cluster_sempre_revisao=False)) == "pendente"
    assert decidir_status(bruto(url=""), RESUMO_BOM, 1, cfg_base()) == "pendente"


# ---------- summarizer ----------

def _fake_post_ok(captura):
    def _post(url, headers=None, json=None, timeout=None):
        captura["payload"] = json
        captura["headers"] = headers
        n = len(json["messages"][0]["content"].split("Noticia ")) - 1
        objs = [{"id": i, "resumo": f"Resumo autoral numero {i} com conteudo proprio suficiente.", "categoria": "economia", "urgente": False} for i in range(1, 50)]
        body = {"choices": [{"message": {"content": json_lib(objs[: max(n, 1)])}}], "usage": {"total_tokens": 1000}}
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: body)

    return _post


def json_lib(obj) -> str:
    return json.dumps(obj)


def test_summarizer_sem_chave_levanta_sem_llm(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("CATALOGO_NOTICIAS_LLM_API_KEY", raising=False)
    with pytest.raises(SemLLMError):
        resumir_em_lote([bruto()], cfg_base(llm_api_key="", llm_base_url="https://x"))


def test_summarizer_parse_tokens_custo_e_max_tokens(monkeypatch):
    import app.pipeline.summarizer as summ

    captura: dict = {}
    monkeypatch.setattr(summ.requests, "post", _fake_post_ok(captura))
    itens = [bruto(url="https://a/1"), bruto(url="https://a/2")]
    out = resumir_em_lote(itens, cfg_base())
    assert len(out) == 2
    assert set(out[0]) >= {"resumo", "categoria", "urgente"}
    assert out[0]["tokens"] == 500
    assert out[0]["custo_usd"] == pytest.approx(500 / 1000 * 0.15)
    assert captura["payload"]["max_tokens"] == 220 * 2  # por item x lote
    assert captura["headers"]["Authorization"] == "Bearer test-key"


# ---------- execucao ----------

def test_execucao_backoff_registra_erro_sem_derrubar_outras(monkeypatch):
    chamadas = {"n": 0}

    def _busca(fonte):
        chamadas["n"] += 1
        raise FonteIndisponivelError("timeout simulado")

    monkeypatch.setattr(execucao_mod, "buscar_itens", _busca)
    db: dict = {}
    fontes = [
        {"nome": "Quebrada", "url": "https://quebrada/rss"},
        {"nome": "Inativa", "url": "https://x", "ativo": False},
    ]
    out = executar_ingestao(fontes, cfg_base(llm_api_key=""), db)
    assert chamadas["n"] == 2  # 2 tentativas de backoff
    assert "Quebrada" in out["erros_por_fonte"]
    assert "timeout simulado" in out["erros_por_fonte"]["Quebrada"]
    assert out["itens_por_fonte"]["Quebrada"] == 0
    assert "Inativa" not in out["itens_por_fonte"]


def test_execucao_teto_llm_tudo_pendente_sem_http(monkeypatch):
    import app.pipeline.summarizer as summ

    def _boom(*a, **k):
        raise AssertionError("nao deveria chamar HTTP com teto excedido")

    monkeypatch.setattr(summ.requests, "post", _boom)
    monkeypatch.setattr(execucao_mod, "buscar_itens", lambda f: [bruto(url="https://a/1"), bruto(url="https://a/2", titulo="Outro fato totalmente distinto aqui")])
    db: dict = {}
    out = executar_ingestao([{"nome": "G1", "url": "https://x"}], cfg_base(llm_teto_usd=0.0), db)
    assert out["chamadas_llm"] == 0
    assert out["custo_usd"] == 0.0
    assert all(d["status_revisao"] == "pendente" for d in db["itens"])


def test_execucao_fim_a_fim_persiste_itens_clusters_e_execucao(monkeypatch):
    dup1 = bruto(url="https://g1/1", titulo="Chuva forte causa alagamento no centro de São Paulo", nome_fonte="G1")
    dup2 = bruto(url="https://uol/1", titulo="Alagamento no centro de Sao Paulo após chuva forte", nome_fonte="UOL")
    solo = bruto(url="https://g1/2", titulo="Time local vence final do campeonato estadual", nome_fonte="G1", categoria="esportes", summary="resumo proprio", content_html="conteudo proprio")
    monkeypatch.setattr(execucao_mod, "buscar_itens", lambda f: [dup1, dup2, solo] if f["nome"] == "G1" else [dup2])
    monkeypatch.setattr(
        execucao_mod,
        "resumir_em_lote",
        lambda itens, cfg: [{"resumo": f"Resumo autoral proprio {i} sobre o fato noticiado.", "categoria": "esportes" if "Time" in it["titulo"] else "geral", "urgente": False, "tokens": 10, "custo_usd": 0.001} for i, it in enumerate(itens)],
    )
    db: dict = {}
    out = executar_ingestao([{"nome": "G1", "url": "https://g1/rss"}, {"nome": "UOL", "url": "https://uol/rss"}], cfg_base(cluster_sempre_revisao=False), db)
    assert set(out) >= {"id", "executado_em", "itens_por_fonte", "erros_por_fonte", "total_itens_ingeridos", "total_grupos_formados", "total_duplicatas_agrupadas", "chamadas_llm", "tokens_llm", "custo_usd"}
    assert out["total_itens_ingeridos"] == 3
    assert len(db["execucoes"]) == 1
    assert len(db["clusters"]) >= 1  # duplicata agrupada gera cluster
    por_url = {d["url"]: d for d in db["itens"]}
    assert por_url["https://g1/2"]["status_revisao"] == "aprovado"
    assert por_url["https://g1/2"]["cluster_id"] is None
    assert por_url["https://g1/1"]["cluster_id"] == por_url["https://uol/1"]["cluster_id"]


def test_execucao_idempotencia_por_url_nao_reingere(monkeypatch):
    item = bruto(url="https://g1/1")
    monkeypatch.setattr(execucao_mod, "buscar_itens", lambda f: [item])
    monkeypatch.setattr(execucao_mod, "resumir_em_lote", lambda itens, cfg: [{"resumo": RESUMO_BOM, "categoria": "geral", "urgente": False, "tokens": 1, "custo_usd": 0.0} for _ in itens])
    db: dict = {}
    cfg = cfg_base(cluster_sempre_revisao=False)
    executar_ingestao([{"nome": "G1", "url": "https://x"}], cfg, db)
    out2 = executar_ingestao([{"nome": "G1", "url": "https://x"}], cfg, db)
    assert out2["total_itens_ingeridos"] == 0
    assert len(db["itens"]) == 1
