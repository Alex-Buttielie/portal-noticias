"""Serviço de domínio de newsletter (run 20260902-1515-newsletter)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import EmailMessage

from config.email_entrega import (
    CanalIndisponivel,
    FalhaDeEntrega,
    entregar_email,
    registrar_evento,
    verificar_canal_email,
)
from feed.services import itens_publicaveis
from gating.services import has_feature
from radar.services import tendencias as radar_tendencias

from .models import EnvioNewsletter, InscricaoNewsletter

logger = logging.getLogger(__name__)

#: Rótulo da métrica de entrega deste fluxo (`portal_email_entrega_total`) e
#: assunto do e-mail. O assunto é constante: nenhum dado do inscrito (nem do
#: conteúdo do resumo) entra em header.
DESTINO_NEWSLETTER = "newsletter"
ASSUNTO_NEWSLETTER = "Seu resumo do Portal de Notícias"


class RecursoGatedError(Exception):
    pass


def inscrever(user, tipo, categorias=None, periodo=None) -> InscricaoNewsletter:
    """Critério de aceite 1 — personalizada exige gating."""
    if tipo == InscricaoNewsletter.TIPO_PERSONALIZADA and not has_feature(user, "newsletter_personalizada"):
        raise RecursoGatedError("Newsletter personalizada é um recurso Premium.")
    defaults = {"tipo": tipo, "categorias": categorias or [], "ativa": True}
    if periodo:
        defaults["periodo"] = periodo
    inscricao, _ = InscricaoNewsletter.objects.update_or_create(user=user, defaults=defaults)
    return inscricao


def cancelar_inscricao(user) -> None:
    InscricaoNewsletter.objects.filter(user=user).update(ativa=False)


def descadastrar_por_token(token: str) -> bool:
    """Critério de aceite 4 — funciona sem login."""
    return InscricaoNewsletter.objects.filter(token_descadastro=token).update(ativa=False) > 0


def _itens_para_inscricao(inscricao: InscricaoNewsletter, limite=10):
    """Critério de aceite 2."""
    if inscricao.tipo == InscricaoNewsletter.TIPO_CATEGORIA and inscricao.categorias:
        itens = []
        for categoria in inscricao.categorias:
            itens.extend(list(itens_publicaveis(categoria=categoria)[:limite]))
        return itens[:limite]
    if inscricao.tipo == InscricaoNewsletter.TIPO_PERSONALIZADA:
        interesses = getattr(inscricao.user, "interesses", []) or []
        itens = []
        for interesse in interesses:
            itens.extend(list(itens_publicaveis(categoria=interesse)[:limite]))
        return itens[:limite] or list(itens_publicaveis()[:limite])
    return list(itens_publicaveis()[:limite])


def montar_corpo_email(inscricao: InscricaoNewsletter) -> str:
    """Critério de aceite 3 — sempre inclui link para a fonte original de cada item."""
    itens = _itens_para_inscricao(inscricao)
    linhas = ["Resumo do Portal de Notícias", ""]
    for item in itens:
        linhas.append(f"- {item.titulo} ({item.nome_fonte}): {item.url_fonte_original}")

    # BRD seção 27 — "Radar de tendências" é um item explícito do conteúdo
    # da newsletter, junto com "Principais acontecimentos" e "Links para
    # fontes originais" (já cobertos acima). Gap real encontrado na análise
    # do BRD: a newsletter nunca incluía nada do Radar. Reaproveita
    # `radar.services.tendencias()` (recorte nacional, sem filtro de
    # localidade — a inscrição de newsletter não guarda localidade própria)
    # e lista as 3 categorias com mais cobertura.
    assuntos = radar_tendencias().get("assuntos_em_alta", [])[:3]
    if assuntos:
        linhas.append("")
        linhas.append("Radar de tendências — assuntos em alta:")
        for assunto in assuntos:
            linhas.append(f"- {assunto['categoria']}: {assunto['numero_noticias']} notícia(s)")

    linhas.append("")
    linhas.append(f"Veja mais e assine o Premium: {settings.FRONTEND_BASE_URL}/planos")
    linhas.append(
        f"Para descadastrar: {settings.FRONTEND_BASE_URL}/newsletter/descadastrar"
        f"?token={inscricao.token_descadastro}"
    )
    return "\n".join(linhas)


def enviar_newsletters(periodo: str | None = None) -> EnvioNewsletter:
    """
    Critérios de aceite 5, 6 — resiliente a falha individual; respeita
    consentimento e inscrição ativa. `periodo` (BRD seção 27 — "Resumo da
    manhã"/"Resumo da noite"): quando informado, envia só para inscrições
    daquele período (usado pelos 2 agendamentos de Celery Beat separados,
    manhã e noite); `None` envia para todas as inscrições ativas,
    independente do período — usado por `manage.py`/testes manuais.

    P1-04 — O CONTADOR NÃO PODE MENTIR
    ===================================
    Este era o terceiro lugar do furo que o P0-02c documentou. O código fazia
    `send_mail(...); total_enviados += 1`, e `console.EmailBackend` (o padrão
    de `config/settings.py:615-617`) devolve 1 depois de imprimir no stdout.
    O resultado era um `EnvioNewsletter` gravado no banco com
    `total_enviados == N` para N e-mails que ninguém recebeu, e um
    `tasks.py:10` logando "N enviados" — duas fontes de verdade afirmando
    que a newsletter foi entregue.

    Agora o envio passa por `config.email_entrega.entregar_email`: nada é
    enviado (e nada é impresso) sem canal de entrega real, e só é contado o
    que o provedor aceitou. Quando falta o canal, o envio é registrado com
    `total_enviados=0` e `total_falhas=<nº de inscrições>` — porque as
    inscrições não chegaram a ser tentadas, e `total_falhas` é o que o
    operador olha para saber que o resumo do dia não saiu. Um `logger.error`
    acompanha, e o canal aparece em `/health-detail`.
    """
    filtros = {"ativa": True, "user__consentimento_aceito_em__isnull": False}
    if periodo:
        filtros["periodo"] = periodo
    inscricoes = list(InscricaoNewsletter.objects.filter(**filtros).select_related("user"))

    if not inscricoes:
        # Nada a enviar: não há por que recusar por falta de canal, e o
        # `EnvioNewsletter` zerado é o registro honesto.
        return EnvioNewsletter.objects.create(
            total_inscricoes_processadas=0,
            total_enviados=0,
            total_falhas=0,
        )

    canal = verificar_canal_email()
    if not canal.disponivel:
        registrar_evento(DESTINO_NEWSLETTER, "sem_canal")
        logger.error(
            "newsletter: NENHUM resumo entregue (inscricoes=%s) por ausência de "
            "canal de entrega real (motivo=%s)",
            len(inscricoes),
            "; ".join(canal.motivos),
        )
        return EnvioNewsletter.objects.create(
            total_inscricoes_processadas=len(inscricoes),
            total_enviados=0,
            # Contadas como falha, e não como "não processada": do ponto de
            # vista de quem esperava o resumo da manhã, elas falharam.
            total_falhas=len(inscricoes),
        )

    total_enviados = 0
    total_falhas = 0
    for inscricao in inscricoes:
        try:
            entregar_email(
                EmailMessage(
                    subject=ASSUNTO_NEWSLETTER,
                    body=montar_corpo_email(inscricao),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[inscricao.user.email],
                ),
                destino=DESTINO_NEWSLETTER,
            )
            total_enviados += 1
        except (CanalIndisponivel, FalhaDeEntrega):
            # Sem `str(exc)` (o texto do provedor pode ecoar o corpo do
            # resumo) e sem o endereço do inscrito: o `id` da inscrição é o
            # que correlaciona. `identidade.emails` faz o mesmo.
            logger.error(
                "newsletter: resumo NÃO entregue para a inscrição id=%s", inscricao.id
            )
            total_falhas += 1
        except Exception:  # noqa: BLE001 — resiliência por inscrição (AC-6)
            logger.exception("Falha ao enviar newsletter para inscrição %s", inscricao.id)
            total_falhas += 1

    envio = EnvioNewsletter.objects.create(
        total_inscricoes_processadas=len(inscricoes),
        total_enviados=total_enviados,
        total_falhas=total_falhas,
    )
    if total_falhas:
        logger.error(
            "newsletter: envio concluído COM FALHAS — %d entregues, %d falhas de %d",
            total_enviados,
            total_falhas,
            len(inscricoes),
        )
    return envio
