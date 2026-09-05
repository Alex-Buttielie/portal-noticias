from django.db.models import Q

from catalogo_noticias.models import NewsItem
from painel_admin.models import AuditoriaAdmin


def auditar(*, acao, alvo_tipo, alvo_id, detalhe, alterado_por):
    return AuditoriaAdmin.objects.create(
        acao=acao, alvo_tipo=alvo_tipo, alvo_id=str(alvo_id), detalhe=detalhe or {}, alterado_por=alterado_por
    )


def decidir_fila(item_id, acao, admin_user):
    try:
        item = NewsItem.objects.select_related("cluster").get(pk=item_id)
    except NewsItem.DoesNotExist:
        return None
    anterior = item.status_revisao
    novo = NewsItem.STATUS_APROVADO if acao == "aprovar" else NewsItem.STATUS_REJEITADO
    if item.cluster_id:
        qs = NewsItem.objects.filter(cluster_id=item.cluster_id, status_revisao=NewsItem.STATUS_PENDENTE)
        qs.update(status_revisao=novo)
        item.status_revisao = novo
    else:
        item.status_revisao = novo
        item.save(update_fields=["status_revisao"])
    auditar(
        acao=f"fila_{acao}",
        alvo_tipo="NewsItem",
        alvo_id=item_id,
        detalhe={"anterior": anterior, "novo": novo, "cluster": item.cluster_id},
        alterado_por=admin_user,
    )
    return item


def filtrar_usuarios(qs, search):
    if search:
        qs = qs.filter(Q(email__icontains=search) | Q(nome__icontains=search))
    return qs
