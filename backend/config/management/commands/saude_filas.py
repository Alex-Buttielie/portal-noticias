"""
`manage.py saude_filas` — relatório consultável da saúde das filas (P1-03).

Este comando é a interface entre o código e o monitor do ambiente. Ele
NÃO decide se o ambiente está saudável: ele mede o que dá para medir e
devolve `desconhecido` sempre que não conseguiu verificar uma dependência.
Quem Monitora (P0-07, dependência humana de provisionamento) decide o que
fazer com cada um dos três estados.

CÓDIGO DE SAÍDA (contrato, para o monitor não precisar parsear texto)
---------------------------------------------------------------------
- 0 = `ok`           — tudo verificado e sem problema.
- 1 = `degradado`    — medido e com problema (fila funda, beat velho,
                       último ciclo em falha...).
- 3 = `desconhecido` — não foi possível verificar. Deliberadamente
                       DIFERENTE de 0: um monitor genérico que trata
                       "não sei" como sucesso é o falso verde que este
                       item existe para matar. (2 fica reservado para
                       erro de uso/argparse do próprio Django.)
"""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from config import filas_saude

SAIDA_OK = 0
SAIDA_DEGRADADO = 1
SAIDA_DESCONHECIDO = 3

CORES = {
    filas_saude.ESTADO_OK: "SUCCESS",
    filas_saude.ESTADO_DEGRADADO: "WARNING",
    filas_saude.ESTADO_DESCONHECIDO: "WARNING",
}

SAIDA_POR_ESTADO = {
    filas_saude.ESTADO_OK: SAIDA_OK,
    filas_saude.ESTADO_DEGRADADO: SAIDA_DEGRADADO,
    filas_saude.ESTADO_DESCONHECIDO: SAIDA_DESCONHECIDO,
}


class Command(BaseCommand):
    help = (
        "Mede e imprime a saúde das filas do portal (broker, worker, "
        "heartbeat do beat e último ciclo monitorado). Sai com 0 (ok), "
        "1 (degradado) ou 3 (desconhecido — não foi possível verificar)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json",
            help="Imprime o relatório completo em JSON (uma linha) em vez do resumo legível.",
        )
        parser.add_argument(
            "--fila",
            dest="fila",
            default=None,
            help="Nome da fila a medir (padrão: FILAS_NOME_FILA).",
        )
        parser.add_argument(
            "--ignorar-saida",
            action="store_true",
            dest="ignorar_saida",
            help="Sempre sai com 0 (para inspeção manual; o relatório continua honesto).",
        )

    def handle(self, *args, **options):
        relatorio = filas_saude.relatorio(fila=options.get("fila"))
        estado = relatorio["estado"]
        if estado not in SAIDA_POR_ESTADO:  # pragma: no cover - trava de seguranca
            raise CommandError(f"estado de saude inesperado: {estado!r}")

        if options.get("json"):
            self.stdout.write(json.dumps(relatorio, ensure_ascii=False, sort_keys=True))
        else:
            self._imprimir_legivel(relatorio)

        if not options.get("ignorar_saida"):
            raise SystemExit(SAIDA_POR_ESTADO[estado])

    # -- apresentação ------------------------------------------------------

    def _imprimir_legivel(self, relatorio):
        estilo = getattr(self.style, CORES[relatorio["estado"]])
        self.stdout.write(
            estilo(f"estado={relatorio['estado']}  verificado={relatorio['verificado']}")
        )
        self.stdout.write(
            f"modo_execucao={relatorio['modo_execucao']}  fila={relatorio['fila']!r}"
        )
        self.stdout.write(f"arquivo_estado={relatorio['arquivo_estado']}")

        partes = relatorio["dependencias"]

        registro = partes["registro"]
        self.stdout.write(
            self._linha(
                "registro",
                registro["verificado"],
                "total_registradas={} faltando={}".format(
                    registro.get("total_registradas"),
                    registro.get("faltando"),
                ),
                registro.get("motivo"),
            )
        )

        broker = partes["broker"]
        self.stdout.write(
            self._linha(
                "broker",
                broker["verificado"],
                f"profundidade={broker['profundidade']}",
                broker.get("motivo"),
            )
        )

        workers = partes["workers"]
        self.stdout.write(
            self._linha(
                "workers",
                workers["verificado"],
                "respondeu={} em_execucao={} reservadas={} idade_da_mais_antiga_s={}".format(
                    workers["respondeu"],
                    workers["em_execucao"],
                    workers["reservadas"],
                    workers["idade_da_mais_antiga_s"],
                ),
                workers.get("motivo"),
            )
        )

        beat = partes["beat"]
        self.stdout.write(
            self._linha(
                "beat",
                beat["verificado"],
                f"idade_s={beat['idade_s']} expirado={beat['expirado']}",
                beat.get("motivo"),
            )
        )

        ciclo = partes["ultimo_ciclo"]
        self.stdout.write(
            self._linha(
                "ultimo_ciclo",
                ciclo["verificado"],
                "task={} estado={} tentativas={}/{} erro={}".format(
                    ciclo.get("task"),
                    ciclo.get("estado"),
                    ciclo.get("tentativas_observadas"),
                    ciclo.get("max_tentativas"),
                    ciclo.get("erro"),
                ),
                ciclo.get("motivo"),
            )
        )

        if relatorio["arquivo_estado_problema"]:
            self.stdout.write(
                self.style.WARNING(
                    f"  arquivo_estado_problema: {relatorio['arquivo_estado_problema']}"
                )
            )
        for motivo in relatorio["motivos"]:
            self.stdout.write(self.style.WARNING(f"  - {motivo}"))

    def _linha(self, nome, verificado, resumo, motivo):
        marca = "verificado" if verificado else "NAO VERIFICADO"
        linha = f"  {nome}: [{marca}] {resumo}"
        if motivo:
            linha = f"{linha} — {motivo}"
        return linha
