"""Serviço de domínio B2B (run 20260902-1519-b2b-corporativo).

O ALERTA B2B PASSA PELO GATE DE E-MAIL (este item)
==================================================
Até aqui `verificar_e_enviar_alertas` chamava `django.core.mail.send_mail`
direto (`b2b/services.py:459` na base `623a0e9`) e era o ÚNICO lugar do projeto
que ainda contornava `config/email_entrega.py`. O `identidade/emails.py` também
chama `send_mail` no nome, mas é o adaptador fino que o P1-04 criou — ele
NÃO contorna o gate, ele **é** o gate para aquele fluxo.

O buraco era o mesmo que o P0-02c documentou, com dois agravantes que só
aparecem quando se olha para este arquivo:

1. **A resposta HTTP não existe aqui.** O `contato` mentia num 200; a
   newsletter mentia num `total_enviados` gravado. O B2B mente num **log de
   task** (`b2b/tasks.py:10`: "%d alerta(s) enviado(s)") e num placar que
   volta para o Beat. O operador lê "1 alerta enviado" e conclui que o
   monitoramento do cliente funciona.
2. **O ratchet anda mesmo quando nada foi entregue.** `ultimo_alerta_em` era
   gravado DEPOIS do `send_mail` e sem olhar o retorno: com
   `DJANGO_EMAIL_BACKEND=console.EmailBackend` (o default de
   `config/settings.py:652-654`), `send_mail` devolvia 1 depois de imprimir no
   stdout, o ratchet avançava, e as notícias ficavam **para sempre** marcadas
   como já alertadas. Medido antes desta correção, com `console`:
   `total_alertas_enviados=1`, `total_falhas=0`, `ultimo_alerta_em` gravado, e
   um e-mail inteiro impresso no stdout do container. Um cliente que nunca
   recebe o alerta e nunca o recebe de novo, com o job reportando sucesso.

O que mudou: o envio passa por `config.email_entrega.entregar_email` (fonte
única do projeto, P1-04), e há um portão de canal ANTES do laço — nada é
montado, nada é impresso, nenhum ratchet anda quando não existe para quem
entregar. Quem é avisado, e como, está em `entregar_alerta`.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Count, Q
from django.utils import timezone

from catalogo_noticias.models import NewsItem
from config.email_entrega import (
    CanalIndisponivel,
    FalhaDeEntrega,
    entregar_email,
    orientacao_de_configuracao,
    registrar_evento,
    verificar_canal_email,
)

from . import cache as cache_b2b
from . import limites
from .limites import CotaDeCriteriosExcedidaError
from .models import CriterioMonitoramento, MembroOrganizacao, Organizacao
from .permissions import PermissaoNegadaError, exigir

logger = logging.getLogger(__name__)

#: Rótulo da métrica `portal_email_entrega_total` deste fluxo. É rótulo, não
#: dado: nenhum endereço de membro, nome de organização ou título de notícia
#: entra nele. Sai para `/metrics` como `destino="b2b_alerta"`.
DESTINO_ALERTA_B2B = "b2b_alerta"

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
    "entregar_alerta",
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


def _corpo_do_alerta(criterio: CriterioMonitoramento, itens_novos: list) -> str:
    """Corpo text/plain do alerta. Nenhum header carrega dado de membro."""
    linhas = [
        f"Novidades para o critério '{criterio.valor}' ({criterio.get_tipo_display()}) "
        f"— {criterio.organizacao.nome}:",
        "",
    ]
    for item in itens_novos:
        linhas.append(f"- {item['titulo']} ({item['nome_fonte']}): {item['url_fonte_original']}")
    linhas.append("")
    linhas.append(f"Painel completo: {settings.FRONTEND_BASE_URL}/empresa")
    return "\n".join(linhas)


def entregar_alerta(
    criterio: CriterioMonitoramento, itens_novos: list, destinatarios: list
) -> int:
    """Entrega UM alerta de critério. Devolve o que foi entregue, ou levanta.

    Esta é a **costura de transporte** do `b2b`, e ela existe por um motivo
   duplo:

    * a política (recusa de backend que não entrega, e exigência de ≥ 1
      devolvida pelo provedor) NÃO é reimplementada aqui — é o
      `config.email_entrega.entregar_email`, o mesmo objeto que `contato`,
      `identidade` e `newsletter` usam;
    * ela é o ponto de aplicação dos dublês de
      `b2b/tests/test_p1_04_entrega.py`: substituir este atributo simula o
      provedor recusando ou estourando, sem que o teste precise saber nada
      do backend.

    `EmailMessage` e não `send_mail`: o corpo é text/plain e não há parte
    HTML. O assunto carrega o nome da organização e o valor do critério — que
    são dados do contrato B2B, não do membro — e nenhum endereço de destinatário
    vai em header, o que também não deixa superfície de injeção de header.
    """
    return entregar_email(
        EmailMessage(
            subject=f"[Alerta] {criterio.organizacao.nome} — novidades em '{criterio.valor}'",
            body=_corpo_do_alerta(criterio, itens_novos),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=list(destinatarios),
        ),
        destino=DESTINO_ALERTA_B2B,
    )


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

    P1-17 — O PLACAR NÃO PODE MENTIR (o gate de e-mail)
    ====================================================
    Este era o ÚNICO fluxo de e-mail do projeto que não passava por
    `config.email_entrega.py`, e ele mentia de um jeito que os outros três não
    conseguiam mentir: ** advancing the ratchet**. Os outros contam errado; este
    perdia o alerta. `ultimo_alerta_em` era gravado depois de um `send_mail` cujo
    retorno ninguém olhava, então com `console.EmailBackend` (o default de
    `config/settings.py:652-654`) o critério era marcado como "já alertado" sem
    que nada tivesse saído — e `_itens_novos_para_criterio` corta por esse
    campo, então aquelas notícias **nunca mais** entravam em alerta, nem depois
    que a configuração fosse corrigida. O cliente pagava por um monitoramento que
    nunca avisou, e o job logava "1 alerta(s) enviado(s)".

    O que este item faz, e o que ele NÃO faz:

    * **Portão de canal, uma vez por execução, ANTES do laço.** Sem canal de
      entrega real, nenhum e-mail é montado (nada vaza no stdout), nenhum
      ratchet anda, e um único `ERROR` diz qual configuração falta e o que
      fazer — o mesmo formato de `newsletter.enviar_newsletters` e de
      `identidade/emails.py`, e a mesma fonte (`config/email_entrega`).
    * **O ratchet só anda depois de uma entrega aceita.** O
      `criterio.save(update_fields=["ultimo_alerta_em"])` está DEPOIS do
      `entregar_email`, e uma recusa cai no `except` sem gravá-lo. É a
      inversão que fecha o buraco: falha de entrega adia o alerta, não o
      consome.
    * **"Enviado" passa a significar entregue.** `total_alertas_enviados`
      incrementa só depois de `entregar_email` devolver, e
      `total_alertas_enviados` é o número que `b2b/tasks.py` loga.
    * **O que NÃO é responsabilidade deste módulo.** Quem recebe é o conjunto de
      `MembroOrganizacao` da organização (`_entrega_para`), não o solicitante de
      um request: este caminho não é autenticado nem público — é a task
      periódica do Beat, sem endpoint. A lista de destinatários continua
      sendo montada exatamente como era (mesma query, mesmo filtro), porque o
      que estava errado não era QUEM recebia, era o "entregue" que não era
      entrega. Nenhum endereço de membro, nome de organização ou título de
      notícia entra no log: só o id do critério e o da organização, que já eram
      o identificador do operador antes deste item.
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

    # P1-17 — PORTÃO DE CANAL, uma vez por execução, ANTES de qualquer
    # montagem. O motivo é o mesmo para todos os critérios e repetir a frase
    # por critério só inflaria o log com o mesmo texto, então o ERROR é único.
    #
    # O portão NÃO retorna aqui, e essa é a parte que levou a duas correções
    # durante a implementação: um `return` aqui contaria TODOS os critérios
    # ativos como `total_falhas`, e isso é mentira do outro lado — um
    # critério sem novidade nenhuma, ou sem destinatário, não "falhou": não
    # tinha o que entregar. O placar que o operador lê é
    # `total_falhas`/`total_alertas_enviados` por CRITÉRIO, então a contagem
    # honesta só existe depois de saber quais critérios tinham algo a enviar
    # (ver `_registrar_falha_por_sem_canal`, chamado no ponto exato do envio).
    #
    # O que o portão garante, e é o que o `console` medido antes desta
    # correção não garantia: NENHUM e-mail é montado (nada vaza no stdout),
    # e NENHUM ratchet anda. O que se perde é adiado, não consumido.
    canal = verificar_canal_email()
    sem_canal = not canal.disponivel
    if sem_canal:
        registrar_evento(DESTINO_ALERTA_B2B, "sem_canal")
        logger.error(
            "b2b: NENHUM alerta entregue por ausência de canal de entrega real "
            "(motivo=%s). %s",
            "; ".join(canal.motivos),
            orientacao_de_configuracao(),
        )

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

            # P1-17: o envio passa pela costura de transporte, que é o
            # `config.email_entrega.entregar_email`. O ratchet é gravado
            # DEPOIS e só se o envio foi aceito — a inversão que fecha o
            # buraco deste módulo (com `console`, o ratchet avançava sem
            # entrega e a notícia nunca mais era alertada).
            if sem_canal:
                # Ponto exato do envio: aqui já se sabe que HÁ o que enviar
                # (item novo) e HÁ para quem enviar (membro com e-mail), então
                # este é o único lugar onde "falha" é a palavra honesta. Nada
                # é montado, nada é impresso, e o ratchet não é tocado — o
                # alerta fica pendente e sai inteiro na próxima execução com
                # canal.
                total_falhas += 1
                _registrar_anomalia(
                    anomalias,
                    "falha_ao_enviar",
                    criterio.organizacao,
                    f"alerta do critério {criterio.id} não saiu: o projeto não "
                    "tem canal de e-mail que entregue (ver ERROR desta execução).",
                )
                continue

            entregar_alerta(criterio, itens_novos, destinatarios)
            criterio.ultimo_alerta_em = timezone.now()
            criterio.save(update_fields=["ultimo_alerta_em"])
            total_alertas_enviados += 1
            enviados_por_organizacao[criterio.organizacao_id] = enviados_org + 1
        except (CanalIndisponivel, FalhaDeEntrega) as exc:
            # `CanalIndisponivel`/`FalhaDeEntrega` são do gate, e são o
            # caso mais provável aqui: o canal caiu entre o portão do topo e
            # este envio. Não há traceback de propósito — o texto de um
            # provedor real ecoa o payload, e o payload aqui carrega título de
            # notícia e nome de organização; `logger.error` com o TIPO e o
            # destino, nada mais. O ratchet NÃO é tocado: o alerta fica
            # pendente e sai na próxima execução.
            logger.error(
                "b2b: alerta do critério %s NÃO foi entregue (organizacao_id=%s, tipo=%s)",
                criterio.id,
                criterio.organizacao_id,
                type(exc).__name__,
            )
            total_falhas += 1
            _registrar_anomalia(
                anomalias,
                "falha_ao_enviar",
                criterio.organizacao,
                f"falha ao enviar o alerta do critério {criterio.id}: ver log.",
            )
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
