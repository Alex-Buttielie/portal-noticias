"""
Estado durável em disco das filas do portal (P1-03, WS-06).

POR QUE ESTE MÓDULO EXISTE
-------------------------
"Processo no ar" não prova "agenda rodando": um `celery-beat` que subiu e
não disparou nada, ou que disparou e whose mensagem ninguém consumiu, produz
exatamente o mesmo `ps` de um beat saudável. Por isso o portal grava em
disco, a cada execução, o que de fato aconteceu — e o relatório de saúde
(`config/filas_saude.py`) só diz `ok` quando leu esse registro E mediu o
broker e o worker. Sem registro, o estado é `desconhecido` (nunca `ok`).

O QUE ESTE MÓDULO NÃO É
-----------------------
- Não é um healthcheck: ele não fala com broker nem com worker. Só persiste
  e lê fatos já observados. A sondagem ativa é `config/filas_saude.py`.
- Não é um substituto do banco: guardamos só o suficiente para o diagnóstico
  (o que rodou, quando, com quantas tentativas, se falhou). O detalhe
  histórico da ingestão continua em `RegistroExecucaoIngestao`.

DURABILIDADE E CAMINHO
---------------------
O diretório vem de `PORTAL_FILAS_ESTADO_DIR` (ver `settings.FILAS_ESTADO_DIR`)
e NUNCA fica dentro do repositório: o default é `$XDG_STATE_HOME/portal-noticias`
ou, na ausência dele, um diretório próprio sob o tempdir do sistema. Consequências
deliberadas:

1. O arquivo de estado jamais entra num `git add` por acidente (validação de
   entrega do P1-03 exige isso), e não é preciso editar `.gitignore`.
2. Em DEV/HOMOLOG/PROD o provisionamento (P0-07) tem de apontar
   `PORTAL_FILAS_ESTADO_DIR` para um caminho durável e fora do diretório de
   deploy — por exemplo `/var/lib/portal-noticias`. Sem isso, o diretório
   some a cada reboot e o relatório volta (corretamente) para
   `desconhecido` até o primeiro tick pós-boot. Essa é uma dependência
   humana declarada, não algo que o código resolva sozinho.

CONCORRÊNCIA E ESCRITA PARCIAL
-------------------------------
Vários workers gravam no mesmo arquivo (um por task). Cada gravação é
read-modify-write sob `fcntl.flock` e sai por `os.replace` a partir de um
arquivo temporário no mesmo diretório: um monitor que leia o arquivo nunca
encontra JSON pela metade, e um writer concorrente nunca perde a chave de
outro. Sem `fcntl` (fora do Linux) a proteção some e isso fica registrado no
próprio relatório — degradação explícita, nunca silenciosa.
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import time
from pathlib import Path
from typing import Any

try:  # pragma: no cover - dependente da plataforma
    import fcntl

    _TEM_FLOCK = True
except ImportError:  # pragma: no cover - Windows/sem fcntl
    fcntl = None  # type: ignore[assignment]
    _TEM_FLOCK = False

# Versão do formato. Sobe quando a forma do JSON muda de modo incompatível;
# um arquivo com versão desconhecida é tratado como ILEGÍVEL (e portanto
# `desconhecido`), nunca como um estado válido.
VERSAO_ESTADO = 1

NOME_ARQUIVO = "estado-filas.json"

#: Marcador interno de erro de leitura. Aparece no dict lido quando o arquivo
#: não pôde ser interpretado; `config/filas_saude.py` transforma isso em
#: `desconhecido` com o motivo explícito.
CHAVE_PROBLEMA = "_problema"

#: Limite de tamanho aceito para o arquivo de estado. Um arquivo maior é
#: tratado como ilegível em vez de ser carregado em memória: o conteúdo é
#: gerado só por este módulo, então um arquivo grande demais é corrupção (ou
#: um arquivo outro no lugar), e tratar como ilegível é o que impede um
#: "estado" inventado.
TAMANHO_MAXIMO_BYTES = 512 * 1024

ESTADO_SUCESSO = "sucesso"
ESTADO_FALHA = "falha"


def diretorio_estado() -> Path:
    """
    Diretório do arquivo de estado, sempre FORA do repositório.

    A resolução é feita por chamada (e não no import) porque o valor vem de
    settings — assim `override_settings` funciona nos testes sem recarregar
    o módulo.
    """
    configurado = os.environ.get("PORTAL_FILAS_ESTADO_DIR", "").strip()
    if configurado:
        return Path(configurado).expanduser()
    xdg = os.environ.get("XDG_STATE_HOME", "").strip()
    base = Path(xdg).expanduser() if xdg else Path(tempfile.gettempdir())
    return base / "portal-noticias"


def caminho_estado() -> Path:
    """Caminho absoluto do arquivo de estado de filas."""
    return diretorio_estado() / NOME_ARQUIVO


def _estado_vazio() -> dict[str, Any]:
    return {"versao": VERSAO_ESTADO, "beat": None, "ciclos": {}}


def ler_estado() -> dict[str, Any]:
    """
    Lê o arquivo de estado.

    Devolve o dict com `CHAVE_PROBLEMA` preenchido quando o arquivo não pôde
    ser interpretado (inexistente, ilegível, JSON inválido, versão
    desconhecida, grande demais). Nesses casos NÃO se devolve um estado
    "vazio" indistinguível de "nada rodou ainda": os dois sãoebabalo
    diferentes e o relatório de saúde precisa saber qual é.
    """
    caminho = caminho_estado()
    try:
        bruto = caminho.read_bytes()
    except FileNotFoundError:
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = (
            f"nenhum arquivo de estado em {caminho} (o beat/worker ainda não "
            f"gravou nada neste ambiente)"
        )
        return estado
    except OSError as exc:
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = f"falha de leitura em {caminho}: {exc}"
        return estado

    if len(bruto) > TAMANHO_MAXIMO_BYTES:
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = (
            f"arquivo de estado com {len(bruto)} bytes excede o limite de "
            f"{TAMANHO_MAXIMO_BYTES}; tratado como ilegível"
        )
        return estado

    try:
        dados = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = f"conteudo ilegivel em {caminho}: {exc}"
        return estado

    if not isinstance(dados, dict):
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = (
            f"conteudo inesperado em {caminho}: esperava objeto JSON, veio "
            f"{type(dados).__name__}"
        )
        return estado

    if dados.get("versao") != VERSAO_ESTADO:
        estado = _estado_vazio()
        estado[CHAVE_PROBLEMA] = (
            f"versao de estado desconhecida em {caminho}: "
            f"{dados.get('versao')!r} (esperado {VERSAO_ESTADO})"
        )
        return estado

    # Normaliza: o consumidor não deve ter de lidar com chaves ausentes nem
    # com tipos inesperados escritos por uma versão futura/alterada.
    estado = _estado_vazio()
    estado["beat"] = dados.get("beat") if isinstance(dados.get("beat"), dict) else None
    ciclos = dados.get("ciclos")
    estado["ciclos"] = {
        nome: registro
        for nome, registro in (ciclos or {}).items()
        if isinstance(registro, dict)
    } if isinstance(ciclos, dict) else {}
    return estado


def _escrever(dados: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Grava `dados` atomicamente. Devolve `(gravou, problema)`.

    Nunca levanta: quem chama decide o que fazer com a falha, e o relatório de
    saúde a transforma em `desconhecido`. Uma falha de escrita NUNCA pode
    virar um "sem novidade, tudo bem".
    """
    caminho = caminho_estado()
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, f"nao foi possivel criar {caminho.parent}: {exc}"

    try:
        caminho.touch()
        # flock no arquivo de estado serializa os writers; o `touch` acima
        # garante que ele existe antes de abrir.
        with caminho.open("r+b") as bloqueio:
            if _TEM_FLOCK:
                fcntl.flock(bloqueio.fileno(), fcntl.LOCK_EX)
            try:
                try:
                    atual = json.loads(bloqueio.read().decode("utf-8") or "{}")
                except (UnicodeDecodeError, json.JSONDecodeError):
                    # Base ilegível: NÃO se propaga. Adotar um arquivo
                    # corrompido como estado faria a próxima leitura "dar
                    # certo" com um estado inventado. Reescreve do zero — o
                    # que havia ali era ilegível de todo modo, e o registro
                    # novo é verdadeiro.
                    atual = _estado_vazio()
                if not isinstance(atual, dict) or atual.get("versao") != VERSAO_ESTADO:
                    atual = _estado_vazio()
                atual.update(dados)
                atual["versao"] = VERSAO_ESTADO
                atual["atualizado_em"] = time.time()
                atual.pop(CHAVE_PROBLEMA, None)
                payload = json.dumps(atual, ensure_ascii=False, sort_keys=True, indent=2)
                descritor, temporario = tempfile.mkstemp(
                    dir=str(caminho.parent), prefix=".estado-filas-", suffix=".tmp"
                )
                try:
                    with os.fdopen(descritor, "w", encoding="utf-8") as saida:
                        saida.write(payload)
                        saida.flush()
                        os.fsync(saida.fileno())
                    os.replace(temporario, caminho)
                except BaseException:
                    # Nunca deixa o temporário para trás: um `.tmp` órfão no
                    # diretório de estado seria ruído operacional sem dono.
                    with _silencia_oserror():
                        os.unlink(temporario)
                    raise
            finally:
                if _TEM_FLOCK:
                    fcntl.flock(bloqueio.fileno(), fcntl.LOCK_UN)
    except (OSError, ValueError, TypeError) as exc:
        return False, f"nao foi possivel gravar {caminho}: {exc}"
    return True, None


