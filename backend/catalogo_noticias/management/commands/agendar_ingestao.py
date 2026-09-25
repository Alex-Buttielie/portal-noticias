"""
Agendador local de ingestão de notícias (management command) — loop sem
Celery/Redis que executa `executar_ingestao()` periodicamente. Motivação e
escopo: implementation-contract.md do run 20260924-2136-ingestao-noticias.

O ambiente nativo (venv + sqlite + locmem, via subir-localhost.sh) nunca
inicia worker/beat Celery — `CELERY_BEAT_SCHEDULE` (config/settings.py) só
vale no docker — e por isso a ingestão parou em 2026-09-21 sem nenhum erro.
Este comando repõe o disparo periódico em dev chamando o MESMO pipeline de
serviço (`catalogo_noticias/services/ingestao.py::executar_ingestao`):
nenhuma lógica de busca/dedup/resumo é duplicada aqui. Em produção/docker o
agendamento continua sendo do Celery beat; este comando é opt-in do modo
nativo (subir-localhost.sh) e nunca é iniciado pelo startup do Django nem
pelo docker-compose.

Uso:
    python manage.py agendar_ingestao                              # primeira rodada imediata, depois a cada intervalo
    python manage.py agendar_ingestao --rodadas 1                  # uma rodada e sai (código 0)
    python manage.py agendar_ingestao --intervalo-segundos 60      # intervalo customizado
    python manage.py agendar_ingestao --intervalo-segundos 1 --rodadas 2  # teste

Sinais (Finding 1 da revisão): o 1º SIGINT/SIGTERM encerra graciosamente
(fim da rodada em curso); o 2º sinal é ESCALONAMENTO e sai na hora — é o
que o `--stop` do subir-localhost.sh usa depois de esperar a parada graciosa.
Falha recorrente (Finding 2): a partir de FALHAS_CONSECUTIVAS_PARA_ALERTAR
rodadas seguidas falhando, o log sobe para ERROR com mensagem própria.
"""

import logging
import os
import signal
import sys
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from catalogo_noticias.services.ingestao import executar_ingestao

logger = logging.getLogger(__name__)

# Finding 2 da revisão: com `executar_ingestao()` falhando sempre (banco
# travado, provider de resumo quebrado, DNS), o loop repetia a mesma falha a
# cada intervalo, indefinidamente, e o sintoma era exatamente o que esta run
# existe para eliminar: "ingestão parada e ninguém sabe". A partir deste
# número de falhas SEGUIDAS o log sobe para ERROR com mensagem própria. O
# isolamento de falha NÃO muda: o loop continua tentando a próxima rodada.
FALHAS_CONSECUTIVAS_PARA_ALERTAR = 3


