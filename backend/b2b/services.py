"""Serviço de domínio B2B (run 20260902-1519-b2b-corporativo)."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone

from catalogo_noticias.models import NewsItem

from . import cache as cache_b2b
from . import limites
from .limites import CotaDeCriteriosExcedidaError
from .models import CriterioMonitoramento, MembroOrganizacao, Organizacao
from .permissions import PermissaoNegadaError, exigir

logger = logging.getLogger(__name__)

# Reexportado para quem já importava daqui (e para as views, que traduzem o
# erro em 403). A implementação da matriz está em `b2b/permissions.py`.
__all__ = [
    "CotaDeCriteriosExcedidaError",
    "CriterioMonitoramento",
    "MembroOrganizacao",
    "Organizacao",
    "PermissaoNegadaError",
    "adicionar_membro",
    "criar_criterio",
    "criar_organizacao",
    "criar_organizacao_com_admin",
    "invalidar_cache_da_organizacao",
    "itens_monitorados",
    "organizacao_do_usuario",
    "remover_membro",
    "resumo_executivo",
    "verificar_e_enviar_alertas",
]


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


def _exigir_admin_da_organizacao(user, organizacao, acao="convidar_membro"):
    """
    Guarda de papel. Delega a `b2b/permissions.py` (fonte única da matriz) e
    é mantida aqui como invariante do domínio: `adicionar_membro`/
    `remover_membro` continuam insecuráveis se alguém chamar o serviço
    direto, sem passar pela view. A view também checa — antes de tocar no
    banco, para devolver 403 sem revelar nada sobre o alvo.
    """
    exigir(user, organizacao, acao)


def _eh_admin(user, organizacao) -> bool:
    from .permissions import eh_admin_da_organizacao

    return eh_admin_da_organizacao(user, organizacao)


def adicionar_membro(organizacao, user, *, quem_adiciona, papel_na_organizacao=MembroOrganizacao.PAPEL_MEMBRO):
    """Critério de aceite 2."""
    _exigir_admin_da_organizacao(quem_adiciona, organizacao)
    if papel_na_organizacao not in dict(MembroOrganizacao.PAPEL_CHOICES):
        raise PermissaoNegadaError("Papel de organização inválido.")
    # `MembroOrganizacao.user` é OneToOne: sem esta checagem o erro viraria
    # IntegrityError (500) numa corrida entre dois convites simultâneos.
    if MembroOrganizacao.objects.filter(user=user).exists():
        raise PermissaoNegadaError("Este usuário já pertence a uma organização.")
    membro = MembroOrganizacao.objects.create(
        organizacao=organizacao, user=user, papel_na_organizacao=papel_na_organizacao
    )
    return membro


def remover_membro(organizacao, user, *, quem_remove):
    """
    Remoção escopada: `filter(organizacao=..., user=...)` — um admin só
    alcança membro da PRÓPRIA organização, mesmo que mande o e-mail de
    alguém de outra empresa (o delete simplesmente não casa).
    """
    _exigir_admin_da_organizacao(quem_remove, organizacao)
    alvo = MembroOrganizacao.objects.filter(organizacao=organizacao, user=user).first()
    if alvo is None:
        return
    _impedir_organizacao_sem_admin(alvo)
    alvo.delete()


def _impedir_organizacao_sem_admin(alvo: MembroOrganizacao) -> None:
    """
    Não remove o ÚLTIMO `admin_organizacao` da organização.

    Sem esta guarda, o administrador poderia remover a si mesmo (ou ser o alvo
    de uma remoção) e a organização ficava sem nenhum administrador: `exigir(
    ..., "convidar_membro")` passaria a falhar para sempre e mais ninguém
    poderia adicionar membros — uma organização órfã, sem volta pela API. O
    sintoma (todo mundo 403 em `/membros/`) não aponta para a causa.
    """
    if alvo.papel_na_organizacao != MembroOrganizacao.PAPEL_ADMIN:
        return
    outros_admins = MembroOrganizacao.objects.filter(
        organizacao=alvo.organizacao, papel_na_organizacao=MembroOrganizacao.PAPEL_ADMIN
    ).exclude(pk=alvo.pk)
    if not outros_admins.exists():
        raise PermissaoNegadaError(
            "A organização precisa de ao menos um administrador: "
            "promova outro membro a administrador antes de remover este."
        )


def organizacao_do_usuario(user) -> Organizacao | None:
    """
    Critério de aceite 5 — ÚNICO ponto que qualquer view deve usar para
    descobrir a organização do requisitante. Nunca aceitar um `organizacao_id`
    vindo direto da URL/payload sem passar por aqui — garante isolamento.
    """
    membro = MembroOrganizacao.objects.filter(user=user).select_related("organizacao").first()
    return membro.organizacao if membro else None


def invalidar_cache_da_organizacao(organizacao: Organizacao) -> None:
    """Descarta o painel cacheado da organização (ver `b2b/cache.py`)."""
    cache_b2b.invalidar_organizacao(organizacao)


def criar_criterio(organizacao, tipo, valor) -> CriterioMonitoramento:
    """
    Cria um critério ATIVO na organização, respeitando a cota do plano.

    A cota é conferida antes do INSERT (e de novo é um problema de corrida
    resolvido no plano de produto, não aqui: o teto é folgado porfolios
    grandes, não é um limite de banco). O que a cota protege de verdade é o
    custo do job periódico de alertas, que varre `NewsItem` uma vez por
    critério ativo.
    """
    limites.exigir_dentro_da_cota(organizacao)
    criterio = CriterioMonitoramento.objects.create(organizacao=organizacao, tipo=tipo, valor=valor)
    invalidar_cache_da_organizacao(organizacao)
    return criterio


def _itens_para_criterio(criterio: CriterioMonitoramento, dias=30):
    corte = timezone.now() - timedelta(days=dias)
    qs = NewsItem.objects.filter(
        status_revisao__in=[NewsItem.STATUS_NAO_APLICAVEL, NewsItem.STATUS_APROVADO],
        timestamp_ingestao__gte=corte,
    )
    if criterio.tipo == CriterioMonitoramento.TIPO_SETOR:
        return qs.filter(categoria__icontains=criterio.valor)
    return qs.filter(Q(titulo__icontains=criterio.valor) | Q(resumo_proprio__icontains=criterio.valor))


def _max_itens_por_criterio() -> int:
    try:
        return max(1, int(getattr(settings, "B2B_MAX_ITENS_POR_CRITERIO", 50)))
    except (TypeError, ValueError):
        return 50


def itens_monitorados(organizacao: Organizacao, dias=30) -> dict:
    """
    Critério de aceite 3 — sempre escopado à `organizacao` recebida.

    Itera `organizacao.criterios` (a relação já filtrada pela organização —
    não há consulta global de `CriterioMonitoramento` em nenhum ponto deste
    caminho), então a chave do dicionário devolvido só pode ser o id de um
    critério da própria empresa.

    O corpo da lista é limitado por `B2B_MAX_ITENS_POR_CRITERIO`; o total
    verdadeiro vem de um `count()` na MESMA query escopada (`total_itens`).
    Sem teto, um critério genérico ("economia") serializava a janela inteira
    numa resposta — e o `count()` só é confiável porque está na mesma query
    filtrada por organização, nunca num total global.
    """
    em_cache = cache_b2b.ler(organizacao, cache_b2b.RECURSO_ITENS_MONITORADOS, dias)
    if em_cache is not None:
        # As chaves voltam como `str` (JSON não tem chave inteira) e são
        # reconvertidas para manter o contrato em Python.
        return {int(chave): dados for chave, dados in em_cache.items()}

    teto = _max_itens_por_criterio()
    resultado = {}
    for criterio in organizacao.criterios.filter(ativo=True):
        itens = _itens_para_criterio(criterio, dias)
        total = itens.count()
        resultado[criterio.id] = {
            "criterio": {"tipo": criterio.tipo, "valor": criterio.valor},
            "itens": list(itens.values("id", "titulo", "url_fonte_original", "nome_fonte")[:teto]),
            "total_itens": total,
            "itens_truncados": total > teto,
        }
    cache_b2b.gravar(
        organizacao,
        cache_b2b.RECURSO_ITENS_MONITORADOS,
        {str(chave): dados for chave, dados in resultado.items()},
        dias,
    )
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


def _alerta_max_itens() -> int:
    try:
        return max(1, int(getattr(settings, "B2B_ALERTA_MAX_ITENS", 20)))
    except (TypeError, ValueError):
        return 20


def _alerta_max_por_execucao() -> int:
    try:
        return max(0, int(getattr(settings, "B2B_ALERTA_MAX_POR_EXECUCAO", 50)))
    except (TypeError, ValueError):
        return 50


def _alerta_max_por_organizacao() -> int:
    try:
        return max(0, int(getattr(settings, "B2B_ALERTA_MAX_POR_ORGANIZACAO", 3)))
    except (TypeError, ValueError):
        return 3


def _alerta_cooldown() -> timedelta:
    try:
        return timedelta(minutes=max(0, int(getattr(settings, "B2B_ALERTA_COOLDOWN_MINUTOS", 240))))
    except (TypeError, ValueError):
        return timedelta(minutes=240)


def _em_cooldown(criterio: CriterioMonitoramento, agora) -> bool:
    """
    O ratchet de `ultimo_alerta_em` impede reenvio do MESMO item; o cooldown
    impede o outro extremo — um item novo a cada hora virar um e-mail por
    execução. É adiamento, não cancelamento: passado o intervalo, tudo que
    entrou desde o último `ultimo_alerta_em` sai na execução seguinte (o corte
    do ratchet não se move enquanto o cooldown é respeitado), então nenhum
    item é perdido — só a frequência é amortecida.
    """
    if criterio.ultimo_alerta_em is None:
        return False
    return (agora - criterio.ultimo_alerta_em) < _alerta_cooldown()


def _registrar_anomalia(anomalias: list, tipo: str, organizacao: Organizacao, detalhe: str) -> None:
    """Acumula o sinal de anomalia de tenant e o deixa acionável no log."""
    anomalias.append(
        {
            "tipo": tipo,
            "organizacao_id": organizacao.pk,
            "organizacao": organizacao.nome,
            "plano": organizacao.plano,
            "detalhe": detalhe,
        }
    )
    logger.warning(
        "b2b anomalia de tenant: tipo=%s organizacao_id=%s organizacao=%r plano=%s detalhe=%s",
        tipo,
        organizacao.pk,
        organizacao.nome,
        organizacao.plano,
        detalhe,
    )


def _anomalias_de_cota_e_higiene() -> list:
    """
    Sinais de anomalia de tenant derivados do estado atual — sem tabela nova,
    sem migration.

    Todos são detectáveis numa consulta agregada e todos são acionáveis (dizem
    o que fazer), e nenhum é "sempre dispara":

    - `cota_atingida`: a organização está no teto de critérios do seu plano.
      Sinal comercial (a cota está barrando o cliente) e de higiene de custo
      (é a organização que mais pesa no job de alertas).
    - `sem_destinatario`: há critérios ativos mas nenhum membro com e-mail —
      hoje o envio era silenciosamente pulado e o cliente achava que estava
      sendo monitorado sem receber nada. Inconsistência de dados que só o
      operador consegue resolver.
    - `organizacao_inativa_com_criterios`: a organização está desativada mas
      ainda tem critérios ativos; o filtro `organizacao__ativo=True` da
      varredura os pula em silêncio, e a varredura morta continua custando
      enquanto ninguém souber que existem.
    Query agregada única para os três sinais — nenhum deles abre uma consulta
    por organização.
    """
    anomalias = []
    orgaos_com_criterios = Organizacao.objects.annotate(
        ativos=Count("criterios", filter=Q(criterios__ativo=True))
    ).filter(ativos__gt=0)

    for organizacao in orgaos_com_criterios:
        if not organizacao.ativo:
            _registrar_anomalia(
                anomalias,
                "organizacao_inativa_com_criterios",
                organizacao,
                f"{organizacao.ativos} critério(s) ativo(s) em organização desativada: "
                "a varredura de alertas os ignora — desative os critérios ou reative a organização.",
            )
            continue
        cota = limites.cota_de_criterios(organizacao)
        if organizacao.ativos >= cota:
            _registrar_anomalia(
                anomalias,
                "cota_atingida",
                organizacao,
                f"{organizacao.ativos}/{cota} critérios ativos no plano "
                f"'{organizacao.plano}': novos critérios estão barrados pela cota.",
            )
        tem_destinatario = MembroOrganizacao.objects.filter(
            organizacao=organizacao
        ).exclude(user__email="").exists()
        if not tem_destinatario:
            _registrar_anomalia(
                anomalias,
                "sem_destinatario",
                organizacao,
                f"{organizacao.ativos} critério(s) ativo(s) e nenhum membro com e-mail: "
                "nenhum alerta pode ser enviado — adicione um membro à organização.",
            )
    return anomalias


def verificar_e_enviar_alertas() -> dict:
    """
    BRD §19 — "Alertas" quando novo conteúdo bate em um critério monitorado
    é um item explícito do produto B2B. Gap real encontrado na análise do
    BRD: `itens_monitorados`/`resumo_executivo` só respondem quando o
    usuário abre o painel — nada avisava proativamente por e-mail. Chamada
    pela task periódica (`tasks.verificar_alertas`); resiliente a falha
    individual de um critério (mesmo padrão de `newsletter.enviar_newsletters`
    e `catalogo_noticias.executar_ingestao`).

    P1-13 — três problemas reais desta função, todos fechados aqui:

    1. **Sem teto de envio (storm).** O envio era "um e-mail por critério que
       casou", sem teto nem por execução nem por organização: com N
       organizações e M critérios, uma execução podia mandar N×M e-mails, e uma
       organização concentrada podia esmagar as demais. Agora há
       `B2B_ALERTA_MAX_POR_EXECUCAO` e `B2B_ALERTA_MAX_POR_ORGANIZACAO`. O
       excedente é suprimido **sem** consumir o ratchet de `ultimo_alerta_em`:
       o que não saiu sai na próxima execução, nada se perde.
    2. **Sem cooldown.** O ratchet só impede reenvio do mesmo item; um fluxo
       contínuo de notícias virava um e-mail por execução, por critério. Ver
       `_em_cooldown` — adia, não cancela, e é por critério (o volume por
       organização é responsabilidade dos dois tetos, não do tempo).
    3. **Sem sinal de anomalia de tenant.** Uma organização órfã, sem
       destinatário, no teto da cota ou desativada com critérios pendentes era
       pulada em silêncio. Ver `_anomalias_de_cota_e_higiene`.
    """
    agora = timezone.now()
    total_criterios_verificados = 0
    total_alertas_enviados = 0
    total_falhas = 0
    total_suprimidos_execucao = 0
    total_suprimidos_organizacao = 0
    total_suprimidos_cooldown = 0
    enviados_por_organizacao: dict[int, int] = {}

    anomalias = _anomalias_de_cota_e_higiene()

    criterios = CriterioMonitoramento.objects.filter(ativo=True, organizacao__ativo=True).select_related(
        "organizacao"
    )
    for criterio in criterios:
        total_criterios_verificados += 1
        try:
            # Cooldown por CRITÉRIO, na dimensão do tempo. O volume por
            # organização é limitado pelo teto por organização (logo abaixo) e o
            # volume total, pelo teto por execução — e são esses dois que
            # seguram a enxurrada, sem atrasar o alerta de um cliente por uma
            # janela inteira. Um curto-circuito do tipo "a organização já foi
            # avisada neste ciclo, o resto espera" foi descartado de propósito:
            # além de mascarar o contador do teto por organização (os dois
            # limites deixavam de ser observáveis separadamente), empurraria
            # para 4 horas a novidade de um segundo critério do mesmo cliente,
            # sem ganho real de anti-storm.
            if _em_cooldown(criterio, agora):
                total_suprimidos_cooldown += 1
                continue

            if total_alertas_enviados >= _alerta_max_por_execucao():
                total_suprimidos_execucao += 1
                continue

            enviados_org = enviados_por_organizacao.get(criterio.organizacao_id, 0)
            if enviados_org >= _alerta_max_por_organizacao():
                total_suprimidos_organizacao += 1
                continue

            itens_novos = list(
                _itens_novos_para_criterio(criterio).values(
                    "titulo", "url_fonte_original", "nome_fonte"
                )[:_alerta_max_itens()]
            )
            if not itens_novos:
                continue

            destinatarios = [
                email
                for email in MembroOrganizacao.objects.filter(organizacao=criterio.organizacao).values_list(
                    "user__email", flat=True
                )
                if email
            ]
            if not destinatarios:
                # Anomalia já detectada em `_anomalias_de_cota_e_higiene`; aqui
                # é só o curto-circuito (nada a enviar).
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
            enviados_por_organizacao[criterio.organizacao_id] = enviados_org + 1
        except Exception:
            logger.exception(
                "Falha ao verificar/enviar alerta do critério %s (organizacao_id=%s)",
                criterio.id,
                criterio.organizacao_id,
            )
            total_falhas += 1
            _registrar_anomalia(
                anomalias,
                "falha_ao_enviar",
                criterio.organizacao,
                f"falha ao enviar o alerta do critério {criterio.id}: ver traceback no log.",
            )

    return {
        "total_criterios_verificados": total_criterios_verificados,
        "total_alertas_enviados": total_alertas_enviados,
        "total_falhas": total_falhas,
        "total_suprimidos_por_limite_execucao": total_suprimidos_execucao,
        "total_suprimidos_por_limite_organizacao": total_suprimidos_organizacao,
        "total_suprimidos_por_cooldown": total_suprimidos_cooldown,
        "anomalias": anomalias,
    }


def resumo_executivo(organizacao: Organizacao, dias=30) -> dict:
    """
    Critério de aceite 4.

    `numero_itens` é o total VERDADEIRO de itens casados, lido do mesmo
    `itens_monitorados` (que só varre `organizacao.criterios`) — o resumo não
    faz agregação própria, justamente para não haver um segundo caminho que
    possa esquecer o filtro de tenant. `organizacao.nome` sai do objeto já
    escopado, nunca de um id do payload.
    """
    em_cache = cache_b2b.ler(organizacao, cache_b2b.RECURSO_RESUMO_EXECUTIVO, dias)
    if em_cache is not None:
        return em_cache

    monitorado = itens_monitorados(organizacao, dias)
    resumo = {
        "organizacao": organizacao.nome,
        "plano": organizacao.plano,
        "criterios": [
            {
                "tipo": dados["criterio"]["tipo"],
                "valor": dados["criterio"]["valor"],
                "numero_itens": dados["total_itens"],
            }
            for dados in monitorado.values()
        ],
        "cota_criterios": limites.cota_de_criterios(organizacao),
        "criterios_ativos": limites.criterios_ativos_da_organizacao(organizacao),
    }
    cache_b2b.gravar(organizacao, cache_b2b.RECURSO_RESUMO_EXECUTIVO, resumo, dias)
    return resumo
