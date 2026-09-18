"""Logger JSON estruturado + contadores em memoria para /metrics."""
from __future__ import annotations

import json
import logging
import sys
import threading
from typing import Dict

_counters: Dict[str, float] = {
    "requisicoes_total": 0,
    "itens_ingeridos_total": 0,
    "custo_llm_usd_total": 0.0,
    "erros_total": 0,
}
_lock = threading.Lock()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "extra_fields"):
            payload.update(getattr(record, "extra_fields"))  # type: ignore[attr-defined]
        return json.dumps(payload, ensure_ascii=False)


def get_logger(name: str = "ingestao") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def inc(contador: str, valor: float = 1.0) -> None:
    with _lock:
        _counters[contador] = _counters.get(contador, 0) + valor


def snapshot() -> Dict[str, float]:
    with _lock:
        return dict(_counters)


def reset_counters() -> None:
    with _lock:
        for k in list(_counters.keys()):
            _counters[k] = 0.0 if isinstance(_counters[k], float) else 0
