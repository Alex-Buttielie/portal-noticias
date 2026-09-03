"""Serviço de domínio B2B (run 20260902-1519-b2b-corporativo)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Q
from django.utils import timezone

from catalogo_noticias.models import NewsItem

from .models import CriterioMonitoramento, MembroOrganizacao, Organizacao

logger = logging.getLogger(__name__)


class PermissaoNegadaError(Exception):
    pass


def criar_organizacao(nome, plano=Organizacao.PLANO_BASIC) -> Organizacao:
    return Organizacao.objects.create(nome=nome, plano=plano)


def criar_organizacao_com_admin(nome, admin_user, plano=Organizacao.PLANO_BASIC) -> Organizacao:
    """
    Bootstrap: cria a organização E já registra `admin_user` como seu
    primeiro `MembroOrganizacao` (papel admin_organizacao) — não passa por
    `_exigir_admin_da_organizacao` porque, por definição, ainda não existe
    NENHUM membro para checar contra (operação privilegiada, feita pela
    equipe/admin da plataforma no onboarding comercial de uma organização,
    não um endpoint self-service do usuário final).
    """
    organizacao = Organizacao.objects.create(nome=nome, plano=plano)
    MembroOrganizacao.objects.create(
        organizacao=organizacao, user=admin_user, papel_na_organizacao=MembroOrganizacao.PAPEL_ADMIN
    )
    return organizacao


def _exigir_admin_da_organizacao(user, organizacao):
    try:
        membro = MembroOrganizacao.objects.get(user=user, organizacao=organizacao)
    except MembroOrganizacao.DoesNotExist:
        raise PermissaoNegadaError("Usuário não pertence a esta organização.")
    if membro.papel_na_organizacao != MembroOrganizacao.PAPEL_ADMIN:
        raise PermissaoNegadaError("Só o administrador da organização pode fazer isso.")


def adicionar_membro(organizacao, user, *, quem_adiciona, papel_na_organizacao=MembroOrganizacao.PAPEL_MEMBRO):
    """Critério de aceite 2."""
    _exigir_admin_da_organizacao(quem_adiciona, organizacao)
    return MembroOrganizacao.objects.create(
        organizacao=organizacao, user=user, papel_na_organizacao=papel_na_organizacao
    )


def remover_membro(organizacao, user, *, quem_remove):
    _exigir_admin_da_organizacao(quem_remove, organizacao)
    MembroOrganizacao.objects.filter(organizacao=organizacao, user=user).delete()


def organizacao_do_usuario(user) -> Organizacao | None:
    """
    Critério de aceite 5 — ÚNICO ponto que qualquer view deve usar para
    descobrir a organização do requisitante. Nunca aceitar um `organizacao_id`
    vindo direto da URL/payload sem passar por aqui — garante isolamento.
    """
    membro = MembroOrganizacao.objects.filter(user=user).select_related("organizacao").first()
    return membro.organizacao if membro else None


def criar_criterio(organizacao, tipo, valor) -> CriterioMonitoramento:
    return CriterioMonitoramento.objects.create(organizacao=organizacao, tipo=tipo, valor=valor)


def _itens_para_criterio(criterio: CriterioMonitoramento, dias=30):
    corte = timezone.now() - timedelta(days=dias)
    qs = NewsItem.objects.filter(
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
        timestamp_ingestao__gte=corte,
    )
    if criterio.tipo == CriterioMonitoramento.TIPO_SETOR:
        return qs.filter(categoria__icontains=criterio.valor)
    return qs.filter(Q(titulo__icontains=criterio.valor) | Q(resumo_proprio__icontains=criterio.valor))


def itens_monitorados(organizacao: Organizacao, dias=30) -> dict:
    """Critério de aceite 3 — sempre escopado à `organizacao` recebida."""
    resultado = {}
    for criterio in organizacao.criterios.filter(ativo=True):
        resultado[criterio.id] = {
            "criterio": {"tipo": criterio.tipo, "valor": criterio.valor},
            "itens": list(
                _itens_para_criterio(criterio, dias).values(
                    "id", "titulo", "url_fonte_original", "nome_fonte"
                )
            ),
        }
    return resultado


def _itens_novos_para_criterio(criterio: CriterioMonitoramento):
    """
    Diferente de `_itens_para_criterio` (janela fixa de N dias, usada pelo
    painel): aqui o corte é `ultimo_alerta_em` (ou `criado_em`, se o
    critério nunca foi alertado) — cada item só entra em UM alerta, nunca é
    reenviado.
    """
    desde = criterio.ultimo_alerta_em or criterio.criado_em
    qs = NewsItem.objects.filter(
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
        timestamp_ingestao__gt=desde,
    )
    if criterio.tipo == CriterioMonitoramento.TIPO_SETOR:
        return qs.filter(categoria__icontains=criterio.valor)
    return qs.filter(Q(titulo__icontains=criterio.valor) | Q(resumo_proprio__icontains=criterio.valor))


def verificar_e_enviar_alertas() -> dict:
    """
    BRD §19 — "Alertas" quando novo conteúdo bate em um critério monitorado
    é um item explícito do produto B2B. Gap real encontrado na análise do
    BRD: `itens_monitorados`/`resumo_executivo` só respondem quando o
    usuário abre o painel — nada avisava proativamente por e-mail. Chamada
    pela task periódica (`tasks.verificar_alertas`); resiliente a falha
    individual de um critério (mesmo padrão de `newsletter.enviar_newsletters`
    e `catalogo_noticias.executar_ingestao`).
    """
    total_criterios_verificados = 0
    total_alertas_enviados = 0
    total_falhas = 0

    criterios = CriterioMonitoramento.objects.filter(ativo=True, organizacao__ativo=True).select_related(
        "organizacao"
    )
    for criterio in criterios:
        total_criterios_verificados += 1
        try:
            itens_novos = list(
                _itens_novos_para_criterio(criterio).values("titulo", "url_fonte_original", "nome_fonte")[:20]
            )
            if not itens_novos:
                continue

            destinatarios = list(
                MembroOrganizacao.objects.filter(organizacao=criterio.organizacao).values_list(
                    "user__email", flat=True
                )
            )
            if not destinatarios:
                continue

            linhas = [
                f"Novidades para o critério '{criterio.valor}' ({criterio.get_tipo_display()}) "
                f"— {criterio.organizacao.nome}:",
                "",
            ]
            for item in itens_novos:
                linhas.append(f"- {item['titulo']} ({item['nome_fonte']}): {item['url_fonte_original']}")
            linhas.append("")
            linhas.append(f"Painel completo: {settings.FRONTEND_BASE_URL}/empresa")

            send_mail(
                subject=f"[Alerta] {criterio.organizacao.nome} — novidades em '{criterio.valor}'",
                message="\n".join(linhas),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=destinatarios,
                fail_silently=False,
            )
            criterio.ultimo_alerta_em = timezone.now()
            criterio.save(update_fields=["ultimo_alerta_em"])
            total_alertas_enviados += 1
        except Exception:
            logger.exception("Falha ao verificar/enviar alerta do critério %s", criterio.id)
            total_falhas += 1

    return {
        "total_criterios_verificados": total_criterios_verificados,
        "total_alertas_enviados": total_alertas_enviados,
        "total_falhas": total_falhas,
    }


def resumo_executivo(organizacao: Organizacao, dias=30) -> dict:
    """Critério de aceite 4."""
    monitorado = itens_monitorados(organizacao, dias)
    return {
        "organizacao": organizacao.nome,
        "criterios": [
            {
                "tipo": dados["criterio"]["tipo"],
                "valor": dados["criterio"]["valor"],
                "numero_itens": len(dados["itens"]),
            }
            for dados in monitorado.values()
        ],
    }