class _silencia_oserror:
    """Contexto mínimo: ignora `OSError` (usado só na limpeza do temporário)."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, tipo, valor, tb) -> bool:
        return tipo is not None and issubclass(tipo, OSError)


def registrar_beat(
    *,
    task: str,
    task_id: str | None = None,
    tentativa: int = 1,
    max_tentativas: int = 1,
    enfileirado_em: float | None = None,
    agora: float | None = None,
) -> tuple[bool, str | None]:
    """
    Grava a prova de que o beat disparou e um worker consumiu a mensagem.

    `enfileirado_em` (epoch do momento em que a mensagem foi publicada) é
    gravado junto para que a idade do ciclo possa ser lida sem depender do
    mtime do arquivo: mtime pode ser preservado por um `cp -p`/`touch`
    externo e viraria uma idade falsa.
    """
    momento = time.time() if agora is None else float(agora)
    registro = {
        "task": task,
        "task_id": task_id or None,
        "registrado_em": momento,
        "tentativa": int(tentativa),
        "max_tentativas": int(max_tentativas),
        "enfileirado_em": float(enfileirado_em) if enfileirado_em else None,
        "host": socket.gethostname(),
        "pid": os.getpid(),
    }
    gravou, problema = _escrever({"beat": registro})
    if gravou:
        # O heartbeat também é um ciclo: registrá-lo como tal permite
        # monitorar um ambiente em que só o heartbeat está no beat_schedule
        # (ex.: DEV antes do primeiro ciclo de ingestão) sem inventar um
        # "nunca rodou" que não é verdade.
        gravou, problema = registrar_ciclo(
            task=task,
            estado=ESTADO_SUCESSO,
            tentativa=tentativa,
            max_tentativas=max_tentativas,
            enfileirado_em=enfileirado_em,
            agora=momento,
        )
    return gravou, problema


def registrar_ciclo(
    *,
    task: str,
    estado: str,
    tentativa: int = 1,
    max_tentativas: int = 1,
    erro: BaseException | str | None = None,
    detalhe: dict[str, Any] | None = None,
    enfileirado_em: float | None = None,
    agora: float | None = None,
) -> tuple[bool, str | None]:
    """
    Grava o resultado de UMA execução de task.

    `tentativas_observadas` conta execuções consecutivas sem sucesso desde o
    último sucesso — é o número de tentativas observável que o item de
    backlog exige, e é zerado (para 1) por um sucesso, para que o contador
    nunca "carregue" falhas antigas de forma permanente.
    """
    if estado not in (ESTADO_SUCESSO, ESTADO_FALHA):
        raise ValueError(f"estado de ciclo invalido: {estado!r}")

    momento = time.time() if agora is None else float(agora)
    estado_lido = ler_estado()
    if CHAVE_PROBLEMA in estado_lido and not estado_lido.get("ciclos"):
        # Um arquivo ilegível não pode ser usado como base do read-modify-write
        # (senão o próximo writer "aceita" o arquivo corrompido como estado
        # válido). Reescreve a partir do vazio — o que se perdeu foi ilegível
        # de todo modo, e o registro novo é verdadeiro.
        ciclos: dict[str, Any] = {}
    else:
        ciclos = dict(estado_lido.get("ciclos") or {})

    anterior = ciclos.get(task) or {}
    if estado == ESTADO_SUCESSO:
        observadas = 1
    else:
        try:
            observadas = int(anterior.get("tentativas_observadas") or 0) + 1
        except (TypeError, ValueError):
            observadas = 1

    registro = {
        "task": task,
        "estado": estado,
        "tentativa": int(tentativa),
        "max_tentativas": int(max_tentativas),
        "tentativas_observadas": observadas,
        "terminado_em": momento,
        "enfileirado_em": float(enfileirado_em) if enfileirado_em else None,
        "host": socket.gethostname(),
        "pid": os.getpid(),
    }
    if erro is not None:
        texto = f"{type(erro).__name__}: {erro}" if isinstance(erro, BaseException) else str(erro)
        registro["erro"] = texto[:500]
    if detalhe:
        registro["detalhe"] = detalhe

    ciclos[task] = registro
    return _escrever({"ciclos": ciclos})


def idade_de(registro: Any, *, agora: float | None = None) -> float | None:
    """
    Idade (segundos) de um registro do arquivo de estado.

    Usa o carimbo DENTRO do arquivo (`registrado_em`/`terminado_em`); só cai
    para o mtime quando o carimbo não existe. Um carimbo de conteúdo é mais
    forte que mtime: sobrevive a cópia/restauro com metadados preservados,
    onde um mtime antigo fingiria que o ciclo é recente.
    """
    momento = time.time() if agora is None else float(agora)
    if not isinstance(registro, dict):
        return None
    for chave in ("registrado_em", "terminado_em"):
        bruto = registro.get(chave)
        if bruto is None:
            continue
        try:
            return max(0.0, momento - float(bruto))
        except (TypeError, ValueError):
            continue
    return None