class Command(BaseCommand):
    help = (
        "Agendador de ingestão de notícias sem Celery/Redis: roda "
        "executar_ingestao() em loop (primeira rodada imediata, depois a cada "
        "--intervalo-segundos; padrão CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS "
        "* 60 = 15 min). Exceção de uma rodada é logada com traceback e o loop "
        "segue para a próxima; a partir de 3 falhas seguidas o log reporta em "
        "ERROR que a ingestão está parada de fato. SIGINT/SIGTERM encerram "
        "graciosamente (fim da rodada atual); um 2º sinal encerra na hora. "
        "--rodadas N limita o total de rodadas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--intervalo-segundos",
            type=int,
            default=None,
            help=(
                "Segundos entre o fim de uma rodada e o início da próxima "
                "(padrão: CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60)."
            ),
        )
        parser.add_argument(
            "--rodadas",
            type=int,
            default=None,
            help=(
                "Número máximo de rodadas (padrão: infinitas). Deve ser >= 0; "
                "com 0 nada é executado (o agendador só registra o início/fim)."
            ),
        )

    def handle(self, *args, **opcoes):
        intervalo = opcoes["intervalo_segundos"]
        if intervalo is None:
            # Mesmo valor do beat (config/settings.py CELERY_BEAT_SCHEDULE):
            # uma única fonte de verdade para o intervalo, sem duplicar config.
            intervalo = settings.CATALOGO_NOTICIAS_INTERVALO_INGESTAO_MINUTOS * 60
        if intervalo <= 0:
            raise CommandError(f"--intervalo-segundos deve ser positivo (recebido {intervalo}).")
        total_rodadas = opcoes["rodadas"]
        # Finding 8 da revisão: simetria com a validação do intervalo. Antes,
        # `--rodadas 0`/`-1` saíam em silêncio com "0 rodada(s)", dando a
        # impressão de que o agendador rodou. Negativo é erro de uso; zero é
        # legítimo (rodar nada) mas vira um aviso explícito no log.
        if total_rodadas is not None and total_rodadas < 0:
            raise CommandError(
                f"--rodadas não pode ser negativo (recebido {total_rodadas})."
            )
        rotulo_rodadas = str(total_rodadas) if total_rodadas is not None else "infinitas"
        if total_rodadas == 0:
            logger.warning(
                "--rodadas 0: nenhuma rodada será executada — o agendador vai só "
                "iniciar e finalizar (use um número >= 1 para executar ingestão)."
            )

        # Encerramento gracioso (critério de aceite 5): SIGINT/SIGTERM apenas
        # marcam a parada — a rodada em curso TERMINA normalmente (o
        # `RegistroExecucaoIngestao` só recebe os totais no `registro.save()`
        # final, no fim da rodada) e nenhuma nova rodada é agendada. Sem
        # handler próprio, o SIGTERM mataria o processo no meio da ingestão
        # sem limpeza e o SIGINT levantaria KeyboardInterrupt com traceback.
        #
        # Finding 1 da revisão: o 1º sinal sozinho deixava o `--stop` sem saída
        # previsível (o segundo sinal era engolido e só `kill -9` encerrava),
        # e o `--stop` removia o pid file antes de o processo sair — abrindo a
        # janela de duas instâncias concorrentes. O 2º sinal é o escalonamento:
        # encerra na hora, com log, para o `--stop` ter um desfecho definido.
        parada_solicitada = None

        def _marcar_parada(signum, _frame):
            nonlocal parada_solicitada
            if parada_solicitada is None:
                parada_solicitada = signal.Signals(signum).name
                logger.info(
                    "Sinal %s recebido — encerrando após a rodada atual",
                    parada_solicitada,
                )
                return
            # Finding 1 (2ª passada da revisão): a redação anterior ("a rodada
            # em curso foi abandonada e NÃO foi registrada") superestimava a
            # atomicidade — `executar_ingestao` NÃO é atômica por rodada. A
            # persistência é POR GRUPO (`@transaction.atomic` em
            # `_persistir_grupo`/`_persistir_grupo_mesclado`) e o
            # `RegistroExecucaoIngestao` só é fechado no `registro.save()`
            # final. Logo: abortar no meio NÃO corrompe nada e os grupos já
            # confirmados permanecem; o que fica de fora é o fechamento do
            # registro da rodada (que permanece com
            # `total_itens_ingeridos=0`, apesar das métricas parciais já
            # gravadas por `_atualizar_metricas_execucao`) e o
            # `confirmar_validadores` das fontes processadas (a próxima rodada
            # rebaixa o XML em vez de perder lote).
            logger.error(
                "Segundo sinal %s — encerrando IMEDIATAMENTE (escalonamento; a "
                "rodada em curso foi ABORTADA no meio: nada fica corrompido e os "
                "grupos já confirmados permanecem, porque a persistência é por "
                "grupo (@transaction.atomic em _persistir_grupo) — o que NÃO "
                "acontece é o fechamento do registro da rodada, que fica com "
                "total_itens_ingeridos=0)",
                signal.Signals(signum).name,
            )
            # Sai sem desenrolar a pilha: um `raise` aqui seria engolido por
            # qualquer `except` do caminho do pipeline e devolveria o processo
            # à vida — exatamente o que o `--stop` precisa evitar. Equivale a um
            # `kill -9` deliberado. É seguro quanto aos dados PELO MESMO motivo
            # do sinal: cada grupo é gravado numa transação própria e o sqlite
            # faz rollback do grupo em andamento; o que se perde é o registro
            # da rodada (ver a mensagem acima).
            for _stream in (sys.stdout, sys.stderr):
                try:
                    _stream.flush()
                except Exception:  # pragma: no cover - stdout fechado
                    pass
            logging.shutdown()
            os._exit(128 + int(signum))

        sinal_int_anterior = signal.signal(signal.SIGINT, _marcar_parada)
        sinal_term_anterior = signal.signal(signal.SIGTERM, _marcar_parada)

        def _dormir(segundos):
            # Dorme em fatias de 1s checando a parada: resposta de encerramento
            # em ~1s sem busy-wait e sem nenhuma consulta fora das rodadas
            # (restricao de performance do contrato).
            restante = segundos
            while restante > 0 and parada_solicitada is None:
                passo = min(1, restante)
                time.sleep(passo)
                restante -= passo

        rodada = 0
        falhas_consecutivas = 0
        logger.info(
            "Agendador de ingestão iniciado (intervalo=%ss, rodadas=%s) — primeira rodada imediata",
            intervalo,
            rotulo_rodadas,
        )
        try:
            while total_rodadas is None or rodada < total_rodadas:
                if parada_solicitada is not None:
                    break
                rodada += 1
                # Conexões de banco em processo de longa vida: mesmo padrão de
                # _executar_ingestao_em_background (robos_views.py) —
                # close_old_connections() no início e no fim de cada rodada
                # evita reutilizar conexão stale entre rodadas.
                close_old_connections()
                logger.info("Rodada %d/%s: iniciando ingestão", rodada, rotulo_rodadas)
                try:
                    registro = executar_ingestao()
                    # Finding 3 da revisão: o log de sucesso fica DENTRO do
                    # try — antes ele vivia no bloco `else`, fora do
                    # `except`/`finally`, e uma exceção ao ler
                    # `registro.id`/`erros_por_fonte` (renomeação de campo,
                    # retorno inesperado, erro de formatação do logging)
                    # escapava do `while` e matava o processo — contradizendo a
                    # garantia "nunca mata o processo" do contrato. A garantia
                    # agora vale para a rodada INTEIRA, não só para a chamada do
                    # pipeline.
                    logger.info(
                        "Rodada %d/%s concluída (registro_id=%s, %d itens, %d erro(s) de fonte)",
                        rodada,
                        rotulo_rodadas,
                        registro.id,
                        registro.total_itens_ingeridos,
                        len(registro.erros_por_fonte),
                    )
                except Exception:
                    # Isolamento de falha (critério de aceite 2): exceção de UMA
                    # rodada é logada com traceback e o loop segue para a próxima
                    # — nunca mata o processo (mesmo padrão de
                    # _executar_ingestao_em_background em robos_views.py).
                    falhas_consecutivas += 1
                    logger.exception(
                        "Rodada %d/%s: falhou — seguindo para a próxima rodada",
                        rodada,
                        rotulo_rodadas,
                    )
                    if falhas_consecutivas >= FALHAS_CONSECUTIVAS_PARA_ALERTAR:
                        # Finding 2 da revisão: falha repetida vira sinal
                        # explícito em vez de ruído recorrente no log.
                        logger.error(
                            "ALERTA: %d rodadas consecutivas falharam (a última foi a "
                            "rodada %d/%s) — a INGESTÃO ESTÁ PARADA de fato, não é só "
                            "uma falha isolada. Ver o log desta execução (com o "
                            "subir-localhost.sh é /tmp/brd-agendador.log). O loop "
                            "continua tentando a cada %ss; se a causa for código/config, "
                            "rode uma ingestão manualmente para ver o traceback.",
                            falhas_consecutivas,
                            rodada,
                            rotulo_rodadas,
                            intervalo,
                        )
                else:
                    # Só reseta se a rodada INTEIRA deu certo (pipeline + log).
                    if falhas_consecutivas:
                        logger.info(
                            "Rodada %d/%s voltou ao normal — contador de falhas "
                            "consecutivas zerado (era %d)",
                            rodada,
                            rotulo_rodadas,
                            falhas_consecutivas,
                        )
                    falhas_consecutivas = 0
                finally:
                    close_old_connections()

                # Dorme apenas se houver próxima rodada e nenhum sinal pendente.
                if (
                    total_rodadas is None or rodada < total_rodadas
                ) and parada_solicitada is None:
                    _dormir(intervalo)
        finally:
            # Restaura os handlers originais: o comando não deixa efeito
            # colateral no processo (importante para call_command em testes).
            signal.signal(signal.SIGINT, sinal_int_anterior)
            signal.signal(signal.SIGTERM, sinal_term_anterior)

        if parada_solicitada is not None:
            logger.info(
                "Agendador encerrado por %s (rodadas executadas=%d)",
                parada_solicitada,
                rodada,
            )
        else:
            logger.info("Agendador encerrado (rodadas executadas=%d)", rodada)
        self.stdout.write(self.style.SUCCESS(f"Agendador finalizado ({rodada} rodada(s))."))
