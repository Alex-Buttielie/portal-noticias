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
        # Achado em producao 2026-10-12: o item em si so era salvo via este
        # qs.update(), que exige status_revisao=PENDENTE. Reverter uma
        # decisao anterior (ex.: aprovar, depois rejeitar o mesmo item ja
        # aprovado) casava zero linhas aqui — item.status_revisao = novo
        # ficava so em memoria, nunca chegava ao banco, e a view respondia
        # 200 com o novo status como se tivesse persistido. Os IRMAOS de
        # cluster continuam so via qs.update() (ainda precisam estar
        # PENDENTE pra herdar a decisao); o ITEM em si agora e SEMPRE salvo
        # explicitamente logo abaixo, fora do if/else, para qualquer status
        # anterior dele.
        qs = NewsItem.objects.filter(
            cluster_id=item.cluster_id, status_revisao=NewsItem.STATUS_PENDENTE
        ).exclude(pk=item.pk)
        qs.update(status_revisao=novo)
    item.status_revisao = novo
    item.save(update_fields=["status_revisao"])

    # A decisão muda o conjunto publicável e, portanto, o snapshot de
    # títulos/categorias usado pelo autocomplete. Este serviço não abre uma
    # transação atômica e sua única chamada é FilaDecisaoView, com
    # ATOMIC_REQUESTS desabilitado; portanto a invalidação imediata é segura.
    # Se um caller futuro envolver a função em atomic, deverá usar on_commit.
    from feed.busca import invalidar_cache_autocomplete

    invalidar_cache_autocomplete()
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
