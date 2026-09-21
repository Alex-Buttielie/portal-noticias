"""Orquestracao do ciclo de ingestao — Frente B.

``executar_ingestao(fontes, cfg, db) -> dict`` (schema ``Execucao`` da
frente A: id, executado_em, itens_por_fonte, erros_por_fonte,
total_itens_ingeridos, total_grupos_formados, total_duplicatas_agrupadas,
chamadas_llm, tokens_llm, custo_usd).

- ``fontes``: list[dict] {nome (ou nome_fonte), url (ou url_feed),
  ativo=True, categoria_padrao=""}. Fontes inativas sao puladas.
- ``cfg``: dict (ou objeto) com as chaves do ``Config`` da frente A
  (dedup_limiar/janela_horas/max_itens, resumo_sim_max/trecho_max,
  categorias_sensiveis, limiar_fontes_alta_relevancia,
  cluster_sempre_revisao, llm_*). A chave LLM vem em ``llm_api_key``
  ou das envs LLM_API_KEY/CATALOGO_NOTICIAS_LLM_API_KEY.
- ``db``: qualquer objeto com colecoes "itens", "clusters" e "execucoes"
  — dict de listas (testes/fakes), objeto com atributos, ou Database
  pymongo (``db["itens"]``). Leitura via ``find()`` quando disponivel,
  escrita via ``insert_one()`` quando disponivel, senao ``append``.

Fluxo: busca por fonte com backoff (2 tentativas; falha registra em
erros_por_fonte sem derrubar as demais) -> idempotencia por URL ->
janela recente (persistidos na janela, cap max, combinados no agrupar)
-> resume em lotes com teto diario (colecao execucoes de hoje; sem LLM
ou teto excedido -> tudo pendente) -> persiste itens+clusters+execucao
-> contadores de ``app.observability`` se existir (import blindado).
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any

from app.collectors.rss import FonteIndisponivelError, buscar_itens
from app.pipeline.curadoria import decidir_status
from app.pipeline.dedup import agrupar
from app.pipeline.summarizer import LLMError, SemLLMError, resumir_em_lote

logger = logging.getLogger("ingestao.pipeline.execucao")

TENTATIVAS_POR_FONTE = 2
BACKOFF_ESPERA_SEGUNDOS = 0.2


def _cfg(cfg: Any, nome: str, default: Any) -> Any:
    if isinstance(cfg, dict):
        return cfg.get(nome, default)
    return getattr(cfg, nome, default)


def _colecao(db: Any, nome: str) -> Any:
    if isinstance(db, dict):
        return db.setdefault(nome, [])
    if hasattr(db, "__getitem__"):
        try:
            return db[nome]
        except Exception:  # noqa: BLE001 — tenta atributo em seguida
            pass
    if hasattr(db, nome):
        return getattr(db, nome)
    if callable(getattr(db, "get_collection", None)):
        return db.get_collection(nome)
    raise TypeError(f"db nao expoe a colecao '{nome}' (dict, atributo ou db[nome]).")


def _todos_docs(col: Any) -> list[dict]:
    if isinstance(col, list):
        return list(col)
    if isinstance(col, dict):
        return list(col.values())
    find = getattr(col, "find", None)
    if callable(find):
        try:
            return list(find({}))
        except TypeError:
            return list(find())
    return list(col)


def _inserir(col: Any, doc: dict) -> None:
    insert_one = getattr(col, "insert_one", None)
    if callable(insert_one):
        insert_one(dict(doc))
        return
    if isinstance(col, list):
        col.append(dict(doc))
        return
    if isinstance(col, dict):
        col[doc.get("id") or doc.get("url") or str(len(col))] = dict(doc)
        return
    append = getattr(col, "append", None)
    if callable(append):
        append(dict(doc))
        return
    raise TypeError("Colecao nao suporta insert_one nem append.")


def _agora_utc() -> datetime:
    return datetime.now(dt_timezone.utc)


def _parse_data(valor: Any) -> datetime | None:
    if valor is None or valor == "":
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=dt_timezone.utc)
    if isinstance(valor, str):
        try:
            dt = datetime.fromisoformat(valor)
            return dt if dt.tzinfo else dt.replace(tzinfo=dt_timezone.utc)
        except ValueError:
            return None
    return None


def _data_do_doc(doc: dict) -> datetime | None:
    return _parse_data(doc.get("publicado_em")) or _parse_data(doc.get("ingerido_em")) or _parse_data(
        doc.get("timestamp")
    )


def _gasto_llm_hoje_usd(col_execucoes: Any) -> float:
    hoje = _agora_utc().date()
    total = 0.0
    for doc in _todos_docs(col_execucoes):
        if _parse_data(doc.get("executado_em")) and _parse_data(doc.get("executado_em")).date() == hoje:
            try:
                total += float(doc.get("custo_usd") or 0.0)
            except (TypeError, ValueError):
                continue
    return total


def _buscar_com_backoff(fonte: dict) -> list[dict]:
    """Busca com 2 tentativas; levanta na ultima falha (chamador registra)."""
    ultimo_erro: Exception | None = None
    nome = str(fonte.get("nome") or fonte.get("nome_fonte") or "fonte")
    for tentativa in range(1, TENTATIVAS_POR_FONTE + 1):
        try:
            return buscar_itens(fonte)
        except FonteIndisponivelError as exc:
            ultimo_erro = exc
        except Exception as exc:  # noqa: BLE001 — erro inesperado de UMA fonte nao derruba as demais
            ultimo_erro = exc
        if tentativa < TENTATIVAS_POR_FONTE:
            time.sleep(BACKOFF_ESPERA_SEGUNDOS)
    logger.error("Fonte '%s' indisponivel apos %d tentativa(s): %s", nome, TENTATIVAS_POR_FONTE, ultimo_erro)
    raise ultimo_erro  # type: ignore[misc]


def _para_pseudo(doc: dict) -> dict:
    """Persistido recente -> dict comparavel no agrupar (marcado)."""
    return {
        "titulo": doc.get("titulo") or "",
        "url": doc.get("url") or doc.get("url_fonte_original") or "",
        "nome_fonte": doc.get("nome_fonte") or "",
        "summary": doc.get("resumo") or "",
        "content_html": "",
        "imagem_url": doc.get("imagem_url") or "",
        "categoria": doc.get("categoria") or "",
        "publicado_em": _data_do_doc(doc),
        "_persistido": True,
    }


def _inc_observability(contador: str, valor: float) -> None:
    try:
        from app.observability import inc  # type: ignore[import]

        inc(contador, valor)
    except Exception:  # noqa: BLE001 — observabilidade nunca quebra a ingestao
        pass


def executar_ingestao(fontes: list[dict], cfg: dict | Any, db: Any) -> dict:
    """Executa um ciclo completo e devolve/persiste o dict ``Execucao``."""
    col_itens = _colecao(db, "itens")
    col_clusters = _colecao(db, "clusters")
    col_execucoes = _colecao(db, "execucoes")

    limiar = float(_cfg(cfg, "dedup_limiar", 0.55))
    janela_horas = float(_cfg(cfg, "dedup_janela_horas", 24.0))
    max_itens = int(_cfg(cfg, "dedup_max_itens", 300))
    lote_llm = max(1, int(_cfg(cfg, "llm_lote", 10) or 10))
    teto_usd = float(_cfg(cfg, "llm_teto_usd", 5.0))

    itens_por_fonte: dict[str, int] = {}
    erros_por_fonte: dict[str, str] = {}
    brutos_novos: list[dict] = []

    for fonte in fontes or []:
        if isinstance(fonte, dict) and fonte.get("ativo") is False:
            continue
        nome = str(
            (fonte.get("nome") or fonte.get("nome_fonte") if isinstance(fonte, dict) else getattr(fonte, "nome", None) or getattr(fonte, "nome_fonte", None) or "fonte")
            or "fonte"
        )
        try:
            itens = _buscar_com_backoff(fonte)
        except Exception as exc:  # noqa: BLE001 — registrado, segue p/ proximas fontes
            erros_por_fonte[nome] = str(exc)
            itens_por_fonte[nome] = 0
            continue
        validos = [it for it in itens if (it.get("titulo") or "").strip() and str(it.get("url") or "").startswith("http")]
        itens_por_fonte[nome] = len(validos)
        brutos_novos.extend(validos)

    # Idempotencia por URL (uma passada, sem N+1): contra o banco E dentro
    # do proprio lote (duas fontes podem trazer a mesma URL no ciclo).
    urls_conhecidas = {
        str(d.get("url") or d.get("url_fonte_original") or "")
        for d in _todos_docs(col_itens)
    }
    novos: list[dict] = []
    for it in brutos_novos:
        url = str(it.get("url"))
        if url in urls_conhecidas:
            continue
        urls_conhecidas.add(url)
        novos.append(it)

    # Janela recente: persistidos com data na janela (sem data entram —
    # nunca descartamos sinal de dedup por falta de data), mais novos
    # primeiro, teto max_itens.
    corte = _agora_utc() - timedelta(hours=janela_horas)
    recentes = [d for d in _todos_docs(col_itens)]
    recentes.sort(key=lambda d: (_data_do_doc(d) is not None, _data_do_doc(d)), reverse=True)
    pseudo: list[dict] = []
    for doc in recentes:
        data = _data_do_doc(doc)
        if data is not None and data < corte:
            continue
        pseudo.append(_para_pseudo(doc))
        if len(pseudo) >= max_itens:
            break

    grupos = agrupar(novos + pseudo, limiar=limiar) if (novos or pseudo) else []
    processados: list[tuple[list[dict], list[dict]]] = []  # (novos_do_grupo, grupo_completo)
    todos_novos_ordenados: list[dict] = []
    for grupo in grupos:
        novos_do_grupo = [it for it in grupo if not it.get("_persistido")]
        if not novos_do_grupo:
            continue  # so persistidos — nada novo a fazer
        processados.append((novos_do_grupo, grupo))
        todos_novos_ordenados.extend(novos_do_grupo)

    # Resumo em lotes com teto diario (gasto de hoje + acumulado NESTA execucao).
    resultado_por_url: dict[str, dict] = {}
    chamadas_llm, tokens_llm, custo_usd = 0, 0, 0.0
    teto_excedido = False
    if todos_novos_ordenados:
        gasto_base = _gasto_llm_hoje_usd(col_execucoes)
        for inicio in range(0, len(todos_novos_ordenados), lote_llm):
            lote = todos_novos_ordenados[inicio : inicio + lote_llm]
            if not teto_excedido and (gasto_base + custo_usd) >= teto_usd:
                teto_excedido = True
                logger.warning(
                    "Teto diario LLM (%.4f USD) atingido (gasto %.4f) — restante sem resumo (pendente).",
                    teto_usd,
                    gasto_base + custo_usd,
                )
            if teto_excedido:
                for it in lote:
                    resultado_por_url[str(it.get("url"))] = {"resumo": "", "categoria": it.get("categoria") or "", "urgente": False}
                continue
            try:
                resultados = resumir_em_lote(lote, cfg)
                if len(resultados) != len(lote):
                    raise LLMError(f"LLM devolveu {len(resultados)} resultados p/ {len(lote)} itens.")
            except SemLLMError:
                logger.warning("Sem chave LLM — todos os itens desta execucao vao para revisao (pendente).")
                for it in todos_novos_ordenados:
                    resultado_por_url[str(it.get("url"))] = {
                        "resumo": "",
                        "categoria": it.get("categoria") or "",
                        "urgente": False,
                    }
                break
            except Exception as exc:  # noqa: BLE001 — fallback por lote, igual ao portal
                logger.error("Falha do LLM p/ lote de %d item(ns): %s", len(lote), exc)
                for it in lote:
                    resultado_por_url[str(it.get("url"))] = {"resumo": "", "categoria": it.get("categoria") or "", "urgente": False}
                continue
            chamadas_llm += 1
            for it, res in zip(lote, resultados):
                if res.get("tokens"):
                    try:
                        tokens_llm += int(res["tokens"])
                    except (TypeError, ValueError):
                        pass
                try:
                    custo_usd += float(res.get("custo_usd") or 0.0)
                except (TypeError, ValueError):
                    pass
                resultado_por_url[str(it.get("url"))] = res

    # Persiste clusters + itens com status de curadoria.
    agora = _agora_utc()
    for novos_do_grupo, grupo in processados:
        n_grupo = len(grupo)  # cobertura total (janela inclusa) conta p/ relevancia
        cluster_id = None
        if len(grupo) > 1:
            cluster_id = uuid.uuid4().hex
            primeira_categoria = ""
            for membro in grupo:
                url_m = str(membro.get("url"))
                res_m = resultado_por_url.get(url_m)
                if res_m and res_m.get("categoria"):
                    primeira_categoria = str(res_m["categoria"])
                    break
            if not primeira_categoria:
                primeira_categoria = str(grupo[0].get("categoria") or "")
            _inserir(
                col_clusters,
                {
                    "id": cluster_id,
                    "titulo": grupo[0].get("titulo") or "",
                    "categoria_dominante": primeira_categoria,
                    "fontes": sorted({str(m.get("nome_fonte") or "") for m in grupo if m.get("nome_fonte")}),
                    "n_itens": len(grupo),
                    "criado_em": agora.isoformat(),
                },
            )
        for item in novos_do_grupo:
            res = resultado_por_url.get(str(item.get("url")), {"resumo": "", "categoria": item.get("categoria") or "", "urgente": False})
            status = decidir_status(item, res, n_grupo, cfg)
            publicado = item.get("publicado_em")
            if isinstance(publicado, datetime):
                publicado_iso = publicado.isoformat()
            else:
                publicado_iso = _parse_data(publicado).isoformat() if _parse_data(publicado) else None
            _inserir(
                col_itens,
                {
                    "id": uuid.uuid4().hex,
                    "titulo": item.get("titulo") or "",
                    "resumo": res.get("resumo") or "",
                    "categoria": res.get("categoria") or item.get("categoria") or "",
                    "urgente": bool(res.get("urgente", False)),
                    "nome_fonte": item.get("nome_fonte") or "",
                    "url_fonte_original": str(item.get("url")),
                    "url": str(item.get("url")),
                    "imagem_url": item.get("imagem_url") or "",
                    "publicado_em": publicado_iso,
                    "ingerido_em": agora.isoformat(),
                    "status_revisao": status,
                    "status": status,
                    "cluster_id": cluster_id,
                },
            )

    total_itens = len(todos_novos_ordenados)
    total_grupos = len(processados)
    execucao: dict = {
        "id": uuid.uuid4().hex,
        "executado_em": agora.isoformat(),
        "itens_por_fonte": itens_por_fonte,
        "erros_por_fonte": erros_por_fonte,
        "total_itens_ingeridos": total_itens,
        "total_grupos_formados": total_grupos,
        "total_duplicatas_agrupadas": max(total_itens - total_grupos, 0),
        "chamadas_llm": chamadas_llm,
        "tokens_llm": tokens_llm,
        "custo_usd": round(custo_usd, 6),
    }
    _inserir(col_execucoes, execucao)

    _inc_observability("itens_ingeridos_total", float(total_itens))
    _inc_observability("custo_llm_usd_total", float(custo_usd))
    if erros_por_fonte:
        _inc_observability("erros_total", float(len(erros_por_fonte)))

    logger.info(
        "Ingestao concluida: %d itens, %d grupos, %d chamadas LLM, %d fonte(s) com erro.",
        total_itens,
        total_grupos,
        chamadas_llm,
        len(erros_por_fonte),
    )
    return execucao
