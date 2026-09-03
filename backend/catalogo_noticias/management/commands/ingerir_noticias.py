"""
Comando manual para rodar uma unica rodada do pipeline de ingestao
(services.executar_ingestao) sem depender de Celery/Redis - util para
desenvolvimento local e para validar o pipeline sob demanda. A task Celery
periodica (catalogo_noticias/tasks.py, CELERY_BEAT_SCHEDULE em
config/settings.py) chama a mesma funcao de servico automaticamente em
producao; este comando e so um atalho para rodar a mesma logica na hora.
"""

from django.core.management.base import BaseCommand

from catalogo_noticias.services.ingestao import executar_ingestao


class Command(BaseCommand):
    help = (
        "Roda uma rodada do pipeline de ingestao de noticias (busca RSS -> "
        "dedup/agrupamento -> resumo/classificacao -> fila de revisao) para "
        "todas as fontes configuradas em CATALOGO_NOTICIAS_FONTES_RSS."
    )

    def handle(self, *args, **options):
        registro = executar_ingestao()

        self.stdout.write(self.style.SUCCESS(f"Execucao concluida (registro_id={registro.id})"))
        self.stdout.write(f"  Itens novos ingeridos: {registro.total_itens_ingeridos}")
        self.stdout.write(f"  Grupos/acontecimentos formados: {registro.total_grupos_formados}")
        self.stdout.write(f"  Duplicatas agrupadas: {registro.total_duplicatas_agrupadas}")
        self.stdout.write(f"  Chamadas ao SummarizationProvider: {registro.chamadas_summarization_provider}")

        self.stdout.write("  Itens por fonte:")
        for nome_fonte, quantidade in registro.itens_por_fonte.items():
            self.stdout.write(f"    - {nome_fonte}: {quantidade}")

        if registro.erros_por_fonte:
            self.stdout.write(self.style.WARNING("  Fontes com erro nesta execucao:"))
            for nome_fonte, erro in registro.erros_por_fonte.items():
                self.stdout.write(self.style.WARNING(f"    - {nome_fonte}: {erro}"))

        if registro.total_itens_ingeridos == 0 and not registro.erros_por_fonte:
            self.stdout.write(
                self.style.WARNING(
                    "  Nenhum item novo (todas as URLs dos feeds atuais ja tinham sido "
                    "ingeridas antes - rode de novo mais tarde, quando as fontes publicarem "
                    "materias novas)."
                )
            )

        self.stdout.write(
            "\nPara ver os itens ingeridos: acesse http://localhost:8000/admin/catalogo_noticias/newsitem/ "
            "(o feed publico so mostra status 'nao_aplicavel'/'aprovado' - sem uma "
            "CATALOGO_NOTICIAS_LLM_API_KEY real configurada, todo item novo cai em "
            "'pendente' e fica visivel so no admin ate ser aprovado manualmente)."
        )
